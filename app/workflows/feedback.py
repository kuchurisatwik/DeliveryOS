from app.workflows.context import WorkflowContext
from app.schemas.quality import GenerationFeedback

class FeedbackBuilder:
    """Deterministically merges various quality reports into a single GenerationFeedback object."""
    
    def build_feedback(self, context: WorkflowContext) -> GenerationFeedback:
        feedback = GenerationFeedback()
        
        # 1. From Execution Report
        if context.test_execution_report:
            feedback.failed_tests = context.test_execution_report.failed_test_names
            
        # 2. From Review Report
        if context.review_report:
            feedback.weak_assertions = context.review_report.weak_assertions
            
        # 3. From Coverage Report
        if context.coverage_improvement_plan:
            feedback.missing_scenarios = context.coverage_improvement_plan.missing_scenarios
            
        if context.coverage_report:
            feedback.coverage_gaps = context.coverage_report.missing_line_numbers
            
        # Determine priority
        if feedback.failed_tests or (context.coverage_report and context.coverage_report.coverage_percentage < 80.0):
            feedback.priority = "High"
        elif feedback.missing_scenarios:
            feedback.priority = "Medium"
        else:
            feedback.priority = "Low"
            
        return feedback
