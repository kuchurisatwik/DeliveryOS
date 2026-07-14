"""Security-pipeline composition — wire Layers 1→2→3→4 into the orchestrator.

This module registers the net-new security stages with the existing
:class:`~app.workflows.orchestrator.WorkflowOrchestrator` and sequences them in
the strict order the design mandates (Requirement 1.2)::

    Config resolution → Layer 2 Detection → Layer 3 Intelligence → Layer 4 Governance

It is *additive*: the existing engineering / test-generation flow in
``app/github/routes.py`` runs unchanged, and these security stages plug in after
the Layer-1 repository-intelligence stages have populated the shared
:class:`~app.workflows.context.WorkflowContext` (``changed_files`` and, when a task
was processed, ``retrieved_knowledge``). The Detection stage derives its
:class:`~app.security.models.ScanScope` from that context (falling back to
``changed_files`` when no ``Changed_Feature`` is present), so the security pipeline
works whether or not per-task context retrieval ran.

Key responsibilities implemented here:

* **Config-before-detection (Requirement 1.5)** — :class:`SecurityConfigResolutionStage`
  loads the per-repo ``Repo_Config`` from the workspace (conventional path
  :data:`DEFAULT_REPO_CONFIG_PATH`) and resolves it via
  :class:`~app.security.config.repo_config.ConfigResolver` *before* the Detection
  stage runs, storing the resolved config and any substitutions on the context.
* **Missing-input guard (Requirement 1.3)** — :func:`ensure_security_inputs` halts
  with a diagnostic error naming the missing ``Commit_SHA`` / ``Git_Diff`` input.
* **Governance (Requirement 12–14)** — :class:`GovernanceStage` evaluates the pure
  Quality Gate, computes the advisory Merge Confidence, and leaves report assembly
  to the existing :class:`~app.workflows.stages.GenerateDummyReportStage` (which
  renders the security sections from the context). It never triggers a merge
  (Requirement 14.5). Its only side-effecting call — fetching SonarQube metrics —
  is injectable and guarded so importing this module and running it in tests stays
  side-effect free.
"""

from __future__ import annotations

import os
from typing import Any, List, Mapping, Optional, Sequence

from app.security.config.repo_config import ConfigResolver
from app.security.detection.adapters import (
    BanditAdapter,
    CheckovAdapter,
    CodeQLAdapter,
    GitleaksAdapter,
    SemgrepAdapter,
    TrivyAdapter,
)
from app.security.detection.runner import DetectionStage, derive_scan_scope
from app.security.governance.merge_confidence import compute_merge_confidence
from app.security.governance.quality_gate import evaluate_quality_gate
from app.security.intelligence.repair import LLMRepairAdapter
from app.security.intelligence.stage import IntelligenceStage
from app.security.intelligence.triage import LLMTriageAdapter
from app.security.intelligence.verify import PatchedScanner
from app.security.models import (
    CandidatePatch,
    Finding,
    IntelligenceResult,
    MergeConfidenceInputs,
    QualityGateThresholds,
    ScanScope,
    SonarMetrics,
)
from app.security.protocols import SonarClient
from app.services.llm_service import LLMService
from app.workflows.context import WorkflowContext
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.results import WorkflowResult
from app.workflows.stages import Stage
from app.utils.logger import logger

#: Conventional location of the per-repository security config inside a checkout.
DEFAULT_REPO_CONFIG_PATH = os.path.join(".deliveryos", "security.json")

#: Neutral SonarQube metrics used when live metrics cannot be retrieved. Chosen so
#: the pipeline never crashes on a missing SonarQube integration; the Quality Gate
#: is advisory and the report records the outcome for the human reviewer.
_FALLBACK_MAINTAINABILITY = "A"


# ---------------------------------------------------------------------------
# Missing-input guard (Requirement 1.3)
# ---------------------------------------------------------------------------


class MissingPipelineInputError(ValueError):
    """Raised when a required pipeline input (Commit_SHA / Git_Diff) is missing."""


def _has_git_diff(context: WorkflowContext) -> bool:
    """Whether a usable Git_Diff is present on the context.

    The security pipeline accepts either the structured diff produced by
    :class:`~app.workflows.intelligence_stages.GitDiffCollectorStage` or the raw
    ``changed_files`` list produced by ``AnalyzeFilesStage`` — either is sufficient
    to derive a :class:`ScanScope`.
    """
    diff = context.structured_diff or {}
    has_structured = any(diff.get(k) for k in ("added", "modified", "deleted", "renamed"))
    return bool(has_structured or context.changed_files)


