from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.utils.logger import logger
from app.services.test_executor import TestExecutionService
from app.services.coverage_service import CoverageService
from app.agents.review.agent import ReviewAgent
from app.agents.coverage.agent import CoverageAgent
from app.workflows.feedback import FeedbackBuilder

class TestExecutionStage(Stage):
    """Deterministically runs the generated tests in the workspace."""
    
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: 'LLMService' = None) -> None:
        if not context.workspace:
            raise ValueError("TestExecutionStage requires a workspace path.")
            
        logger.info(f"Iteration {context.iteration_count}: Executing tests...")
        executor = TestExecutionService()
        report = executor.run_tests(context.workspace)
        context.test_execution_report = report
        
        logger.info(f"Tests execution complete. Passed: {report.passed}, Failed: {report.failed}")

class CoverageAnalysisStage(Stage):
    """Deterministically runs coverage analysis in the workspace."""
    
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: 'LLMService' = None) -> None:
        if not context.workspace:
            raise ValueError("CoverageAnalysisStage requires a workspace path.")
            
        logger.info(f"Iteration {context.iteration_count}: Running coverage analysis...")
        coverage = CoverageService()
        report = coverage.run_coverage(context.workspace)
        context.coverage_report = report
        context.coverage_percentage = report.coverage_percentage
        
        logger.info(f"Coverage analysis complete. Coverage: {report.coverage_percentage}%")

class ReviewAgentStage(Stage):
    """AI agent reviews the generated tests."""
    
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: 'LLMService' = None) -> None:
        if not llm_service:
            raise ValueError("ReviewAgentStage requires an LLMService")
            
        logger.info(f"Iteration {context.iteration_count}: Review Agent analyzing tests...")
        agent = ReviewAgent(llm_service)
        report = agent.review_tests(context)
        context.review_report = report
        
        logger.info(f"Review Agent complete. Approved: {report.approved}")

class CoverageAgentStage(Stage):
    """AI agent maps coverage gaps to missing test scenarios."""
    
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: 'LLMService' = None) -> None:
        if not llm_service:
            raise ValueError("CoverageAgentStage requires an LLMService")
            
        logger.info(f"Iteration {context.iteration_count}: Coverage Agent mapping gaps...")
        agent = CoverageAgent(llm_service)
        plan = agent.analyze_coverage(context)
        context.coverage_improvement_plan = plan
        
        logger.info(f"Coverage Agent complete. Found {len(plan.missing_scenarios)} missing scenarios.")

class FeedbackBuilderStage(Stage):
    """Deterministically merges all reports into GenerationFeedback."""
    
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: 'LLMService' = None) -> None:
        logger.info(f"Iteration {context.iteration_count}: Building iteration feedback...")
        builder = FeedbackBuilder()
        feedback = builder.build_feedback(context)
        context.generation_feedback = feedback
        
        logger.info(f"Feedback Builder complete. Priority: {feedback.priority}")
