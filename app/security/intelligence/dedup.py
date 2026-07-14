"""Layer 3 Deduplication — collapse duplicate ``Normalized_Finding``s (Requirement 6).

:func:`deduplicate` is a **pure, deterministic** function (no I/O, no hidden state)
that merges every group of :class:`~app.security.models.Normalized_Finding`s
describing the *same vulnerability at the same location* into a single finding,
while preserving every distinct vulnerability as its own finding.

Two findings are considered the same iff they share the same **dedup key**
``(rule_identity, canonical_location)`` where ``canonical_location`` is derived
with the exact same path canonicalization used by
:mod:`app.security.intelligence.normalize`, so keys computed here line up with the
identities assigned during normalization. When a group is collapsed:

* the merged finding's ``scanners`` frozenset equals the **union** of every
  originating scanner in the group (Requirement 6.2); and
* all other fields are taken from the first-seen finding of the group, which — for
  the normalized findings produced upstream — is stable because those fields are a
  pure function of the shared dedup key.

The output preserves the **first-seen order of groups**, so the function is stable
and deterministic: the same input list always yields the same output list.
"""

from __future__ import annotations

from dataclasses import replace

from app.security.intelligence.normalize import _canonical_path
from app.security.models import Location, Normalized_Finding

#: A dedup key: ``(rule_identity, canonical_location)`` where the canonical
#: location is ``(canonical_path, start_line, end_line, symbol)``.
DedupKey = tuple[str, tuple[str, int, int, str]]


def _canonical_location(location: Location) -> tuple[str, int, int, str]:
    """Canonicalize a location for stable, cross-scanner grouping.

    Uses the same path canonicalization as
    :mod:`app.security.intelligence.normalize` so that findings normalized from
    different scanners at the same source location produce identical keys.
    """
    return (
        _canonical_path(location.path),
        location.start_line,
        location.end_line,
        location.symbol or "",
    )


def _dedup_key(finding: Normalized_Finding) -> DedupKey:
    """Derive the ``(rule_identity, canonical_location)`` dedup key (Req 6.1)."""
    return (finding.rule_identity, _canonical_location(finding.location))


def deduplicate(findings: list[Normalized_Finding]) -> list[Normalized_Finding]:
    """Collapse findings sharing a ``(rule_identity, canonical_location)`` key.

    Pure and deterministic: the returned list depends only on ``findings`` and the
    first-seen order of their dedup-key groups.

    Args:
        findings: The normalized findings to deduplicate.

    Returns:
        One :class:`Normalized_Finding` per distinct ``(rule_identity,
        canonical_location)`` group (Requirement 6.1, 6.3). Each merged finding's
        ``scanners`` frozenset is the union of the group's originating scanners
        (Requirement 6.2); every other field comes from the group's first-seen
        finding. Group order follows first appearance in ``findings``.
    """
    merged: dict[DedupKey, Normalized_Finding] = {}
    scanners_by_key: dict[DedupKey, set[str]] = {}

    for finding in findings:
        key = _dedup_key(finding)
        if key not in merged:
            # First finding of this group establishes the base + insertion order.
            merged[key] = finding
            scanners_by_key[key] = set(finding.scanners)
        else:
            # Subsequent duplicates only contribute their originating scanners.
            scanners_by_key[key].update(finding.scanners)

    return [
        replace(base, scanners=frozenset(scanners_by_key[key]))
        for key, base in merged.items()
    ]