def ensure_security_inputs(context: WorkflowContext) -> None:
    """Halt with a diagnostic error naming any missing required input (Req 1.3).

    Raises:
        MissingPipelineInputError: naming ``Commit_SHA`` and/or ``Git_Diff`` when
            either required input is unavailable. Deeper layer-failure containment
            (still producing a report with ``failed_layer`` set) is handled by
            task 10.2; here we simply stop the security pipeline with a clear,
            named diagnostic.
    """
    missing: list[str] = []
    if not context.commit_sha:
        missing.append("Commit_SHA")
    if not _has_git_diff(context):
        missing.append("Git_Diff")
    if missing:
        raise MissingPipelineInputError(
            "Cannot start the security pipeline; missing required input(s): "
            + ", ".join(missing)
        )


# ---------------------------------------------------------------------------
# Layer-failure containment (Requirement 1.4)
# ---------------------------------------------------------------------------

#: Maps each security stage class to the human-readable layer name recorded in
#: ``Pull_Request_Report.failed_layer`` when that stage terminates with an
#: unrecoverable error (Requirement 1.4). Keyed by class name so the mapping stays
#: decoupled from imports and so tests can supply their own stage classes. The
#: Layer-1 "Repository Intelligence" name is included for completeness even though
#: those stages run in the base workflow, not inside :func:`build_security_stages`.
DEFAULT_SECURITY_LAYER_NAMES: Mapping[str, str] = {
    "SecurityConfigResolutionStage": "Configuration",
    "DetectionStage": "Detection",
    "IntelligenceStage": "Intelligence",
    "GovernanceStage": "Governance",
    # Layer 1 (base workflow) — mapped for completeness / reuse in tests.
    "RepositoryIntelligenceStage": "Repository Intelligence",
}


def resolve_layer_name(
    stage: Stage, layer_names: Optional[Mapping[str, str]] = None
) -> str:
    """Return the layer name for ``stage`` (pure, Requirement 1.4).

    Looks the stage's class name up in ``layer_names`` (defaulting to
    :data:`DEFAULT_SECURITY_LAYER_NAMES`); falls back to the stage's own ``name``
    when unmapped so an unexpected stage still yields a meaningful label.
    """
    names = layer_names if layer_names is not None else DEFAULT_SECURITY_LAYER_NAMES
    return names.get(type(stage).__name__, stage.name)


