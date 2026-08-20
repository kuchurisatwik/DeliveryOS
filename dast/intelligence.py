"""Turns raw tool findings into stable, deduplicated findings.

This is the DAST service's use of the SAST pipeline's intelligence layer: the
same pure :func:`~app.security.intelligence.normalize.normalize` and
:func:`~app.security.intelligence.dedup.deduplicate` functions, imported rather
than reimplemented, so both pipelines derive finding identity identically.

Why it matters here: a raw :class:`~app.security.models.Finding` has no id. Only
after normalisation does it carry a ``finding_id`` — a hash of the rule identity
plus the location — and without that there is nothing to compare between runs, so
no baseline and no "show me only what's new" is possible.

One wrinkle this module exists to solve: :class:`Normalized_Finding` deliberately
carries no ``raw`` field, because the SAST layer only needs file and line. For a
dynamic finding the raw payload *is* the proof — it holds the request that was
sent and the response that came back, which is the first thing anyone triaging
the finding asks for. So the raw payloads are carried alongside, keyed by the
finding id they normalised into.

That keying is exact rather than approximate: ``_derive_finding_id`` hashes
``(rule_identity, canonical_location)`` and ``_dedup_key`` groups on the very same
pair, so every finding that dedup merges necessarily shares one ``finding_id``.
The evidence map therefore lines up one-to-one with the deduplicated output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.security.intelligence.dedup import deduplicate
from app.security.intelligence.normalize import normalize
from app.security.models import Finding, Normalized_Finding
from app.utils.logger import logger


@dataclass(frozen=True)
class ConsolidatedFindings:
    """Deduplicated findings plus the raw evidence behind each one."""

    findings: tuple[Normalized_Finding, ...] = ()
    #: ``finding_id`` -> the raw tool payloads that produced it. One entry per
    #: occurrence, so a rule that fired on twelve URLs keeps all twelve.
    evidence: dict[str, list[Finding]] = field(default_factory=dict)
    #: How many raw findings went in, before deduplication.
    raw_count: int = 0

    @property
    def collapsed(self) -> int:
        """How many duplicate findings deduplication removed."""
        return max(0, self.raw_count - len(self.findings))


def consolidate(findings: Sequence[Finding]) -> ConsolidatedFindings:
    """Normalise and deduplicate raw tool findings, preserving their evidence.

    Pure apart from logging: the same input always yields the same ``finding_id``
    values, which is exactly the property a baseline diff depends on.
    """
    normalized: list[Normalized_Finding] = []
    evidence: dict[str, list[Finding]] = {}

    for finding in findings:
        normalised_finding = normalize(finding)
        normalized.append(normalised_finding)
        evidence.setdefault(normalised_finding.finding_id, []).append(finding)

    deduped = tuple(deduplicate(normalized))

    result = ConsolidatedFindings(
        findings=deduped, evidence=evidence, raw_count=len(findings)
    )
    if result.collapsed:
        logger.info(
            "Consolidated %d raw finding(s) into %d unique (%d duplicate(s) merged)",
            result.raw_count,
            len(deduped),
            result.collapsed,
        )
    return result
