"""End-to-end integration test for the DeliveryOS Security Pipeline.

Deterministic example/integration test (NOT property-based). It drives a single
representative run through the real security stage sequence — assembled by
:func:`~app.security.pipeline.build_security_stages` and executed by the real
:class:`~app.workflows.orchestrator.WorkflowOrchestrator` (via
:func:`~app.security.pipeline.run_security_pipeline_with_containment`) — with
**fakes for every impure boundary** so nothing touches a subprocess, an LLM, a
SonarQube server, or the network:

* **Scanner adapters** — in-memory fakes returning canned :class:`Finding`s, plus
  one deliberately-failing scanner so the run produces an *incomplete* coverage
  entry (Requirement 14.2/14.4).
* **AI triage** — a fake :class:`AITriageAdapter` that labels one finding a likely
  false positive (retained, never repaired) and the rest as real.
* **AI repair** — a fake :class:`AIRepairAdapter` that proposes a patch for one
  finding and declines the other (→ one ``fixed``, one ``remaining``).
* **Patched scan (verification)** — a fake
  :data:`~app.security.intelligence.verify.PatchedScanner` that reports the
  patched finding as resolved with nothing new introduced (→ the patch is
  accepted and the finding marked ``fixed``).
* **SonarQube metrics** — a fake :class:`~app.security.protocols.SonarClient`
  injected into the real :class:`~app.security.pipeline.GovernanceStage`.
* **GitHub** — a mocked :class:`~app.services.github_service.GitHubService`; the
  PR is opened via :meth:`open_pull_request` and **no merge is ever invoked**
  (reinforces Property 20).

Assertions cover:

* The four security layers run in strict order (config → detection → intelligence
  → governance) through the orchestrator, populating the context with
  ``detection_result``, ``intelligence_result``, ``quality_gate`` and
  ``security_merge_confidence`` (Requirements 1.1, 1.2).
* A complete :class:`~app.security.models.Pull_Request_Report` is assembled and
  attached (via the real :class:`~app.workflows.stages.GenerateDummyReportStage`
  security section, which also writes ``AI_REPORT.md``) covering fixed/remaining
  findings, merge confidence, the quality gate, and the incomplete scanner
  (Requirements 14.1, 14.2).
* No merge call is ever made: the PR is opened via the mocked
  ``GitHubService.open_pull_request`` and nothing merges (Property 20).

Requirements: 1.1, 1.2, 14.1
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence
from unittest.mock import MagicMock

import pytest

from app.schemas.repository import (
    ChangedFeature,
    RelatedSymbol,
    RepositoryContext,
    RetrievedSymbol,
    SymbolReachability,
)
from app.security.detection.adapters.base import ScannerError
from app.security.detection.runner import DetectionStage
from app.security.intelligence.stage import IntelligenceStage
from app.security.models import (
    AITriage,
    CandidatePatch,
    Finding,
    GateStatus,
    Location,
    Merge_Confidence,
    Normalized_Finding,
    Priority,
    Pull_Request_Report,
    ScanScope,
    Severity,
    SonarMetrics,
)
from app.security.pipeline import (
    GovernanceStage,
    build_security_stages,
    run_security_pipeline_with_containment,
)
from app.services.github_service import GitHubService
from app.workflows.context import WorkflowContext
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.stages import CreatePullRequestStage, GenerateDummyReportStage


# --------------------------------------------------------------------------- #
# Fakes for the impure boundaries
# --------------------------------------------------------------------------- #


class FakeScanner:
    """In-memory :class:`ScannerAdapter` returning canned findings."""

    def __init__(self, name: str, findings: Sequence[Finding]) -> None:
        self.name = name
        self._findings = list(findings)
        self.received_scope: Optional[ScanScope] = None

    def scan(self, scope: ScanScope) -> List[Finding]:
        self.received_scope = scope
        return list(self._findings)


class FailingScanner:
    """A scanner that always fails, producing an ``incomplete`` coverage entry."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self._reason = reason

    def scan(self, scope: ScanScope) -> List[Finding]:
        raise ScannerError(self.name, self._reason)


class FakeTriageAdapter:
    """Labels findings whose rule identity is in ``false_positives`` as likely FP."""

    def __init__(self, false_positives: Sequence[str] = ()) -> None:
        self._false_positives = set(false_positives)

    def triage(self, f: Normalized_Finding, ctx) -> AITriage:
        is_fp = f.rule_identity in self._false_positives
        return AITriage(
            explanation=f"Triage for {f.rule_identity}",
            priority=Priority.P1,
            suggested_fix="Apply a secure coding pattern.",
            likely_false_positive=is_fp,
        )


