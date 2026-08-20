"""The scan job: preflight, run the tools, record the result.

This is the function the queue worker calls. It is deliberately linear and
side-effecting at the edges only — everything it calls (preflight, the runner,
storage) is independently testable.
"""

from __future__ import annotations

import os
import time
from typing import Optional
from urllib.parse import urljoin

import httpx

from app.utils.logger import logger
from dast import baseline, storage
from dast.config import dast_settings
from dast.endpoints.extractor import EndpointExtractor
from dast.endpoints.models import (
    EndpointInventory,
    ExtractionActivity,
    ExtractionResult,
)
from dast.endpoints.reconcile import reconcile
from dast.endpoints.synthesize import synthesize_openapi_bytes
from dast.intelligence import consolidate
from dast.models import DastScope, ScanRecord
from dast.preflight import PreflightError, PreflightResult, run_preflight
from dast.runner import run_scan

#: What one extraction run yields when no source tree is available to walk: an
#: empty inventory and a zeroed activity record. Reusing a single frozen pair keeps
#: the "no source_root" path allocation-free and unambiguous — an absent source is
#: recorded as "read nothing, found nothing, no languages", never as a clean scan.
_EMPTY_INVENTORY = EndpointInventory(endpoints=())
_EMPTY_ACTIVITY = ExtractionActivity(
    files_read=0, endpoints_found=0, languages=frozenset()
)


def synth_spec_path(scan_id: str) -> str:
    """On-disk path of the synthesised OpenAPI spec for ``scan_id``.

    Kept under the state directory (not a random temp file) so the HTTP surface
    can serve it back to the ZAP sidecar by scan id — this is the file ZAP imports
    to seed its site tree when the target publishes no spec of its own.
    """
    return os.path.join(dast_settings.DAST_STATE_DIR, "specs", f"{scan_id}.json")


def _activity_to_dict(activity: ExtractionActivity) -> dict:
    """Serialise an :class:`ExtractionActivity` for the preflight record (Req 11.4).

    ``languages`` is a frozenset, which is not JSON-serialisable and has no stable
    order; it is emitted as a sorted list so the on-disk scan record is both valid
    JSON and deterministic across runs.
    """
    return {
        "files_read": activity.files_read,
        "endpoints_found": activity.endpoints_found,
        "languages": sorted(activity.languages),
    }


def _extract_inventory(record: ScanRecord) -> ExtractionResult:
    """Statically extract endpoints from the scan's source tree, if one is given.

    The checked-out repository path rides on the scan request as ``source_root``.
    When it is present, the :class:`EndpointExtractor` walks it and returns the
    inventory plus its evidence; when it is absent (the common case today), an
    empty inventory and zeroed activity stand in so the rest of scope assembly is
    identical whether or not a source tree was supplied (Req 1.1).

    Read defensively via ``getattr`` so this preserves existing behaviour on a
    ``ScanRecord`` that carries no ``source_root`` at all.
    """
    source_root = getattr(record, "source_root", None)
    if not source_root:
        return ExtractionResult(inventory=_EMPTY_INVENTORY, activity=_EMPTY_ACTIVITY)
    return EndpointExtractor().extract(source_root)


def _assemble_scope(record: ScanRecord, preflight: PreflightResult) -> DastScope:
    """Assemble the scan scope with reconciled, source-seeded ``spec_paths``.

    This is the service seam where static endpoint extraction meets the runtime
    OpenAPI spec. It:

    - extracts the source-code endpoint inventory (empty when no source tree);
    - reconciles the runtime spec templates with the inventory templates into one
      distinct-identity set, placed on ``DastScope.spec_paths`` verbatim so the ZAP
      and Schemathesis adapters seed themselves with no adapter change (Req 7.1-7.4);
    - records extraction evidence and the seed count/seeded flag in the scan's
      preflight record (Req 11.4, 11.5) so an empty inventory + empty spec surfaces
      as an unseeded scan surface rather than a clean one (Req 11.2, 11.3);
    - when the target published no runtime spec, writes the synthesised OpenAPI
      document to a temp file and points ``DAST_SCHEMATHESIS_SCHEMA_FILE`` at it so
      Schemathesis runs against the synthesised schema while ZAP seeds from the same
      reconciled ``spec_paths`` (Req 8.1, 8.2).
    """
    result = _extract_inventory(record)
    inventory = result.inventory

    reconciled = reconcile(
        preflight.spec_paths, [endpoint.path for endpoint in inventory.endpoints]
    )

    # Extraction evidence + seed accounting on the preflight record (Req 11.4, 11.5).
    # ``seeded`` is False exactly when the reconciled surface is empty — which, when
    # both the inventory and the runtime spec were empty, is what marks the scan
    # surface unseeded rather than scanned-and-clean (Req 11.2, 11.3).
    record.preflight["extraction"] = _activity_to_dict(result.activity)
    record.preflight["spec_seed"] = {
        "seed_count": len(reconciled),
        "seeded": bool(reconciled),
    }

    # No runtime spec → drive BOTH scanners from a synthesised schema. Even an empty
    # inventory yields a structurally valid (empty-paths) document, so Schemathesis
    # loads *something* rather than falling back to fetching a spec the target does
    # not publish (Req 8.1, 8.2). The same file is served back to ZAP (below) so it
    # seeds from our synthesised spec instead of the target's absent /openapi.json.
    spec_url: Optional[str] = None
    if not preflight.spec_paths:
        schema_bytes = synthesize_openapi_bytes(inventory)
        schema_path = synth_spec_path(record.scan_id)
        os.makedirs(os.path.dirname(schema_path), exist_ok=True)
        with open(schema_path, "wb") as handle:
            handle.write(schema_bytes)
        dast_settings.DAST_SCHEMATHESIS_SCHEMA_FILE = schema_path

        # Point ZAP at the served synthesised spec (with the target as host
        # override) only when we know a URL the sidecar can reach us on. Without
        # DAST_SELF_URL there is no such URL, so ZAP keeps its prior behaviour of
        # importing the target's own DAST_OPENAPI_PATH.
        self_url = dast_settings.DAST_SELF_URL
        if self_url:
            spec_url = f"{self_url.rstrip('/')}/internal/openapi/{record.scan_id}"

        logger.info(
            "DAST scan %s: target published no OpenAPI spec; scanners will run "
            "against a synthesised schema at %s (%d endpoint(s)); ZAP spec_url=%s",
            record.scan_id,
            schema_path,
            len(inventory.endpoints),
            spec_url or "(target /openapi.json fallback)",
        )

    return DastScope(
        target_url=record.target_url,
        commit_sha=record.commit_sha,
        auth_header=dast_settings.DAST_AUTH_HEADER,
        spec_paths=reconciled,
        spec_url=spec_url,
        profile=record.profile,
    )


