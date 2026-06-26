from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.utils.logger import logger
from app.agents.test_planning.planner import TestPlannerAgent

class TestPlanningAgentStage(Stage):
    """Executes the Test Planning Agent to build a test plan from the architectural summary."""
    
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: None) -> None:
        if not llm_service:
            raise ValueError("TestPlanningAgentStage requires an LLMService instance")
            
        if not context.change_summary:
            logger.warning("No change_summary found in context. Skipping TestPlanningAgentStage.")
            return
            
        logger.info("Calling Test Planning Agent (Senior QA Architect)...")
        agent = TestPlannerAgent(llm_service)
        test_plan = agent.generate_plan(context)
        
        context.test_plan = test_plan
        context.planning_confidence = test_plan.confidence
        context.planning_summary = test_plan.summary
        context.recommended_test_levels = test_plan.recommended_test_levels
        
        logger.info(f"Test Planning completed. Confidence: {test_plan.confidence}. Priority: {test_plan.priority}")
