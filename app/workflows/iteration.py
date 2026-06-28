from app.workflows.context import WorkflowContext
from app.utils.logger import logger

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
            
        # Only care about test failures — not lint/type
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
        """Calculates a 0-100 metric based on test results and coverage."""
        val = context.validation_report
        if not val:
            return 0.0
            
        score = 0.0
        
        # Build & Syntax (30 points)
        if val.build_status:
            score += 30.0
            
        # Tests Pass Rate (50 points) — increased weight since this is what matters
        if val.execution_report:
            total_tests = val.execution_report.passed + val.execution_report.failed + val.execution_report.errors
            if total_tests > 0:
                pass_ratio = val.execution_report.passed / total_tests
                score += (pass_ratio * 50.0)
                
        # Coverage (20 points)
        if val.coverage_report:
            cov = min(val.coverage_report.coverage_percentage, 100.0)
            score += (cov / 100.0) * 20.0
            
        context.merge_confidence = round(score, 2)
        return context.merge_confidence
