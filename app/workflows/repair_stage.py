from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.agents.repair.agent import RepairAgent
from app.utils.logger import logger
from app.schemas.quality import RepairedArtifact
from app.schemas.repair import RepairedFile

class RepairAgentStage(Stage):
    """
    Executes the Unified Repair Agent.
    Includes a hard filter that drops any rewritten file targeting non-test files.
    """
    def __init__(self, agent: RepairAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info(f"Iteration {context.iteration_count}: Starting RepairAgentStage (1-Call Unified Repair)...")
        
        # 1. Execute AI Repair Session
        session = self.agent.conduct_session(context)
        
        # 2. Convert to RepairedArtifact with HARD FILTER: only test files allowed
        repaired_files = []
        dropped = 0
        for p in session.repaired_files:
            safe_path = p.file_path.lstrip("/\\")
            if safe_path.startswith("tests/") or safe_path.startswith("test/") or safe_path == "conftest.py" or safe_path.startswith("tests\\") or safe_path.startswith("test\\"):
                repaired_files.append(RepairedFile(
                    file_path=p.file_path,
                    content=p.content
                ))
            else:
                logger.warning(f"DROPPED regenerated file for non-test path: {safe_path} — Repair Agent may only rewrite test files.")
                dropped += 1
            
        repaired_artifact = RepairedArtifact(repaired_files=repaired_files)
        context.repaired_artifact = repaired_artifact
        
        # Save into history
        context.iteration_history.append(repaired_artifact)
        
        logger.info(f"RepairAgentStage completed. Accepted {len(repaired_files)} completely regenerated files, dropped {dropped} non-test files.")
