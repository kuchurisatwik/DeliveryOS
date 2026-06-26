from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext
from app.agents.repair.agent import RepairAgent
from app.utils.logger import logger
from app.schemas.quality import PatchArtifact, PatchBlock

class RepairAgentStage(Stage):
    """
    Executes the Unified Repair Agent.
    Replaces ReviewAgent, CoverageAgent, ImprovementPlanner, and TestImprovementAgent stages.
    Takes ValidationReport and outputs PatchArtifact.
    """
    def __init__(self, agent: RepairAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info(f"Iteration {context.iteration_count}: Starting RepairAgentStage (1-Call Unified Repair)...")
        
        # 1. Execute AI Repair Session
        session = self.agent.conduct_session(context)
        
        # 2. Convert to PatchArtifact for downstream WorkspacePatchStage
        # (Alternatively, WorkspacePatchStage could be updated to accept RepairSessionSchema directly, 
        # but maintaining compatibility is safe).
        patches = []
        for p in session.patches:
            patches.append(PatchBlock(
                file_path=p.file_path,
                search_block=p.search_block,
                replace_block=p.replace_block
            ))
            
        patch_artifact = PatchArtifact(patches=patches)
        context.patch_artifact = patch_artifact
        
        # Save into history
        context.iteration_history.append(patch_artifact)
        
        logger.info(f"RepairAgentStage completed successfully. Generated {len(patches)} patches.")
