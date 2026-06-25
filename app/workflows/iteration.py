from app.workflows.context import WorkflowContext

class IterationController:
    """Decides whether to trigger a regeneration cycle based on quality metrics."""
    
    def __init__(self, max_iterations: int = 3, target_coverage: float = 90.0):
        self.max_iterations = max_iterations
        self.target_coverage = target_coverage
        
    def should_regenerate(self, context: WorkflowContext) -> bool:
        if context.iteration_count >= self.max_iterations:
            return False
            
        # Check pass rate
        if context.test_execution_report and context.test_execution_report.failed > 0:
            return True
            
        # Check coverage
        if context.coverage_report and context.coverage_report.coverage_percentage < self.target_coverage:
            return True
            
        # Check review
        if context.review_report and not context.review_report.approved:
            return True
            
        return False
