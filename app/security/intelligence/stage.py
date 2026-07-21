"""Layer 3 Intelligence — the full-flow assembly Stage.

Verification is optional (opt-in via ``SECURITY_VERIFY_PATCHES``). When disabled
(the default), AI-generated patches are attached to findings as **advisory
suggestions** — no scanner re-run, no scanner-confirmed ``fixed`` status. The
finding retains status ``UNRESOLVED`` with a reason marking it as an unverified
AI suggestion so a human reviewer can apply it. This avoids ~40s of scanner
re-run per finding while patch-application-to-disk is not yet implemented; the
scanner-verified path stays available via the flag for the future closed-loop
mode.

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
from app.security.intelligence.correlate import correlate
from app.security.intelligence import baseline as baseline_mod
from app.security.intelligence.enrich import enrich
from app.security.intelligence.normalize import normalize
from app.security.intelligence.scoring import order_by_risk, score_findings
from app.security.intelligence.triage import attach_triage
from app.security.intelligence.verify import Verifier
from app.security.models import (
    AITriage,
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
#: Recorded reason when verification is disabled and the AI patch is attached
#: as an advisory suggestion for the human reviewer.
UNVERIFIED_PATCH_REASON = (
    "AI suggested a fix — advisory only, not scanner-verified. Human review required."
)


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

        from app.config.settings import settings

        mode = (settings.SECURITY_TRIAGE_MODE or "batch").strip().lower()
        logger.info(
            "IntelligenceStage: processing %d raw finding(s) in '%s' mode",
            len(raw_findings),
            mode,
        )
        if mode == "batch":
            context.intelligence_result = self._process_batch(
                raw_findings, repo_context, context
            )
        else:  # "per_finding" (and any legacy value) → original per-finding loop
            context.intelligence_result = self._process(
                raw_findings, repo_context, scope, context
            )

    # ------------------------------------------------------------------ #
    # Shared deterministic core (Phase 1: + cross-tool correlation + baseline)
    # ------------------------------------------------------------------ #

    def _prepare_findings(
        self, raw_findings: list[Any], repo_context: Any
    ) -> list[Normalized_Finding]:
        """normalize → dedup → (correlate) → enrich → score → order (pure).

        Cross-tool correlation runs between dedup and enrich so scoring/ordering
        operate on the merged finding set. It is gated by
        ``SECURITY_CORRELATE_FINDINGS`` (default on).
        """
        from app.config.settings import settings

        normalized = [normalize(f) for f in raw_findings]
        deduped = deduplicate(normalized)
        if getattr(settings, "SECURITY_CORRELATE_FINDINGS", True):
            before = len(deduped)
            deduped = correlate(deduped)
            if len(deduped) != before:
                logger.info(
                    "Cross-tool correlation: %d → %d finding(s) after merging "
                    "same-class same-location duplicates.",
                    before, len(deduped),
                )
        enriched = enrich(deduped, repo_context)
        return list(order_by_risk(score_findings(tuple(enriched))))

    def _apply_baseline(
        self, ordered: list[Normalized_Finding], context: WorkflowContext
    ) -> list[Normalized_Finding]:
        """Apply baseline/delta mode: filter to new findings, or refresh the baseline.

        Gated by ``SECURITY_BASELINE`` (a path). When ``SECURITY_BASELINE_UPDATE``
        is set the baseline is (re)written from this run and no filtering happens.
        Disabled (empty setting) → returns ``ordered`` unchanged.
        """
        from app.config.settings import settings

        path = baseline_mod.resolve_baseline_path(
            getattr(context, "workspace", None),
            getattr(settings, "SECURITY_BASELINE", ""),
        )
        if path is None:
            return ordered

        if getattr(settings, "SECURITY_BASELINE_UPDATE", False):
            baseline_mod.write_baseline(path, ordered)
            logger.info(
                "Security baseline refreshed at %s (%d fingerprint(s)); no filtering.",
                path, len(ordered),
            )
            return ordered

        known = baseline_mod.load_baseline(path)
        if not known:
            logger.info(
                "Security baseline at %s is empty/missing; reporting all findings.", path
            )
            return ordered
        new_findings = baseline_mod.filter_new(ordered, known)
        logger.info(
            "Baseline delta: %d of %d finding(s) are new (baseline has %d known).",
            len(new_findings), len(ordered), len(known),
        )
        return new_findings

    # ------------------------------------------------------------------ #
    # Batch mode (production): deterministic grouping + 1–N batched LLM calls
    # ------------------------------------------------------------------ #

    def _process_batch(
        self, raw_findings: list[Any], repo_context: Any, context: WorkflowContext
    ) -> IntelligenceResult:
        """Group findings by rule, severity-gate, then analyze in 1–N LLM calls.

        Produces the same normalized/deduped/scored finding set as per-finding
        mode, but attaches AI analysis at the *rule* level (one call covers many
        findings). Escalated (HIGH/CRITICAL) rule-groups get an AI remediation;
        the rest are reported deterministically. Nothing is repaired or verified
        in this mode — every finding is returned as ``remaining`` with its triage
        attached, and a per-rule remediation guide is stored on the context for
        the report.
        """
        from dataclasses import replace as _replace

        from app.config.settings import settings
        from app.security.models import Severity
        from app.security.intelligence.batch_triage import (
            LLMBatchTriage,
            RuleAnalysis,
            group_findings,
            parse_severities,
            select_for_ai,
        )
        from app.security.intelligence.remediation_kb import lookup_remediation

        ordered = self._prepare_findings(raw_findings, repo_context)
        ordered = self._apply_baseline(ordered, context)

        groups = group_findings(ordered)
        severities = parse_severities(settings.SECURITY_AI_SEVERITIES)
        escalate, rest = select_for_ai(groups, severities)

        # A representative finding per rule (first occurrence in risk order) — used
        # for the dedicated CRITICAL repair call.
        representative: dict[str, Normalized_Finding] = {}
        for f in ordered:
            representative.setdefault(f.rule_identity, f)

        # --- Tier 1+2: batched text + illustrative snippets for HIGH/CRITICAL ---
        analyzer = LLMBatchTriage(
            self._batch_llm_service(),
            batch_size=settings.SECURITY_AI_BATCH_SIZE,
            max_calls=settings.SECURITY_AI_MAX_CALLS,
        )
        analysis: dict[str, RuleAnalysis] = analyzer.analyze(escalate, repo_context)

        # --- Tier 1: CRITICAL rule-groups get a dedicated repair call → real diff ---
        critical_groups = [g for g in escalate if g.severity is Severity.CRITICAL]
        max_repair = max(0, int(settings.SECURITY_AI_MAX_REPAIR_CALLS))
        patches: dict[str, Any] = {}
        repair_calls = 0
        for g in critical_groups:
            if repair_calls >= max_repair:
                break
            rep = representative.get(g.rule_identity)
            if rep is None:
                continue
            try:
                patch = self._repair_adapter.repair(rep, repo_context)
                repair_calls += 1
            except Exception as exc:  # noqa: BLE001 - repair augments; never fatal
                logger.warning(
                    "CRITICAL repair unavailable for %s (%s); keeping batch snippet.",
                    g.rule_identity, exc,
                )
                repair_calls += 1
                patch = None
            if patch is not None and getattr(patch, "diff", "").strip():
                patches[g.rule_identity] = patch
                ra = analysis.get(g.rule_identity)
                if ra is not None:
                    analysis[g.rule_identity] = _replace(ra, diff=patch.diff, tier="critical")

        # --- Tier 3: MEDIUM/LOW get deterministic canned guidance (0 LLM calls) ---
        deterministic: dict[str, RuleAnalysis] = {}
        for g in rest:
            deterministic[g.rule_identity] = RuleAnalysis(
                explanation=g.sample_message,
                priority=self._priority_for_severity(g.severity),
                remediation=lookup_remediation(g.rule_identity, g.category),
                likely_false_positive=False,
                tier="deterministic",
            )

        logger.info(
            "IntelligenceStage(batch): %d finding(s) → %d rule-group(s); "
            "%d HIGH/CRITICAL to AI (%d dedicated CRITICAL repair diffs), "
            "%d MEDIUM/LOW deterministic",
            len(ordered), len(groups), len(escalate), len(patches), len(rest),
        )

        # Attach analysis (AI or deterministic) to each finding as its triage.
        merged = {**deterministic, **analysis}  # AI wins over canned when both exist
        processed: list[Normalized_Finding] = []
        for f in ordered:
            ra = merged.get(f.rule_identity)
            new_f = f
            if ra is not None:
                new_f = _replace(
                    f,
                    triage=AITriage(
                        explanation=ra.explanation,
                        priority=ra.priority,
                        suggested_fix=ra.remediation,
                        likely_false_positive=ra.likely_false_positive,
                    ),
                    likely_false_positive=ra.likely_false_positive,
                    status=FindingStatus.UNRESOLVED,
                    unresolved_reason="Advisory — see remediation guide.",
                )
            # Attach the real patch to the representative CRITICAL finding.
            patch = patches.get(f.rule_identity)
            if patch is not None and representative.get(f.rule_identity) is f:
                new_f = _replace(new_f, candidate_patch=patch)
            processed.append(new_f)

        # Dev-team guides: escalated (AI, ordered by severity) + deterministic tail.
        context.security_remediation_guide = [
            (g, analysis.get(g.rule_identity)) for g in escalate
        ]
        context.security_deterministic_guide = [
            (g, deterministic.get(g.rule_identity)) for g in rest
        ]

        return IntelligenceResult(fixed=(), remaining=tuple(processed))

    @staticmethod
    def _priority_for_severity(severity: Any) -> Any:
        from app.security.intelligence.batch_triage import _priority_for

        return _priority_for(severity)

    def _batch_llm_service(self):
        """Reuse the triage adapter's LLMService when available, else a default."""
        svc = getattr(self._triage_adapter, "llm_service", None)
        if svc is not None:
            return svc
        from app.services.llm_service import LLMService

        return LLMService()

    # ------------------------------------------------------------------ #
    # Ordered flow (design IntelligenceLayer.process)
    # ------------------------------------------------------------------ #

    def _process(
        self,
        raw_findings: list[Any],
        repo_context: Any,
        scope: ScanScope,
        context: WorkflowContext,
    ) -> IntelligenceResult:
        """Run normalize → dedup → correlate → enrich → score/order → baseline → triage → repair → verify."""
        # 1-4. Normalize → dedup → correlate → enrich → score/order (pure).
        ordered = self._prepare_findings(raw_findings, repo_context)
        # 4b. Baseline / delta filtering (Phase 1).
        ordered = self._apply_baseline(list(ordered), context)
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

        try:
            patch = self._repair_adapter.repair(finding, repo_context)
        except Exception as exc:  # noqa: BLE001 - AI augments, never a hard dep
            # LLM/AI repair outage must not sink the finding: keep it as an
            # unresolved (remaining) finding for the human reviewer.
            logger.warning(
                "AI repair unavailable for finding %s (%s); marking unresolved.",
                finding.finding_id,
                exc,
            )
            return replace(
                finding,
                status=FindingStatus.UNRESOLVED,
                unresolved_reason="AI repair unavailable (LLM error); finding retained for review.",
            )

        # Requirement 10.4 — no patch means the finding stays unresolved.
        if patch is None:
            return replace(
                finding,
                status=FindingStatus.UNRESOLVED,
                unresolved_reason=NO_PATCH_REASON,
            )

        finding = replace(finding, candidate_patch=patch)

        # Advisory mode (SECURITY_VERIFY_PATCHES=false): attach the AI patch as a
        # suggestion, skip the ~40s-per-finding scanner re-run. Finding stays
        # UNRESOLVED so a human reviewer applies it.
        from app.config.settings import settings

        if not settings.SECURITY_VERIFY_PATCHES:
            return replace(
                finding,
                status=FindingStatus.UNRESOLVED,
                unresolved_reason=UNVERIFIED_PATCH_REASON,
            )

        # Requirement 11 — deterministic re-verification (opt-in).
        outcome = self._verifier.verify(patch, baseline, scope)
        if outcome.accepted:
            return replace(finding, status=FindingStatus.FIXED, unresolved_reason=None)

        reason = INTRODUCED_REASON if outcome.introduced_findings else UNRESOLVED_REASON
        return replace(
            finding,
            status=FindingStatus.UNRESOLVED,
            unresolved_reason=reason,
        )
