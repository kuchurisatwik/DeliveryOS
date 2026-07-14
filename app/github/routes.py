from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
import hmac
import hashlib
from app.schemas.webhook import PushEventSchema
from app.workflows.context import WorkflowContext
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.stages import (
    CloneRepositoryStage, AnalyzeFilesStage, CreateBranchStage,
    GenerateDummyReportStage, CommitStage, PushBranchStage, CreatePullRequestStage
)
from app.workflows.engineering_stage import EngineeringAgentStage
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService
from app.services.validators import ValidationEngine
from app.agents.engineering.agent import EngineeringAgent
from app.agents.repair.agent import RepairAgent
from app.services.workspace_writer import WorkspaceWriterService
from app.workflows.intelligence_stages import (
    GitDiffCollectorStage, RepositoryIndexerStage, ContextRetrievalStage,
    PromptAssemblyStage, FeaturePlannerStage
)
from app.security.pipeline import (
    build_security_stages,
    ensure_security_inputs,
    MissingPipelineInputError,
    run_security_pipeline_with_containment,
)
from app.config.settings import settings
from app.utils.logger import logger

router = APIRouter(prefix="/github", tags=["github"])

def verify_signature(payload: bytes, signature: str) -> bool:
    """Verifies the GitHub webhook signature."""
    if not settings.WEBHOOK_SECRET:
        # Skip validation if secret is not configured
        return True
        
    if not signature:
        return False
        
    mac = hmac.new(settings.WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

from app.workflows.quality_stages import (
    ValidationEngineStage, WorkspaceWriterStage
)
from app.workflows.repair_stage import RepairAgentStage
from app.workflows.iteration import IterationController
from app.services.repository.retriever import ContextRetrievalEngine

# Valid values for the PIPELINE_MODE switch.
_VALID_PIPELINE_MODES = ("security", "testing", "both")


def resolve_pipeline_mode() -> str:
    """Return the configured pipeline mode, defaulting to 'both' when unset/invalid.

    Reads ``settings.PIPELINE_MODE`` and normalizes it. An unrecognized value
    falls back to 'both' with a warning so a typo never silently disables a
    pipeline.
    """
    mode = (settings.PIPELINE_MODE or "both").strip().lower()
    if mode not in _VALID_PIPELINE_MODES:
        logger.warning(
            "Unknown PIPELINE_MODE '%s'; expected one of %s. Falling back to 'both'.",
            settings.PIPELINE_MODE,
            _VALID_PIPELINE_MODES,
        )
        return "both"
    return mode


def _run_testing_pipeline(
    orchestrator: WorkflowOrchestrator,
    context: WorkflowContext,
    engineering_agent: EngineeringAgent,
    validation_engine: ValidationEngine,
    repair_agent: RepairAgent,
    writer_service: WorkspaceWriterService,
) -> "IterationController | None":
    """Run the test-generation / validation / repair pipeline over each task.

    Returns the last :class:`IterationController` used (or ``None`` when there were
    no tasks), so the caller can compute the final merge confidence.
    """
    if not context.tasks:
        logger.info("No tasks to process for the testing pipeline.")
        return None

    logger.info(f"Processing {len(context.tasks)} independent Engineering Tasks...")
    controller: "IterationController | None" = None

    for task in context.tasks:
        context.current_task = task
        logger.info(f"==== STARTING TASK: {task.feature_name} ====")

        # Engineering Session for this Task
        engineering_stages = [
            ContextRetrievalStage(),
            PromptAssemblyStage(),
            EngineeringAgentStage(engineering_agent),
        ]
        res = orchestrator.run_pipeline(context, engineering_stages)
        if res.status == "FAILED":
            logger.error(f"Pipeline failed during Engineering Session for {task.feature_name}. Skipping to next task.")
            continue

        # Validation & Improvement Engine Loop for this Task
        context.iteration_count = 1
        controller = IterationController(max_iterations=5)

        while True:
            val_stage = [ValidationEngineStage(validation_engine)]
            res = orchestrator.run_pipeline(context, val_stage)
            if res.status == "FAILED":
                logger.error(f"Validation failed fatally for {task.feature_name}. Breaking repair loop.")
                break

            if not controller.should_improve(context):
                logger.info(f"Quality thresholds met or max iterations reached for {task.feature_name}. Exiting loop.")
                break

            logger.info(f"[{task.feature_name}] Triggering improvement iteration {context.iteration_count}...")

            improvement_stages = [
                RepairAgentStage(repair_agent),
                WorkspaceWriterStage(writer_service)
            ]
            res = orchestrator.run_pipeline(context, improvement_stages)
            if res.status == "FAILED":
                logger.error(f"Repair failed fatally for {task.feature_name}. Breaking repair loop.")
                break

            context.iteration_count += 1

        logger.info(f"==== FINISHED TASK: {task.feature_name} ====\n")

    if controller:
        controller.calculate_merge_confidence(context)
    return controller


def _run_security_pipeline(
    orchestrator: WorkflowOrchestrator,
    context: WorkflowContext,
    llm_service: LLMService,
) -> None:
    """Run the security pipeline (Layers 1→2→3→4) over the whole commit.

    Builds a whole-commit repository context first (so enrichment/reachability
    cover every changed file regardless of whether the testing loop ran), resolves
    Repo_Config before Detection (1.5), then runs Detection → Intelligence →
    Governance in strict order (1.2) with layer-failure containment (1.4). A missing
    required input halts it with a named diagnostic (1.3).
    """
    # Build a fresh whole-commit RepoContext for the security layers. This makes
    # the security pipeline independent of the per-task testing loop and ensures
    # enrichment/reachability reflect the entire commit (not just the last task).
    if context.workspace and context.changed_files:
        try:
            engine = ContextRetrievalEngine(context.workspace)
            context.retrieved_knowledge = engine.retrieve(
                list(context.changed_files), context.structured_diff
            )
        except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
            logger.warning("Whole-commit context retrieval failed: %s", exc)

    try:
        ensure_security_inputs(context)
    except MissingPipelineInputError as e:
        logger.error(f"Security pipeline halted: {e}")
        return

    security_stages = build_security_stages(llm_service, workspace=context.workspace)
    # Layer-failure containment (1.4): an unrecoverable error in any security layer
    # stops subsequent layers and records the failing layer on the context so the
    # report sets Pull_Request_Report.failed_layer.
    sec_res = run_security_pipeline_with_containment(
        orchestrator, context, security_stages
    )
    if sec_res.status == "FAILED":
        logger.error(
            "Security pipeline failed in '%s' layer: %s. Continuing to report/PR "
            "stages so a diagnostic report is still produced.",
            context.failed_layer,
            sec_res.errors,
        )


def run_ai_sde_workflow(push_event: PushEventSchema):
    """Background task function to execute the AI-SDE workflow using the orchestrator.

    The ``PIPELINE_MODE`` setting selects which pipeline(s) run:
    ``'security'`` (security only), ``'testing'`` (test generation only), or
    ``'both'`` (default). Shared setup (clone, branch, diff, index, feature
    planning) and the final report/commit/PR stages always run so a PR is produced
    regardless of mode.
    """
    ref = push_event.ref
    base_branch = ref.replace("refs/heads/", "") if "refs/heads/" in ref else "main"

    mode = resolve_pipeline_mode()
    run_testing = mode in ("testing", "both")
    run_security = mode in ("security", "both")
    logger.info(f"Pipeline mode: '{mode}' (testing={run_testing}, security={run_security})")

    context = WorkflowContext(
        repository=push_event.repository.full_name,
        repo_name=push_event.repository.name,
        clone_url=push_event.repository.clone_url,
        branch=base_branch,
        commit_sha=push_event.after
    )
    
    git_service = GitService()
    github_service = GitHubService()
    llm_service = LLMService()
    
    engineering_agent = EngineeringAgent(llm_service)
    validation_engine = ValidationEngine()
    repair_agent = RepairAgent(llm_service)
    writer_service = WorkspaceWriterService()
    
    orchestrator = WorkflowOrchestrator()
    
    # 1. Pre-Stages (Setup & Feature Planning) — shared by both pipelines.
    pre_stages = [
        CloneRepositoryStage(git_service),
        CreateBranchStage(git_service),
        AnalyzeFilesStage(git_service),
        GitDiffCollectorStage(git_service),
        RepositoryIndexerStage(),
        FeaturePlannerStage()
    ]
    res = orchestrator.run_pipeline(context, pre_stages)
    if res.status == "FAILED":
        logger.error("Pipeline failed during setup. Aborting.")
        return

    # 2. Testing pipeline (test generation + validation/repair) — optional.
    if run_testing:
        _run_testing_pipeline(
            orchestrator, context, engineering_agent,
            validation_engine, repair_agent, writer_service,
        )
    else:
        logger.info("Skipping testing pipeline (PIPELINE_MODE='%s').", mode)

    # 3. Security pipeline (Layers 1→2→3→4) — optional.
    if run_security:
        _run_security_pipeline(orchestrator, context, llm_service)
    else:
        logger.info("Skipping security pipeline (PIPELINE_MODE='%s').", mode)

    # 4. Post-Loop Stages (Report, Commit & PR) — always run.
    post_stages = [
        GenerateDummyReportStage(),
        CommitStage(git_service),
        PushBranchStage(git_service),
        CreatePullRequestStage(github_service)
    ]
    orchestrator.run_pipeline(context, post_stages)

@router.post("/webhook")
async def github_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None)
):
    """Endpoint for receiving GitHub webhooks."""
    payload_bytes = await request.body()
    
    if not verify_signature(payload_bytes, x_hub_signature_256):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
        
    if x_github_event == "push":
        # Parse payload
        try:
            payload_data = await request.json()
            # Validate schema
            push_event = PushEventSchema(**payload_data)
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
            
        # Trigger background task with the new orchestrator
        if "ai-sde/" in push_event.ref:
            logger.info(f"Ignoring push event for AI branch: {push_event.ref}")
            return {"status": "ignored", "message": "Ignoring AI generated branch to prevent infinite loops"}
            
        background_tasks.add_task(run_ai_sde_workflow, push_event)
        
        return {"status": "accepted", "message": "Push event queued for processing"}
        
    return {"status": "ignored", "message": f"Event {x_github_event} not handled"}