class FakeRepairAdapter:
    """Proposes a patch only for rule identities in ``repairable``."""

    def __init__(self, repairable: Sequence[str] = ()) -> None:
        self._repairable = set(repairable)

    def repair(self, f: Normalized_Finding, ctx) -> Optional[CandidatePatch]:
        if f.rule_identity in self._repairable:
            return CandidatePatch(
                target_finding_id=f.finding_id,
                diff=f"--- patch for {f.finding_id} ---",
            )
        return None


class FakePatchedScanner:
    """A verification scan that reports the patched target as fully resolved.

    Returns an empty finding set for every re-scan, so the targeted finding is
    absent post-patch (resolved) and no finding absent from the baseline is
    introduced — the patch is accepted and the finding marked ``fixed``.
    """

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, patch: CandidatePatch, scope: ScanScope) -> List[Finding]:
        self.calls += 1
        return []


class FakeSonarClient:
    """Injected :class:`SonarClient` returning fixed, healthy metrics."""

    def __init__(self, metrics: SonarMetrics) -> None:
        self._metrics = metrics
        self.calls = 0

    def fetch_metrics(self, commit_sha: str) -> SonarMetrics:
        self.calls += 1
        return self._metrics


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


def _finding(scanner: str, rule_id: str, path: str, severity: Severity) -> Finding:
    return Finding(
        scanner=scanner,
        rule_id=rule_id,
        location=Location(path=path, start_line=10, end_line=12, symbol="handler"),
        severity=severity,
        message=f"{rule_id} detected in {path}",
        raw={"scanner": scanner, "rule": rule_id},
    )


def _repo_context() -> RepositoryContext:
    """A representative Layer 1 context so enrichment has real signals to use."""
    return RepositoryContext(
        target_symbols=[
            RetrievedSymbol(
                name="handler",
                type="function",
                file_path="app/routes/api.py",
                body="def handler(): ...",
            )
        ],
        related_symbols=[
            RelatedSymbol(
                name="service_call",
                type="function",
                file_path="app/service.py",
                relation="callee",
            )
        ],
        reachability=[
            SymbolReachability(
                symbol_name="handler",
                file_path="app/routes/api.py",
                caller_count=3,
                has_callers=True,
                reachable_from_entrypoint=True,
            )
        ],
        changed_feature=ChangedFeature(
            files=["app/routes/api.py", "app/service.py"],
            related_symbols=[
                RelatedSymbol(
                    name="service_call",
                    type="function",
                    file_path="app/service.py",
                    relation="callee",
                )
            ],
        ),
    )


def _context(tmp_path) -> WorkflowContext:
    workspace = str(tmp_path)
    return WorkflowContext(
        repository="octo/example",
        repo_name="example",
        clone_url="https://github.com/octo/example.git",
        branch="main",
        commit_sha="abc1234def5678",
        workspace=workspace,
        ai_branch_name="ai-sde/review-abc1234-20240101000000",
        changed_files=["app/routes/api.py", "app/service.py"],
        retrieved_knowledge=_repo_context(),
    )


def _build_stages(sonar_metrics: SonarMetrics):
    """Compose the four security stages with fakes for every impure boundary."""
    # Two findings that surface real work, one FP that stays for human review.
    fixable = _finding("bandit", "B101-assert-used", "app/routes/api.py", Severity.HIGH)
    stubborn = _finding("semgrep", "sqli-risk", "app/service.py", Severity.HIGH)
    false_pos = _finding("gitleaks", "generic-api-key", "app/service.py", Severity.MEDIUM)

    detection_stage = DetectionStage(
        adapters=[
            FakeScanner("bandit", [fixable]),
            FakeScanner("semgrep", [stubborn]),
            FakeScanner("gitleaks", [false_pos]),
            FailingScanner("trivy", "tool not installed"),
        ]
    )

    intelligence_stage = IntelligenceStage(
        triage_adapter=FakeTriageAdapter(false_positives={"generic-api-key"}),
        repair_adapter=FakeRepairAdapter(repairable={"b101-assert-used"}),
        scan_patched=FakePatchedScanner(),
    )

    sonar_client = FakeSonarClient(sonar_metrics)
    governance_stage = GovernanceStage(sonar_client=sonar_client)

    stages = build_security_stages(
        MagicMock(),  # llm_service unused: all AI boundaries are injected fakes
        detection_stage=detection_stage,
        intelligence_stage=intelligence_stage,
        governance_stage=governance_stage,
    )
    return stages, sonar_client


# --------------------------------------------------------------------------- #
# The end-to-end test
# --------------------------------------------------------------------------- #


