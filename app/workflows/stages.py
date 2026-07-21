import abc
import os
import datetime
from app.workflows.context import WorkflowContext
from app.services.git_service import GitService
from app.services.github_service import GitHubService

class Stage(abc.ABC):
    """Abstract base class for a workflow stage."""
    
    @abc.abstractmethod
    def execute(self, context: WorkflowContext) -> None:
        """Executes the stage logic.
        
        Args:
            context: The shared workflow context.
        """
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__

class CloneRepositoryStage(Stage):
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        context.workspace = self.git_service.clone_repository(context.clone_url, context.repo_name)

class AnalyzeFilesStage(Stage):
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set. Cannot analyze files.")
        context.changed_files = self.git_service.get_changed_files(context.workspace, context.commit_sha)

class CreateBranchStage(Stage):
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set. Cannot create branch.")
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        context.ai_branch_name = f"ai-sde/review-{context.commit_sha[:7]}-{timestamp_str}"
        self.git_service.create_branch(context.workspace, context.ai_branch_name, context.commit_sha)

class GenerateDummyReportStage(Stage):
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace or not context.ai_branch_name:
            raise ValueError("Workspace or ai_branch_name is not set.")
        report_path = os.path.join(context.workspace, "AI_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# AI Software Delivery Engineer: Architecture Review\n\n")
            f.write(f"**Repository:** {context.repository}\n")
            f.write(f"**Commit SHA:** {context.commit_sha}\n")
            f.write(f"**Branch:** {context.ai_branch_name}\n")
            f.write(f"**Timestamp:** {datetime.datetime.now().isoformat()}Z\n\n")
            
            if context.change_summary:
                f.write(f"## Executive Summary\n{context.change_summary.summary}\n\n")
                f.write(f"- **Feature Type:** {context.change_summary.feature_type}\n")
                f.write(f"- **Risk Level:** {context.change_summary.risk_level}\n")
                f.write(f"- **Confidence:** {context.change_summary.confidence}\n")
                f.write(f"- **Breaking Change:** {context.change_summary.breaking_change}\n\n")
                
                f.write(f"## Architectural Impact\n{context.change_summary.architecture_impact}\n\n")
                f.write(f"## Reasoning\n{context.change_summary.reasoning}\n\n")
                
                f.write("## Affected Components\n")
                f.write(f"- **Services:** {', '.join(context.change_summary.affected_services)}\n")
                f.write(f"- **Modules:** {', '.join(context.change_summary.affected_modules)}\n")
                f.write(f"- **Routes:** {', '.join(context.change_summary.affected_routes)}\n")
                f.write(f"- **Database Tables:** {', '.join(context.change_summary.affected_database_tables)}\n")
            else:
                f.write("No AI analysis was generated.\n")
                
            if getattr(context, 'test_plan', None):
                f.write("\n---\n\n## 🧪 Test Plan Summary\n\n")
                f.write(f"**Overall Risk:** {context.test_plan.overall_risk}\n")
                f.write(f"**Confidence:** {context.test_plan.confidence}\n")
                f.write(f"**Priority:** {context.test_plan.priority}\n\n")
                
                f.write("### Recommended Test Levels\n")
                f.write(f"- Unit: {'Yes' if context.test_plan.recommended_test_levels.unit else 'No'}\n")
                f.write(f"- Integration: {'Yes' if context.test_plan.recommended_test_levels.integration else 'No'}\n")
                f.write(f"- API: {'Yes' if context.test_plan.recommended_test_levels.api else 'No'}\n")
                f.write(f"- E2E: {'Yes' if context.test_plan.recommended_test_levels.e2e else 'No'}\n\n")
                
                # Combine all scenarios to print
                all_scenarios = (
                    context.test_plan.unit_test_scenarios +
                    context.test_plan.integration_test_scenarios +
                    context.test_plan.api_test_scenarios +
                    context.test_plan.negative_test_scenarios +
                    context.test_plan.boundary_test_scenarios +
                    context.test_plan.security_test_scenarios +
                    context.test_plan.performance_test_scenarios
                )
                
                f.write(f"### Proposed Scenarios ({len(all_scenarios)})\n")
                for s in all_scenarios:
                    f.write(f"- **{s.scenario_name}** ({s.category}): {s.expected_behaviour}\n")
                    
            if getattr(context, 'planning_warnings', None):
                f.write("\n### ⚠️ Planning Warnings\n")
                for w in context.planning_warnings:
                    f.write(f"- {w}\n")
                    
            if getattr(context, 'generated_tests', None):
                f.write(f"\n---\n\n## 🛠️ Generated Test Code ({context.generated_files_count} files)\n\n")
                f.write(f"**Framework:** {context.generated_test_framework}\n")
                f.write(f"**Confidence:** {context.generation_confidence}\n\n")
                
                f.write("### New Files Written to Workspace:\n")
                for gen_file in context.generated_tests.generated_files:
                    f.write(f"- `{gen_file.path}`\n")
                    
                if context.generated_tests.new_fixtures:
                    f.write("\n### New Fixtures:\n")
                    for fix in context.generated_tests.new_fixtures:
                        f.write(f"- {fix}\n")
                        
                if context.generated_tests.mock_objects:
                    f.write("\n### Mock Objects Used:\n")
                    for mock in context.generated_tests.mock_objects:
                        f.write(f"- {mock}\n")
                        
                if context.generation_warnings:
                    f.write("\n### ⚠️ Generation Warnings\n")
                    for w in context.generation_warnings:
                        f.write(f"- {w}\n")
                        
            # Phase 6: Validation & Improvement Engine Report
            if getattr(context, 'iteration_count', 0) > 1 or getattr(context, 'validation_report', None):
                f.write(f"\n---\n\n## 🔄 Validation & Improvement Engine\n\n")
                f.write(f"**Improvement Iterations Required:** {context.iteration_count - 1}\n")
                
                if getattr(context, 'merge_confidence', None) is not None:
                    f.write(f"**Merge Confidence:** {context.merge_confidence}/100\n\n")
                
                val = getattr(context, 'validation_report', None)
                if val:
                    f.write("### Deterministic Validation Results\n")
                    f.write(f"- **Syntax:** {'✅ Passed' if val.syntax_status.passed else '❌ Failed'}\n")
                    f.write(f"- **Imports:** {'✅ Passed' if val.import_status.passed else '❌ Failed'}\n")
                    f.write(f"- **Dependencies:** {'✅ Passed' if val.dependency_status.passed else '❌ Failed'}\n")
                    f.write(f"- **Lint (Ruff):** {'✅ Passed' if val.lint_status.passed else '❌ Failed'}\n")
                    f.write(f"- **Types (Mypy):** {'✅ Passed' if val.type_status.passed else '❌ Failed'}\n")
                    
                    if val.execution_report:
                        f.write(f"\n### Test Execution\n")
                        f.write(f"**Pass Rate:** {val.execution_report.passed} passed, {val.execution_report.failed} failed\n")
                        
                    if val.coverage_report:
                        f.write(f"**Coverage:** {val.coverage_report.coverage_percentage:.2f}%\n")
                        
                if getattr(context, 'review_report', None):
                    f.write(f"\n### AI Review\n")
                    f.write(f"**AI Code Review Approved:** {'Yes' if context.review_report.approved else 'No'}\n")

            # Layer 4 Governance: append the security-pipeline sections when the
            # security outputs are present on the context (backward-compatible —
            # the existing report content above is untouched when they are absent).
            security_section = _render_security_report_section(context)
            if security_section:
                f.write(security_section)