def _target_reachable(target_url: str, *, attempts: int = 3) -> bool:
    """Cheap "is the target still up?" probe used as the runner's mid-scan guard.

    Hits the health path directly (not through the proxy) so a dead upstream reads
    as a connection failure rather than a proxy 502. Retries a few times with short
    gaps so a momentary blip under load is not mistaken for a crash — only a target
    that stays unreachable across every attempt is reported as down.
    """
    base = target_url.rstrip("/") + "/"
    health_url = urljoin(base, dast_settings.DAST_HEALTH_PATH.lstrip("/"))
    for attempt in range(attempts):
        try:
            response = httpx.get(health_url, timeout=5.0, follow_redirects=True)
            if response.status_code < 500:
                return True
        except httpx.HTTPError:
            pass
        if attempt < attempts - 1:
            time.sleep(1.0)
    return False


def run_dast_scan(record: ScanRecord) -> None:
    """Execute one scan end to end and persist the outcome.

    Never raises: the queue worker treats an exception as a failed job, but we want
    the *reason* durably attached to the scan record so it shows up in the UI rather
    than only in the logs.
    """
    record.status = "running"
    record.started_at = time.time()
    storage.save(record)

    try:
        preflight = run_preflight(
            record.target_url,
            commit_sha=record.commit_sha,
            auth_header=dast_settings.DAST_AUTH_HEADER,
        )
        record.preflight = preflight.to_dict()

        # Assemble the scope: reconcile the runtime spec with the source-extracted
        # endpoint inventory and seed the scanners through DastScope.spec_paths.
        # This also records extraction/seed evidence on record.preflight, so save
        # after it runs to persist that evidence.
        scope = _assemble_scope(record, preflight)
        storage.save(record)

        result = run_scan(
            scope, health_check=lambda: _target_reachable(record.target_url)
        )

        # Normalise and deduplicate before storing. This is what gives every
        # finding a stable ``finding_id``, which is the prerequisite for the
        # baseline: without it there is nothing to diff between two runs.
        consolidated = consolidate(result.findings)

        # Compare against what we already knew about this target, so the report
        # can lead with what is NEW rather than repeating the same known issues
        # every run until people stop reading it.
        coverage_complete = bool(result.coverage) and all(
            c.status == "complete" for c in result.coverage
        )
        previous = baseline.load(record.target_url)
        diff = baseline.diff(
            previous, consolidated.findings, coverage_complete=coverage_complete
        )
        record.baseline = diff.to_dict()

        new_ids = set(diff.new)
        record.raw_finding_count = consolidated.raw_count
        record.findings = [
            {
                **storage.normalized_finding_to_dict(
                    finding, consolidated.evidence.get(finding.finding_id, ())
                ),
                "is_new": finding.finding_id in new_ids,
                "first_seen": (previous.get(finding.finding_id) or {}).get("first_seen"),
            }
            for finding in consolidated.findings
        ]
        record.coverage = [c.to_dict() for c in result.coverage]
        # A scan where no tool completed is a failed scan, not a clean one. Without
        # this the most dangerous outcome — every tool silently broken — renders as
        # a green, empty report.
        if result.coverage and all(c.status != "complete" for c in result.coverage):
            record.status = "failed"
            record.error = "no tool completed successfully; results are not usable"
        else:
            record.status = "done"
            # Only a scan that actually worked may update the baseline. Letting a
            # scan that reached nothing write its empty results would erase every
            # known finding, and the next run would report the whole backlog as
            # brand new. Findings merely *unverified* this run are retained —
            # only confirmed-resolved ones are dropped.
            baseline.update(
                record.target_url,
                consolidated.findings,
                previous=previous,
                drop=diff.resolved,
            )

    except PreflightError as exc:
        logger.error("DAST scan %s failed preflight: %s", record.scan_id, exc)
        record.status = "failed"
        record.error = f"preflight: {exc}"
    except Exception as exc:  # noqa: BLE001 - record the reason, never crash the worker
        logger.exception("DAST scan %s failed", record.scan_id)
        record.status = "failed"
        record.error = str(exc)[:500]
    finally:
        record.finished_at = time.time()
        storage.save(record)
        logger.info(
            "DAST scan %s finished: status=%s findings=%d",
            record.scan_id,
            record.status,
            len(record.findings),
        )
