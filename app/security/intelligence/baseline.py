"""Layer 3 Baseline / delta mode — surface only newly introduced findings (Phase 1).

On a mature repository a full scan reports the whole backlog of pre-existing
findings on every push, which drowns out the issues a *change* actually
introduced. Baseline mode fixes that: a stored set of finding **fingerprints**
represents "known / accepted" findings, and a run in delta mode reports only the
findings whose fingerprint is absent from the baseline.

A fingerprint is deliberately **line-independent** — ``sha256(rule_identity |
canonical_path)`` — so a finding is still recognised as "known" after unrelated
edits shift its line number. This trades a little precision (two occurrences of
the same rule in one file share a fingerprint) for stability, which is the right
call for a noise-reduction baseline.

Everything here is pure except the small JSON load/save helpers, which are the
only I/O touchpoints and fail safe (a missing/corrupt baseline behaves like an
empty baseline, so delta mode degrades to reporting everything rather than hiding
findings).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Iterable

from app.security.intelligence.normalize import _canonical_path
from app.security.models import Normalized_Finding
from app.utils.logger import logger


def fingerprint(finding: Normalized_Finding) -> str:
    """Return a stable, line-independent fingerprint for a finding (pure)."""
    canonical = "|".join(
        (finding.rule_identity, _canonical_path(finding.location.path))
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def compute_fingerprints(findings: Iterable[Normalized_Finding]) -> list[str]:
    """Return the sorted, de-duplicated fingerprints of ``findings`` (pure)."""
    return sorted({fingerprint(f) for f in findings})


def filter_new(
    findings: list[Normalized_Finding], baseline: set[str]
) -> list[Normalized_Finding]:
    """Return only findings whose fingerprint is absent from ``baseline`` (pure).

    Order is preserved. An empty baseline returns every finding unchanged.
    """
    if not baseline:
        return list(findings)
    return [f for f in findings if fingerprint(f) not in baseline]


def load_baseline(path: str) -> set[str]:
    """Load a baseline fingerprint set from ``path``; empty set on any problem."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    if isinstance(data, dict):
        data = data.get("fingerprints", [])
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data}


def write_baseline(path: str, findings: Iterable[Normalized_Finding]) -> None:
    """Write the current findings' fingerprints to ``path`` as JSON (best-effort)."""
    payload = {
        "version": 1,
        "fingerprints": compute_fingerprints(findings),
    }
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except OSError as exc:  # pragma: no cover - best effort
        logger.warning("Failed to write security baseline to %s: %s", path, exc)


def resolve_baseline_path(workspace: str | None, configured: str) -> str | None:
    """Resolve the baseline file path from settings, or ``None`` when disabled."""
    configured = (configured or "").strip()
    if not configured or configured.lower() in ("off", "none", "false"):
        return None
    if os.path.isabs(configured):
        return configured
    base = workspace or os.getcwd()
    return os.path.join(base, configured)
