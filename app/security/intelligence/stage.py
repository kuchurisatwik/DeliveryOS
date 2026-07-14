"""Layer 3 Intelligence — the full-flow assembly Stage.

:class:`IntelligenceStage` is the net-new Layer 3 workflow stage (subclassing the
existing :class:`app.workflows.stages.Stage`). It wires the deterministic core and
the AI/verification boundaries into the single ordered flow the design's
``IntelligenceLayer.process`` describes:

    normalize → deduplicate → enrich → score / order → triage → repair → verify

and emits an :class:`~app.security.models.IntelligenceResult` that partitions the
findings into ``fixed`` and ``remaining`` (each finding carrying its triage, patch
if any, and status). The result is written onto the shared
:class:`~app.workflows.context.WorkflowContext` (``context.intelligence_result``).

Pure vs. impure
---------------
The pure deterministic stages (:mod:`~app.security.intelligence.normalize`,
:mod:`~app.security.intelligence.dedup`, :mod:`~app.security.intelligence.enrich`,
:mod:`~app.security.intelligence.scoring`) and the pure orchestration in
:func:`~app.security.intelligence.triage.attach_triage` need no injection. The two
AI boundaries (triage, repair) and the verification scanner re-run are the only
side-effecting parts, and all three are **injected** via the constructor:

* ``triage_adapter`` — an :class:`~app.security.protocols.AITriageAdapter`
* ``repair_adapter`` — an :class:`~app.security.protocols.AIRepairAdapter`
* ``scan_patched``   — the :data:`~app.security.intelligence.verify.PatchedScanner`
  callable the :class:`~app.security.intelligence.verify.Verifier` uses to re-run
  the Layer 2 scanners against the patched scope.

Injecting all three lets the whole stage run end-to-end with in-memory fakes — no
LLM, no scanner subprocess, no network — which is how the Layer 3 tests exercise it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Optional

from app.security.detection.runner import derive_scan_scope
from app.security.intelligence.dedup import deduplicate
from app.security.intelligence.enrich import enrich
from app.security.intelligence.normalize import normalize
from app.security.intelligence.scoring import order_by_risk, score_findings
from app.security.intelligence.triage import attach_triage
from app.security.intelligence.verify import Verifier
from app.security.models import (
    FindingStatus,
    IntelligenceResult,
    Normalized_Finding,
    ScanScope,
)
from app.workflows.context import WorkflowContext
from app.workflows.stages import Stage
from app.utils.logger import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.security.protocols import AIRepairAdapter, AITriageAdapter
    from app.security.intelligence.verify import PatchedScanner

#: Recorded reason when AI_Repair produces no patch for a finding (Requirement 10.4).
NO_PATCH_REASON = "AI_Repair produced no candidate patch."
#: Recorded reason when a false-positive-labeled finding is not repaired.
FALSE_POSITIVE_REASON = "Labeled likely false positive; retained for human review."
#: Recorded reason when verification does not confirm resolution (Requirement 11.3).
UNRESOLVED_REASON = "Verification did not confirm the finding was resolved."
#: Recorded reason when the patch introduced a new finding (Requirement 11.4).
INTRODUCED_REASON = "Patch rejected: it introduced a finding absent from the baseline."


class IntelligenceStage(Stage):
    """Runs the ordered Layer 3 flow and produces an :class:`IntelligenceResult`."""

    def __init__(
        self,
        triage_adapter: "AITriageAdapter",
        repair_adapter: "AIRepairAdapter",
        scan_patched: "PatchedScanner",
    ) -> None:
        """Create the stage with its three injected side-effecting boundaries.

        Args:
            triage_adapter: Produces an :class:`AITriage` per finding (Requirement 9).
            repair_adapter: Produces a :class:`CandidatePatch` or ``None`` per
                finding (Requirement 10).
            scan_patched: Re-runs the Layer 2 scanners against the patched scope for
                verification (Requirement 11.1); wrapped by a :class:`Verifier`.
        """
        self._triage_adapter = triage_adapter
        self._repair_adapter = repair_adapter
        self._verifier = Verifier(scan_patched)

    # ------------------------------------------------------------------ #
    # Stage entry point
    # ------------------------------------------------------------------ #

    def execute(self, context: WorkflowContext) -> None:
        detection_result: Any = context.detection_result
        raw_findings = list(getattr(detection_result, "findings", None) or [])
        repo_context: Any = context.retrieved_knowledge
        scope = derive_scan_scope(context)

        logger.info(
            "IntelligenceStage: processing %d raw finding(s)", len(raw_findings)
        )
        context.intelligence_result = self._process(raw_findings, repo_context, scope)

    # ------------------------------------------------------------------ #
    # Ordered flow (design IntelligenceLayer.process)
    # ------------------------------------------------------------------ #

    def _process(
        self, raw_findings: list[Any], repo_context: Any, scope: ScanScope
    ) -> IntelligenceResult:
        """Run normalize → dedup → enrich → score/order → triage → repair → verify."""
        # 1. Normalization (Requirement 5) — pure.
        normalized = [normalize(f) for f in raw_findings]
        # 2. Deduplication (Requirement 6) — pure.
        deduped = deduplicate(normalized)
        # 3. Enrichment (Requirement 7) — pure.
        enriched = enrich(deduped, repo_context)
        # 4. Risk scoring + ordering (Requirement 8) — pure.
        ordered = order_by_risk(score_findings(tuple(enriched)))
        # 5. AI triage (Requirement 9) — injected adapter, retains all findings.
        triaged = attach_triage(list(ordered), self._triage_adapter, repo_context)

        # The pre-patch finding set is the verification baseline: any post-patch
        # finding whose identity is not present here counts as newly introduced.
        baseline = list(triaged)

        # 6. AI repair (Requirement 10) + 7. Verification (Requirement 11).
        processed = [
            self._repair_and_verify(finding, repo_context, baseline, scope)
            for finding in triaged
        ]

        fixed = tuple(f for f in processed if f.status is FindingStatus.FIXED)
        remaining = tuple(f for f in processed if f.status is not FindingStatus.FIXED)
        logger.info(
            "IntelligenceStage: %d fixed, %d remaining", len(fixed), len(remaining)
        )
        return IntelligenceResult(fixed=fixed, remaining=remaining)

    # ------------------------------------------------------------------ #
    # Per-finding repair + verification (Requirements 10, 11)
    # ------------------------------------------------------------------ #

    def _repair_and_verify(
        self,
        finding: Normalized_Finding,
        repo_context: Any,
        baseline: list[Normalized_Finding],
        scope: ScanScope,
    ) -> Normalized_Finding:
        """Repair a single finding and verify the resulting patch.

        Follows the design's Requirement 10 + 11 semantics:

        * A finding labeled a likely false positive is **retained** unrepaired for
          human review (Requirement 9.2 / 10.1 — repair is only attempted for
          non-false-positive findings).
        * Otherwise AI_Repair is asked for a :class:`CandidatePatch`; when none is
          produced the finding is marked ``unresolved`` with a recorded reason
          (Requirement 10.4).
        * A produced patch is re-verified by re-running the scanners
          (Requirement 11.1): accepted patches mark the finding ``fixed``
          (Requirement 11.2); a patch that does not confirm resolution
          (Requirement 11.3) or introduces a new finding (Requirement 11.4) is
          rejected and the finding marked ``unresolved``.
        """
        # Likely false positives are retained but never repaired.
        if finding.likely_false_positive:
            return replace(
                finding,
                status=FindingStatus.UNRESOLVED,
                unresolved_reason=FALSE_POSITIVE_REASON,
            )

        patch = self._repair_adapter.repair(finding, repo_context)

        # Requirement 10.4 — no patch means the finding stays unresolved.
        if patch is None:
            return replace(
                finding,
                status=FindingStatus.UNRESOLVED,
                unresolved_reason=NO_PATCH_REASON,
            )

        finding = replace(finding, candidate_patch=patch)

        # Requirement 11 — deterministic re-verification.
        outcome = self._verifier.verify(patch, baseline, scope)
        if outcome.accepted:
            return replace(finding, status=FindingStatus.FIXED, unresolved_reason=None)

        reason = INTRODUCED_REASON if outcome.introduced_findings else UNRESOLVED_REASON
        return replace(
            finding,
            status=FindingStatus.UNRESOLVED,
            unresolved_reason=reason,
        )