def determine_failed_layer(
    stages: Sequence[Stage],
    completed_count: int,
    layer_names: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Deterministically decide which layer failed (pure, Requirement 1.4).

    Given the ordered ``stages`` and the number of stages that completed
    successfully (``completed_count``), the failing stage is the one at index
    ``completed_count`` — because the orchestrator stops on the first failure, so
    every earlier stage completed and no later stage was invoked. Returns that
    stage's mapped layer name, or ``None`` when every stage completed
    (``completed_count >= len(stages)``).

    Keeping this decision pure and separable is what lets Property 1 (task 10.3)
    assert both that subsequent layers are never invoked *and* that ``failed_layer``
    names exactly the failing layer.
    """
    if completed_count < 0:
        completed_count = 0
    if completed_count >= len(stages):
        return None
    return resolve_layer_name(stages[completed_count], layer_names)


def run_security_pipeline_with_containment(
    orchestrator: WorkflowOrchestrator,
    context: WorkflowContext,
    stages: Sequence[Stage],
    *,
    layer_names: Optional[Mapping[str, str]] = None,
) -> WorkflowResult:
    """Run the security ``stages`` with layer-failure containment (Requirement 1.4).

    Delegates sequencing to the existing
    :meth:`WorkflowOrchestrator.run_pipeline`, which already stops on the first
    failure (so subsequent security layers are never invoked). On failure this
    wrapper records the failing layer's name on ``context.failed_layer`` — derived
    purely via :func:`determine_failed_layer` from the count of stages the
    orchestrator reported as completed — so the downstream report assembly sets
    ``Pull_Request_Report.failed_layer`` and a diagnostic report is still produced.

    Global orchestrator semantics are unchanged; containment is layered on top for
    the security stage sequence only, leaving the existing test-generation flow
    unaffected.
    """
    stage_list = list(stages)
    result = orchestrator.run_pipeline(context, stage_list)
    if result.status == "FAILED":
        failed_layer = determine_failed_layer(
            stage_list, len(result.completed_stages), layer_names
        )
        context.failed_layer = failed_layer
        logger.error(
            "Security pipeline halted: '%s' layer failed; a diagnostic report "
            "with failed_layer set will still be produced (Req 1.4).",
            failed_layer,
        )
    return result


# ---------------------------------------------------------------------------
# Layer 1.5 — Config resolution before Detection (Requirement 1.5, 15)
# ---------------------------------------------------------------------------


class SecurityConfigResolutionStage(Stage):
    """Resolve ``Repo_Config`` before Detection runs (Requirements 1.5, 15).

    Loads the per-repository config file from the checked-out workspace (at
    :data:`DEFAULT_REPO_CONFIG_PATH` by default) when present, otherwise resolves
    ``None`` (all documented defaults). The resulting immutable
    :class:`~app.security.models.ResolvedConfig` is stored on
    ``context.resolved_config`` and the substitution records on
    ``context.config_substitutions`` for the Governance/report layers to consume.
    """

    def __init__(self, config_rel_path: str = DEFAULT_REPO_CONFIG_PATH) -> None:
        self._config_rel_path = config_rel_path

    def execute(self, context: WorkflowContext) -> None:
        raw = self._load_raw_config(context)
        resolved, substitutions = ConfigResolver.resolve(raw)
        context.resolved_config = resolved
        context.config_substitutions = list(substitutions)
        logger.info(
            "SecurityConfigResolutionStage: resolved Repo_Config "
            "(%s file, %d substitution(s))",
            "with" if raw is not None else "no",
            len(substitutions),
        )

    def _load_raw_config(self, context: WorkflowContext) -> Optional[str]:
        """Return the raw config file contents from the workspace, or ``None``."""
        workspace = context.workspace
        if not workspace:
            return None
        path = os.path.join(workspace, self._config_rel_path)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:  # pragma: no cover - defensive I/O guard
            logger.warning("Failed to read Repo_Config at %s: %s", path, exc)
            return None


# ---------------------------------------------------------------------------
# Layer 3 verification boundary — the patched-scan callable
# ---------------------------------------------------------------------------


def make_patched_scanner(workspace: Optional[str]) -> PatchedScanner:
    """Build the :data:`PatchedScanner` used by the Layer 3 :class:`Verifier`.

    Returns a callable that re-runs the six deterministic Layer 2 scanners over the
    supplied scope (Requirement 11.1) and returns their aggregated raw findings.
    The scanners are constructed once, scoped to the cloned ``workspace``, and the
    call reuses :meth:`DetectionStage.run_on_scope` so verification benefits from
    the exact same parallel execution and per-scanner failure isolation as Layer 2.
    """
    adapters = [
        BanditAdapter(cwd=workspace),
        SemgrepAdapter(cwd=workspace),
        CodeQLAdapter(cwd=workspace),
        GitleaksAdapter(cwd=workspace),
        CheckovAdapter(cwd=workspace),
        TrivyAdapter(cwd=workspace),
    ]
    detection = DetectionStage(adapters=adapters)

    def scan_patched(patch: CandidatePatch, scope: ScanScope) -> Sequence[Finding]:
        # NOTE: patch application to the working tree is the caller's concern; here
        # we re-run the scanners against the (patched) scope and return findings.
        return detection.run_on_scope(scope).findings

    return scan_patched


# ---------------------------------------------------------------------------
# Layer 4 — Governance stage (Requirements 12, 13; report rendered downstream)
# ---------------------------------------------------------------------------


class GovernanceStage(Stage):
    """Evaluate the Quality Gate and compute advisory Merge Confidence (Req 12–13).

    Stores :class:`~app.security.models.Quality_Gate` on ``context.quality_gate``
    and :class:`~app.security.models.Merge_Confidence` on
    ``context.security_merge_confidence``. The existing
    :class:`~app.workflows.stages.GenerateDummyReportStage` reads these (plus the
    Layer 2/3 results and config substitutions) to assemble and render the
    :class:`~app.security.models.Pull_Request_Report` (Requirement 14). This stage
    never triggers a merge (Requirement 14.5).

    The only side effect — fetching SonarQube metrics — is delegated to an injected
    :class:`~app.security.protocols.SonarClient`. When none is injected a real
    :class:`~app.security.governance.sonar_client.HttpSonarClient` is built lazily
    *only if* SonarQube is configured; otherwise (and on any fetch error) neutral
    fallback metrics are used so the stage stays import- and test-safe.
    """

    def __init__(self, sonar_client: Optional[SonarClient] = None) -> None:
        self._sonar_client = sonar_client

    def execute(self, context: WorkflowContext) -> None:
        thresholds = self._resolve_thresholds(context)
        result: IntelligenceResult = context.intelligence_result or IntelligenceResult()

        # The Quality Gate evaluates the *current* security posture: the findings
        # that remain unfixed after Layer 3.
        remaining = list(result.remaining)
        metrics = self._fetch_metrics(context)

        quality_gate = evaluate_quality_gate(metrics, remaining, thresholds)
        context.quality_gate = quality_gate

        merge_confidence = compute_merge_confidence(
            MergeConfidenceInputs(
                testing_confidence=self._testing_confidence(context),
                security_confidence=self._security_confidence(result),
                coverage_percent=metrics.coverage_percent,
                remaining_findings=len(remaining),
                quality_gate_status=quality_gate.status,
            )
        )
        context.security_merge_confidence = merge_confidence

        logger.info(
            "GovernanceStage: quality gate %s, merge confidence %.2f (advisory)",
            quality_gate.status.value,
            merge_confidence.score,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_thresholds(context: WorkflowContext) -> QualityGateThresholds:
        """Use the resolved Repo_Config thresholds, or documented defaults."""
        resolved = getattr(context, "resolved_config", None)
        thresholds = getattr(resolved, "thresholds", None)
        return thresholds if thresholds is not None else QualityGateThresholds()

    def _fetch_metrics(self, context: WorkflowContext) -> SonarMetrics:
        """Fetch SonarQube metrics, guarded; fall back to neutral metrics on failure."""
        client = self._sonar_client or self._maybe_build_sonar_client()
        if client is not None:
            try:
                return client.fetch_metrics(context.commit_sha)
            except Exception as exc:  # noqa: BLE001 - Sonar is advisory; never abort
                logger.warning("SonarQube metrics unavailable, using fallback: %s", exc)
        return self._fallback_metrics(context)

    @staticmethod
    def _maybe_build_sonar_client() -> Optional[SonarClient]:
        """Construct an HttpSonarClient only when SonarQube is configured."""
        from app.config.settings import settings

        if not settings.SONARQUBE_PROJECT_KEY:
            return None
        # Imported lazily so importing this module never requires httpx/network.
        from app.security.governance.sonar_client import HttpSonarClient

        return HttpSonarClient()

    @staticmethod
    def _fallback_metrics(context: WorkflowContext) -> SonarMetrics:
        """Neutral metrics derived from local validation coverage when available."""
        coverage = 0.0
        validation_report = getattr(context, "validation_report", None)
        coverage_report = getattr(validation_report, "coverage_report", None)
        pct = getattr(coverage_report, "coverage_percentage", None)
        if pct is not None:
            try:
                coverage = float(pct)
            except (TypeError, ValueError):
                coverage = 0.0
        return SonarMetrics(
            coverage_percent=coverage,
            code_smells=0,
            technical_debt_minutes=0,
            security_hotspots=0,
            maintainability_rating=_FALLBACK_MAINTAINABILITY,
        )

    @staticmethod
    def _testing_confidence(context: WorkflowContext) -> float:
        """Map the existing 0–100 merge_confidence onto a 0–1 testing confidence."""
        try:
            return max(0.0, min(1.0, float(context.merge_confidence) / 100.0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _security_confidence(result: IntelligenceResult) -> float:
        """Fraction of findings resolved by Layer 3 (1.0 when there are none)."""
        total = len(result.fixed) + len(result.remaining)
        if total == 0:
            return 1.0
        return len(result.fixed) / total


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def build_security_stages(
    llm_service: LLMService,
    *,
    sonar_client: Optional[SonarClient] = None,
    detection_stage: Optional[Stage] = None,
    intelligence_stage: Optional[Stage] = None,
    governance_stage: Optional[Stage] = None,
    config_stage: Optional[Stage] = None,
    workspace: Optional[str] = None,
) -> List[Stage]:
    """Build the ordered security stage list (Layer 1.5 → 2 → 3 → 4).

    Production wiring constructs the real adapters:

    * :class:`DetectionStage` with its default six scanner adapters (Layer 2);
    * :class:`IntelligenceStage` with :class:`LLMTriageAdapter` /
      :class:`LLMRepairAdapter` (both reusing ``llm_service``) and a patched-scan
      callable from :func:`make_patched_scanner` (Layer 3);
    * :class:`GovernanceStage` (Layer 4).

    Every stage is overridable so tests can inject in-memory fakes and run the whole
    pipeline without subprocesses, LLM calls, or network. The stages are returned in
    strict execution order with config resolution first (Requirement 1.5).
    """
    config = config_stage or SecurityConfigResolutionStage()
    detection = detection_stage or DetectionStage()
    intelligence = intelligence_stage or IntelligenceStage(
        triage_adapter=LLMTriageAdapter(llm_service),
        repair_adapter=LLMRepairAdapter(llm_service),
        scan_patched=make_patched_scanner(workspace),
    )
    governance = governance_stage or GovernanceStage(sonar_client=sonar_client)
    return [config, detection, intelligence, governance]
