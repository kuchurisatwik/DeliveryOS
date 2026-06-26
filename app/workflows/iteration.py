from app.workflows.context import WorkflowContext

class IterationController:
    """Decides whether to trigger an improvement cycle based on validation metrics."""
    
    def __init__(self, max_iterations: int = 3, target_coverage: float = 90.0):
        self.max_iterations = max_iterations
        self.target_coverage = target_coverage
        
    def should_improve(self, context: WorkflowContext) -> bool:
        if context.iteration_count >= self.max_iterations:
            return False
            
        val = context.validation_report
        if not val:
            return False
            
        # Check deterministic failures
        if not val.build_status or not val.lint_status.passed or not val.type_status.passed:
            return True
            
        # Check tests pass rate
        if val.execution_report and val.execution_report.failed > 0:
            return True
            
        # Check coverage
        if val.coverage_report and val.coverage_report.coverage_percentage < self.target_coverage:
            return True
            
        # Check subjective review
        if context.review_report and not context.review_report.approved:
            return True
            
        return False

    def calculate_merge_confidence(self, context: WorkflowContext) -> float:
        """Calculates a 0-100 metric based on validation facts."""
        val = context.validation_report
        if not val:
            return 0.0
            
        score = 0.0
        
        # Build & Syntax (30 points)
        if val.build_status and val.syntax_status.passed and val.import_status.passed and val.dependency_status.passed:
            score += 30.0
            
        # Lint & Type (10 points)
        if val.lint_status.passed:
            score += 5.0
        if val.type_status.passed:
            score += 5.0
            
        # Tests Pass Rate (40 points)
        if val.execution_report:
            total_tests = val.execution_report.passed + val.execution_report.failed + val.execution_report.errors
            if total_tests > 0:
                pass_ratio = val.execution_report.passed / total_tests
                score += (pass_ratio * 40.0)
                
        # Coverage (20 points)
        if val.coverage_report:
            cov = min(val.coverage_report.coverage_percentage, 100.0)
            score += (cov / 100.0) * 20.0
            
        context.merge_confidence = round(score, 2)
        return context.merge_confidence
