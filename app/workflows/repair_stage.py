from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.agents.repair.agent import RepairAgent
from app.utils.logger import logger
from app.schemas.quality import PatchArtifact, PatchBlock

class RepairAgentStage(Stage):
    """
    Executes the Unified Repair Agent.
    Includes a hard filter that drops any patch targeting non-test files.
    """
    def __init__(self, agent: RepairAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info(f"Iteration {context.iteration_count}: Starting RepairAgentStage (1-Call Unified Repair)...")
        
        # 1. Execute AI Repair Session
        session = self.agent.conduct_session(context)
        
        # 2. Convert to PatchArtifact with HARD FILTER: only test files allowed
        patches = []
        dropped = 0
        for p in session.patches:
            safe_path = p.file_path.lstrip("/\\")
            if safe_path.startswith("tests/") or safe_path.startswith("test/") or safe_path == "conftest.py" or safe_path.startswith("tests\\") or safe_path.startswith("test\\"):
                patches.append(PatchBlock(
                    file_path=p.file_path,
                    search_block=p.search_block,
                    replace_block=p.replace_block
                ))
            else:
                logger.warning(f"DROPPED patch for non-test file: {safe_path} — Repair Agent may only patch test files.")
                dropped += 1
            
        patch_artifact = PatchArtifact(patches=patches)
        context.patch_artifact = patch_artifact
        
        # Save into history
        context.iteration_history.append(patch_artifact)
        
        logger.info(f"RepairAgentStage completed. Accepted {len(patches)} patches, dropped {dropped} non-test patches.")
