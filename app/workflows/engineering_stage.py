from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.agents.engineering.agent import EngineeringAgent
from app.services.workspace_writer import WorkspaceWriterService
from app.utils.logger import logger

class EngineeringAgentStage(Stage):
    """
    Executes the Unified Engineering Agent.
    Replaces RepositoryUnderstanding, TestPlanning, and TestGeneration stages.
    """
    def __init__(self, agent: EngineeringAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info("Starting EngineeringAgentStage (1-Call Unified Session)...")
        
        # 1. AI Execution
        session = self.agent.conduct_session(context)
        
        # 2. Extract and spread context
        context.engineering_session = session
        context.change_summary = session.change_summary
        
        context.test_plan = session.test_plan
        context.planning_confidence = session.test_plan.confidence
        context.planning_summary = session.test_plan.summary
        context.recommended_test_levels = session.test_plan.recommended_test_levels
        
        # 3. File I/O
        writer = WorkspaceWriterService()
        if context.workspace:
            written_files = writer.write_artifact(context.workspace, session.generated_tests)
            
            context.generated_tests = session.generated_tests
            context.generated_files_count = len(written_files)
            context.generated_test_framework = session.generated_tests.framework
            context.generation_confidence = session.generated_tests.confidence
            context.generation_warnings = session.generated_tests.warnings
            context.workspace_changes = written_files
            logger.info(f"Wrote {len(written_files)} generated test files to workspace.")
        else:
            logger.warning("No workspace provided. Cannot write generated tests.")
            
        logger.info("EngineeringAgentStage completed successfully.")
