from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext



from app.utils.logger import logger
from app.agents.test_planning.planner import TestPlannerAgent

class TestPlanningAgentStage(Stage):
    # Define correctly after LLMService is resolved.
    """Executes the Test Planning Agent to build a test plan from the architectural summary."""
    def __init__(self, llm_service: 'app.services.llm_service.LLMService'):
        self.llm_service = llm_service
        
    def execute(self, context: WorkflowContext) -> None:
            
        if not context.change_summary:
            logger.warning("No change_summary found in context. Skipping TestPlanningAgentStage.")
            return
            
        logger.info("Calling Test Planning Agent (Senior QA Architect)...")
        agent = TestPlannerAgent(self.llm_service)
        test_plan = agent.generate_plan(context)
        
        context.test_plan = test_plan
        context.planning_confidence = test_plan.confidence
        context.planning_summary = test_plan.summary
        context.recommended_test_levels = test_plan.recommended_test_levels
        
        logger.info(f"Test Planning completed. Confidence: {test_plan.confidence}. Priority: {test_plan.priority}")