def _render_security_report_section(context: WorkflowContext) -> str:
    """Assemble and render the Layer 4 security sections, or "" when unavailable.

    Pulls the security-pipeline outputs from the shared context
    (``intelligence_result``, ``detection_result`` coverage, ``quality_gate``,
    ``security_merge_confidence``, ``config_substitutions``), assembles a pure
    :class:`~app.security.models.Pull_Request_Report` via
    :func:`app.security.governance.report.assemble_pull_request_report`, caches it
    on ``context.security_report``, and renders it to Markdown (Requirement 14).
    Never triggers a merge (Requirement 14.5). Returns an empty string when the
    required security outputs are not present, so non-security runs are unaffected.
    """
    intelligence_result = getattr(context, "intelligence_result", None)
    quality_gate = getattr(context, "quality_gate", None)
    merge_confidence = getattr(context, "security_merge_confidence", None)
    failed_layer = getattr(context, "failed_layer", None)

    # Emit a security section when the core Layer 3/4 outputs are present, OR when
    # a security layer failed — in which case a diagnostic report naming the
    # failing layer must still be produced (Requirement 1.4).
    have_core_outputs = (
        intelligence_result is not None
        and quality_gate is not None
        and merge_confidence is not None
    )
    if not have_core_outputs and failed_layer is None:
        return ""

    # Imported lazily so the base workflow has no hard dependency on the
    # security package when it is not in use.
    from app.security.governance.report import (
        assemble_pull_request_report,
        render_security_sections,
    )
    from app.security.models import (
        GateStatus,
        IntelligenceResult,
        Merge_Confidence,
        MergeConfidenceInputs,
        Quality_Gate,
    )

    # On an unrecoverable layer failure the later layers never ran, so their
    # outputs may be missing. Fill neutral defaults so a report is still produced;
    # the gate is defaulted to FAILED so an incomplete run never reports a passing
    # gate (Requirement 1.4).
    if intelligence_result is None:
        intelligence_result = IntelligenceResult()
    if quality_gate is None:
        quality_gate = Quality_Gate(status=GateStatus.FAILED)
    if merge_confidence is None:
        merge_confidence = Merge_Confidence(
            score=0.0,
            inputs=MergeConfidenceInputs(
                testing_confidence=0.0,
                security_confidence=0.0,
                coverage_percent=0.0,
                remaining_findings=len(intelligence_result.remaining),
                quality_gate_status=quality_gate.status,
            ),
        )

    detection_result = getattr(context, "detection_result", None)
    coverage = tuple(getattr(detection_result, "coverage", ()) or ())
    raw_findings = tuple(getattr(detection_result, "findings", ()) or ())
    substitutions = tuple(getattr(context, "config_substitutions", None) or ())

    # Number of files the scanners were scoped to (best-effort, for the report).
    scanned_file_count = None
    repo_ctx = getattr(context, "retrieved_knowledge", None)
    changed_feature = getattr(repo_ctx, "changed_feature", None) if repo_ctx else None
    if changed_feature is not None and getattr(changed_feature, "files", None):
        scanned_file_count = len(changed_feature.files)
    elif getattr(context, "changed_files", None):
        scanned_file_count = len(context.changed_files)

    # Scope mode for the report label — the ACTUAL resolved scope captured at
    # detection time (so 'auto' onboarding shows 'full', and it isn't mislabeled
    # after the repo is marked scanned later in the run).
    scan_scope_mode = getattr(context, "security_scan_scope_mode", None)
    if scan_scope_mode is None:
        try:
            from app.security.detection.runner import resolve_scope_mode

            scan_scope_mode = resolve_scope_mode(context)
        except Exception:  # noqa: BLE001 - never break report rendering
            scan_scope_mode = "commit"

    security_summary = None
    if failed_layer:
        security_summary = (
            f"Security evaluation incomplete: the {failed_layer} layer terminated "
            "with an unrecoverable error. Results are partial and no passing gate "
            "is implied; a human reviewer must account for the missing analysis."
        )

    report = assemble_pull_request_report(
        commit_sha=context.commit_sha,
        intelligence_result=intelligence_result,
        merge_confidence=merge_confidence,
        quality_gate=quality_gate,
        coverage=coverage,
        config_substitutions=substitutions,
        security_summary=security_summary,
        failed_layer=failed_layer,
    )
    context.security_report = report
    return render_security_sections(
        report,
        coverage=coverage,
        raw_findings=raw_findings,
        scanned_file_count=scanned_file_count,
        scan_scope_mode=scan_scope_mode,
        remediation_guide=getattr(context, "security_remediation_guide", None) or (),
        deterministic_guide=getattr(context, "security_deterministic_guide", None) or (),
        repo_slug=getattr(context, "repository", None),
        branch=getattr(context, "branch", None),
    )

class CommitStage(Stage):
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set.")
        self.git_service.commit_changes(context.workspace, f"Add AI_REPORT for {context.commit_sha[:7]}")
class PushBranchStage(Stage):
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace or not context.ai_branch_name:
            raise ValueError("Workspace or ai_branch_name is not set.")
        self.git_service.push_branch(context.workspace, context.ai_branch_name)
class CreatePullRequestStage(Stage):
    def __init__(self, github_service: GitHubService):
        self.github_service = github_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.ai_branch_name:
            raise ValueError("ai_branch_name is not set.")
        pr_title = f"AI-SDE: Automated Code Review and Testing for {context.commit_sha[:7]}"
        pr_body = "This PR contains the automated analysis and tests generated by the AI Software Delivery Engineer."
        context.pr_url = self.github_service.open_pull_request(
            repo_full_name=context.repository,
            head_branch=context.ai_branch_name,
            base_branch=context.branch,
            title=pr_title,
            body=pr_body
        )
