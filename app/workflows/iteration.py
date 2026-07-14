from app.workflows.context import WorkflowContext
from app.utils.logger import logger
from app.security.governance.merge_confidence import compute_merge_confidence
from app.security.models import GateStatus, MergeConfidenceInputs

class IterationController:
    """Decides whether to trigger an improvement cycle based on test results only.
    Includes stagnation detection to avoid wasting iterations on the same failures.
    """
    
    def __init__(self, max_iterations: int = 5, target_coverage: float = 90.0):
        self.max_iterations = max_iterations
        self.target_coverage = target_coverage
        self._previous_passed = -1  # Track for stagnation
        self._stagnation_count = 0
        
    def should_improve(self, context: WorkflowContext) -> bool:
        if context.iteration_count >= self.max_iterations:
            logger.info("Max iterations reached.")
            return False
            
        val = context.validation_report
        if not val:
            return False
        
        # If build is broken (syntax/import error), we MUST repair
        if not val.build_status:
            logger.info("Build is broken (syntax/import errors). Triggering repair.")
            return True
            
        # Check test failures
        if val.execution_report and val.execution_report.failed > 0:
            # Stagnation detection: if tests_passed hasn't improved for 2 iterations, abort
            current_passed = val.execution_report.passed
            if current_passed == self._previous_passed:
                self._stagnation_count += 1
                if self._stagnation_count >= 2:
                    logger.warning(f"Stagnation detected: tests_passed stuck at {current_passed} for {self._stagnation_count} iterations. Aborting repair loop.")
                    return False
            else:
                self._stagnation_count = 0
            self._previous_passed = current_passed
            return True
            
        # Check coverage threshold
        if val.coverage_report and val.coverage_report.coverage_percentage < self.target_coverage:
            return True
            
        return False

    def calculate_merge_confidence(self, context: WorkflowContext) -> float:
        """Calculate the advisory 0-100 merge-confidence metric.

        This now delegates to the pure, deterministic
        :func:`app.security.governance.merge_confidence.compute_merge_confidence`,
        folding the historical build/test/coverage signal into a single
        ``testing_confidence`` dimension and adding the security dimension
        (security confidence, remaining findings, Quality_Gate status).

        Weighting (advisory 0-100): testing confidence 40, security confidence
        30, coverage 15, Quality_Gate passed 15, minus 2 points per remaining
        finding (capped at 10 findings / -20). The ``testing_confidence`` fed to
        the scorer preserves the *relative* weight of the old scheme (30 build +
        50 test-pass = 80): build contributes 3/8 and the test pass-ratio 5/8.

        Backward compatibility: callers that only rely on
        ``context.merge_confidence`` keep working. When the security pipeline has
        not run, the security inputs default to a clean state (full security
        confidence, no remaining findings, Quality_Gate passed) so the score
        remains meaningful for test-only runs. The result is advisory and never
        triggers an automatic merge (Requirement 13.3).
        """
        val = context.validation_report
        if not val:
            return 0.0

        # --- Testing confidence (0-1): build + test-pass signal --------------
        # Preserve the old 30:50 build:test-pass ratio -> 3/8 build, 5/8 tests.
        testing_confidence = 0.0
        if val.build_status:
            testing_confidence += 3.0 / 8.0
        if val.execution_report:
            total_tests = (
                val.execution_report.passed
                + val.execution_report.failed
                + val.execution_report.errors
            )
            if total_tests > 0:
                pass_ratio = val.execution_report.passed / total_tests
                testing_confidence += (5.0 / 8.0) * pass_ratio

        # --- Coverage (0-100) ------------------------------------------------
        coverage_percent = 0.0
        if val.coverage_report:
            coverage_percent = min(val.coverage_report.coverage_percentage, 100.0)

        # --- Security dimension (defaults to clean when pipeline hasn't run) --
        security_confidence, remaining_findings, quality_gate_status = (
            self._derive_security_inputs(context)
        )

        inputs = MergeConfidenceInputs(
            testing_confidence=testing_confidence,
            security_confidence=security_confidence,
            coverage_percent=coverage_percent,
            remaining_findings=remaining_findings,
            quality_gate_status=quality_gate_status,
        )

        result = compute_merge_confidence(inputs)
        context.merge_confidence = result.score
        return context.merge_confidence

    @staticmethod
    def _derive_security_inputs(
        context: WorkflowContext,
    ) -> tuple[float, int, GateStatus]:
        """Derive (security_confidence, remaining_findings, quality_gate_status).

        Reads the Layer 3 ``intelligence_result`` and any Layer 4 ``quality_gate``
        from the context when the security pipeline has run; otherwise returns a
        sensible clean default (full confidence, zero remaining findings, gate
        passed) so test-only runs still produce a meaningful score.
        """
        remaining_findings = 0
        security_confidence = 1.0

        intel = getattr(context, "intelligence_result", None)
        if intel is not None:
            fixed = tuple(getattr(intel, "fixed", ()) or ())
            remaining = tuple(getattr(intel, "remaining", ()) or ())
            remaining_findings = len(remaining)
            total = len(fixed) + remaining_findings
            # Fraction of findings resolved; no findings at all -> full confidence.
            security_confidence = (len(fixed) / total) if total > 0 else 1.0

        gate = getattr(context, "quality_gate", None)
        quality_gate_status = getattr(gate, "status", None)
        if not isinstance(quality_gate_status, GateStatus):
            quality_gate_status = GateStatus.PASSED

        return security_confidence, remaining_findings, quality_gate_status
