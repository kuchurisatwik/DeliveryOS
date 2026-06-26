from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.utils.logger import logger
from app.agents.test_generation.generator import TestGenerationAgent
from app.services.workspace_writer import WorkspaceWriterService

class TestGenerationAgentStage(Stage):
    """Executes the Test Generation Agent (SDET) and writes the results to the workspace."""
    def __init__(self, llm_service: 'LLMService'):
        self.llm_service = llm_service
        
    def execute(self, context: WorkflowContext) -> None:
            
        if not context.test_plan:
            logger.warning("No test_plan found in context. Skipping TestGenerationAgentStage.")
            return
            
        if not context.workspace:
            raise ValueError("No workspace path set in context. Cannot generate and write tests.")
            
        logger.info("Calling Test Generation Agent (Senior SDET)...")
        agent = TestGenerationAgent(self.llm_service)
        
        # 1. Reasoning Phase (AI)
        artifact = agent.generate_tests(context)
        
        # 2. Execution Phase (File I/O)
        logger.info(f"Test Generation completed. Found {len(artifact.generated_files)} files. Writing to workspace...")
        writer = WorkspaceWriterService()
        written_files = writer.write_artifact(context.workspace, artifact)
        
        # 3. Context Update
        context.generated_tests = artifact
        context.generated_files_count = len(written_files)
        context.generated_test_framework = artifact.framework
        context.generation_confidence = artifact.confidence
        context.generation_warnings = artifact.warnings
        context.workspace_changes = written_files
        
        logger.info(f"Successfully wrote {context.generated_files_count} files. Generation confidence: {context.generation_confidence}")
