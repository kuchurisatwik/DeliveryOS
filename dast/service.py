"""The scan job: preflight, run the tools, record the result.

This is the function the queue worker calls. It is deliberately linear and
side-effecting at the edges only — everything it calls (preflight, the runner,
storage) is independently testable.
"""

from __future__ import annotations

import time

from app.utils.logger import logger
from dast import storage
from dast.config import dast_settings
from dast.models import DastScope, ScanRecord
from dast.preflight import PreflightError, run_preflight
from dast.runner import run_scan


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
        storage.save(record)

        scope = DastScope(
            target_url=record.target_url,
            commit_sha=record.commit_sha,
            auth_header=dast_settings.DAST_AUTH_HEADER,
            spec_paths=preflight.spec_paths,
            profile=record.profile,
        )
        result = run_scan(scope)

        record.findings = [storage.finding_to_dict(f) for f in result.findings]
        record.coverage = [c.to_dict() for c in result.coverage]
        # A scan where no tool completed is a failed scan, not a clean one. Without
        # this the most dangerous outcome — every tool silently broken — renders as
        # a green, empty report.
        if result.coverage and all(c.status != "complete" for c in result.coverage):
            record.status = "failed"
            record.error = "no tool completed successfully; results are not usable"
        else:
            record.status = "done"

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
