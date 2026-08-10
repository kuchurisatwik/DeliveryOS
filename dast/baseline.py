"""Per-target baseline — so each scan reports what's *new*, not everything.

A scanner pointed at a real application reports the same known issues on every
run. Without a baseline the report is the same wall of text every time, the team
stops reading it, and a genuinely new vulnerability arrives buried in noise it is
indistinguishable from.

The baseline is a set of ``finding_id`` values per target. Because those ids are a
stable hash of ``(rule_identity, endpoint identity)``, the same issue at the same
endpoint hashes identically on every run, and the diff between two scans is
meaningful.

Two rules here are specific to *dynamic* scanning and matter more than the diff
itself:

**A finding that disappears has not necessarily been fixed.** In SAST, a finding
vanishing means the code changed. In DAST it might mean the code changed — or that
the scanner never reached that endpoint this time, because auth expired, a rate
limiter kicked in, or the app was still warming up. So "resolved" is only reported
when every tool completed. Otherwise those findings are held as *unverified*, and
the baseline keeps them.

**A bad scan must never overwrite a good baseline.** If a scan that reached
nothing were allowed to write its (empty) results, every real finding would be
forgotten, and the next scan would report the entire backlog as brand new. The
baseline is only updated from a scan that is trustworthy on its own terms.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from app.security.models import Normalized_Finding
from app.utils.logger import logger
from dast.config import dast_settings

_BASELINES_SUBDIR = "baselines"


def target_key(target_url: str) -> str:
    """Canonical identity of a scan target: ``scheme://host:port``.

    The path is dropped so that scanning ``https://staging.test`` and
    ``https://staging.test/`` share one baseline, and the host is lowercased
    because DNS is case-insensitive but string comparison is not.
    """
    parts = urlsplit(target_url.strip())
    if not parts.scheme:
        return target_url.strip().lower().rstrip("/")
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


@dataclass(frozen=True)
class BaselineDiff:
    """How this scan's findings compare with what we already knew."""

    new: tuple[str, ...] = ()
    #: Present in this scan and already in the baseline.
    known: tuple[str, ...] = ()
    #: In the baseline but absent here, *and* the scan was complete enough to
    #: treat that absence as meaningful.
    resolved: tuple[str, ...] = ()
    #: In the baseline but absent here while coverage was incomplete — we cannot
    #: tell "fixed" from "not looked at", so we say so instead of guessing.
    unverified: tuple[str, ...] = ()
    #: True when this target had no baseline yet. Everything is technically new
    #: on a first scan, which makes "new" meaningless, so it is reported empty.
    is_first_scan: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "new": list(self.new),
            "known": list(self.known),
            "resolved": list(self.resolved),
            "unverified": list(self.unverified),
            "is_first_scan": self.is_first_scan,
            "new_count": len(self.new),
            "known_count": len(self.known),
            "resolved_count": len(self.resolved),
            "unverified_count": len(self.unverified),
        }


def _baselines_dir() -> str:
    path = os.path.join(dast_settings.DAST_STATE_DIR, _BASELINES_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _baseline_path(key: str) -> str:
    # Hash the key: a URL contains ``:`` and ``/``, neither of which is a legal
    # filename character on Windows.
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(_baselines_dir(), f"{digest}.json")


def load(target_url: str) -> dict[str, Any]:
    """Read a target's baseline. Returns ``{}`` when none exists yet."""
    try:
        with open(_baseline_path(target_key(target_url)), "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload.get("findings") or {}
    except (OSError, ValueError):
        return {}


def diff(
    baseline: Mapping[str, Any],
    findings: Sequence[Normalized_Finding],
    *,
    coverage_complete: bool,
) -> BaselineDiff:
    """Compare this scan's findings against the stored baseline.

    Pure: no I/O, so the interesting rules are directly testable.
    """
    current = {f.finding_id for f in findings}
    known_ids = set(baseline)

    if not known_ids:
        # Nothing to compare against. Reporting every finding as "new" on a first
        # scan would be technically true and completely useless.
        return BaselineDiff(
            known=tuple(sorted(current)), is_first_scan=True
        )

    new = tuple(sorted(current - known_ids))
    known = tuple(sorted(current & known_ids))
    missing = sorted(known_ids - current)

    # A finding can only be called "resolved" if we actually looked for it.
    if coverage_complete:
        return BaselineDiff(new=new, known=known, resolved=tuple(missing))
    return BaselineDiff(new=new, known=known, unverified=tuple(missing))


def update(
    target_url: str,
    findings: Iterable[Normalized_Finding],
    *,
    previous: Mapping[str, Any] | None = None,
    drop: Iterable[str] = (),
) -> None:
    """Write the target's baseline from a trustworthy scan.

    ``first_seen`` is preserved for findings already known, so the record shows
    how long an issue has been outstanding rather than resetting on every scan.
    ``drop`` removes ids confirmed resolved; anything merely *unverified* is
    retained, because forgetting it would make it reappear as new next time.
    """
    previous = previous or {}
    dropped = set(drop)
    now = time.time()

    entries: dict[str, Any] = {
        finding_id: entry
        for finding_id, entry in previous.items()
        if finding_id not in dropped
    }

    for finding in findings:
        existing = entries.get(finding.finding_id) or {}
        entries[finding.finding_id] = {
            "first_seen": existing.get("first_seen", now),
            "last_seen": now,
            "severity": finding.severity.name,
            "rule_identity": finding.rule_identity,
            "path": finding.location.path,
        }

    key = target_key(target_url)
    payload = {"target": key, "updated_at": now, "findings": entries}
    path = _baseline_path(key)
    try:
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(temp_path, path)
        logger.info(
            "Baseline for %s updated: %d finding(s) tracked (%d dropped as resolved)",
            key,
            len(entries),
            len(dropped),
        )
    except OSError as exc:  # noqa: BLE001 - a failed baseline write must not fail the scan
        logger.error("Could not write baseline for %s: %s", key, exc)
