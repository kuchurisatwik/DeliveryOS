from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext


from app.utils.logger import logger
from app.services.validators import ValidationEngine
from app.agents.review.agent import ReviewAgent
from app.agents.coverage.agent import CoverageAgent
from app.workflows.planner import ImprovementPlanner
from app.agents.test_improvement.agent import TestImprovementAgent
from app.services.workspace_patch import WorkspacePatchService

class ValidationEngineStage(Stage):
    """Deterministically runs all validation services in the workspace."""
    def __init__(self, engine: ValidationEngine):
        self.engine = engine
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("ValidationEngineStage requires a workspace path.")
            
        logger.info(f"Iteration {context.iteration_count}: Running Validation Engine...")
        report = self.engine.run_all(context.workspace)
        context.validation_report = report
        
        logger.info(f"Validation complete. Build: {report.build_status}, Syntax: {report.syntax_status.passed}, Tests Passed: {report.execution_report.passed if report.execution_report else 0}")

class ReviewAgentStage(Stage):
    """AI agent reviews the generated tests based on validation report."""
    def __init__(self, agent: ReviewAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info(f"Iteration {context.iteration_count}: Review Agent analyzing tests...")
        report = self.agent.review_tests(context)
        context.review_report = report
        
        logger.info(f"Review Agent complete. Approved: {report.approved}")

class CoverageAgentStage(Stage):
    """AI agent maps coverage gaps to missing test scenarios."""
    def __init__(self, agent: CoverageAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info(f"Iteration {context.iteration_count}: Coverage Agent mapping gaps...")
        analysis = self.agent.analyze_coverage(context)
        context.coverage_analysis = analysis
        
        logger.info(f"Coverage Agent complete. Found {len(analysis.missing_scenarios)} missing scenarios.")

class ImprovementPlannerStage(Stage):
    """Deterministically merges all reports into an ImprovementPlan."""
    def __init__(self, planner: ImprovementPlanner):
        self.planner = planner
        
    def execute(self, context: WorkflowContext) -> None:
        logger.info(f"Iteration {context.iteration_count}: Building improvement plan...")
        plan = self.planner.build_plan(
            validation=context.validation_report,
            review=context.review_report,
            coverage=context.coverage_analysis
        )
        context.improvement_plan = plan
        
        logger.info(f"Improvement Planner complete. Actions required: {len(plan.actions)}")

class TestImprovementAgentStage(Stage):
    """AI agent generates targeted patches based on the ImprovementPlan."""
    def __init__(self, agent: TestImprovementAgent):
        self.agent = agent
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.improvement_plan or len(context.improvement_plan.actions) == 0:
            logger.info("No improvement actions required. Skipping TestImprovementAgent.")
            return
            
        logger.info(f"Iteration {context.iteration_count}: Generating targeted patches...")
        patches = self.agent.generate_patches(context)
        context.patch_artifact = patches
        
        # Save into history
        context.iteration_history.append(patches)
        
        logger.info(f"Test Improvement Agent complete. Generated {len(patches.patches)} patches.")

class WorkspacePatchStage(Stage):
    """Deterministically applies the patch artifact to the workspace."""
    def __init__(self, patch_service: WorkspacePatchService):
        self.patch_service = patch_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.patch_artifact or len(context.patch_artifact.patches) == 0:
            logger.info("No patches to apply. Skipping WorkspacePatchStage.")
            return
            
        logger.info(f"Iteration {context.iteration_count}: Applying patches to workspace...")
        self.patch_service.apply_patches(context.workspace, context.patch_artifact)
        
        logger.info("Workspace Patch applied.")