def test_end_to_end_security_pipeline_produces_report_and_never_merges(
    tmp_path, monkeypatch
):
    """Full Layer 1→4 run through the orchestrator; report attached, no merge.

    Exercises the closed scanner-verified repair loop with in-memory fakes, so
    ``SECURITY_VERIFY_PATCHES`` is explicitly enabled for this test. The
    runtime default is advisory mode (``False``).
    """
    from app.config.settings import settings as _settings

    monkeypatch.setattr(_settings, "SECURITY_VERIFY_PATCHES", True)
    # This test exercises the per-finding triage→repair→verify loop; batch mode
    # is the runtime default, so select per-finding explicitly here.
    monkeypatch.setattr(_settings, "SECURITY_TRIAGE_MODE", "per_finding")

    metrics = SonarMetrics(
        coverage_percent=95.0,
        code_smells=1,
        technical_debt_minutes=10,
        security_hotspots=0,
        maintainability_rating="A",
    )
    stages, sonar_client = _build_stages(metrics)
    context = _context(tmp_path)

    # --- Run the four security layers through the real orchestrator (Req 1.2) ---
    orchestrator = WorkflowOrchestrator()
    result = run_security_pipeline_with_containment(orchestrator, context, stages)

    assert result.status == "SUCCESS"
    assert context.failed_layer is None
    # Strict layer order: config → detection → intelligence → governance (Req 1.2).
    assert result.completed_stages == [
        "SecurityConfigResolutionStage",
        "DetectionStage",
        "IntelligenceStage",
        "GovernanceStage",
        "RecordScanStateStage",
    ]

    # --- The context is populated by every layer (Req 1.1) ---
    assert context.resolved_config is not None
    assert context.detection_result is not None
    assert context.intelligence_result is not None
    assert context.quality_gate is not None
    assert context.security_merge_confidence is not None
    assert sonar_client.calls == 1  # governance fetched metrics via the fake

    # Detection: three findings aggregated, one scanner incomplete (Req 3, 14.4).
    detection = context.detection_result
    assert len(detection.findings) == 3
    incomplete = [c for c in detection.coverage if c.status == "incomplete"]
    assert [c.scanner for c in incomplete] == ["trivy"]

    # Intelligence: one fixed (patched + verified), two remaining (FP + no-patch).
    intel = context.intelligence_result
    assert len(intel.fixed) == 1
    assert len(intel.remaining) == 2
    assert intel.fixed[0].rule_identity == "b101-assert-used"

    # Merge confidence is advisory (Req 13.3).
    merge_confidence: Merge_Confidence = context.security_merge_confidence
    assert merge_confidence.advisory is True
    assert 0.0 <= merge_confidence.score <= 100.0

    # --- Report assembly + attachment via the real report stage (Req 14) ---
    GenerateDummyReportStage().execute(context)

    report: Pull_Request_Report = context.security_report
    assert isinstance(report, Pull_Request_Report)
    assert report.commit_sha == "abc1234def5678"
    # Report partitions match the intelligence result (Req 14.2).
    assert len(report.fixed_findings) == 1
    assert len(report.remaining_findings) == 2
    # Merge confidence + quality gate carried into the report (Req 14.2/14.3).
    assert report.merge_confidence is context.security_merge_confidence
    assert report.quality_gate is context.quality_gate
    assert report.quality_gate.status in (GateStatus.PASSED, GateStatus.FAILED)
    # The incomplete scanner is surfaced in the report (Req 14.4).
    assert [c.scanner for c in report.incomplete_scanners] == ["trivy"]

    # The Markdown report file was written to the workspace and includes the
    # rendered security section.
    report_path = os.path.join(context.workspace, "AI_REPORT.md")
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as fh:
        report_md = fh.read()
    assert "Security Pipeline Report" in report_md
    assert "Merge Confidence (advisory)" in report_md

    # --- The PR is opened via the mocked GitHubService; nothing merges (Prop 20) ---
    github_service = MagicMock(spec=GitHubService)
    github_service.open_pull_request.return_value = (
        "https://github.com/octo/example/pull/1"
    )

    CreatePullRequestStage(github_service).execute(context)

    github_service.open_pull_request.assert_called_once()
    assert context.pr_url == "https://github.com/octo/example/pull/1"
    # The real GitHubService exposes no merge surface, and none was invoked.
    assert not hasattr(GitHubService, "merge_pull_request")
    merge_calls = [c for c in github_service.mock_calls if "merge" in str(c).lower()]
    assert merge_calls == []
    called_methods = {c[0] for c in github_service.method_calls}
    assert called_methods == {"open_pull_request"}
