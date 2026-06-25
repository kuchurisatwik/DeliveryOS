from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
import hmac
import hashlib
from app.schemas.webhook import PushEventSchema
from app.workflows.context import WorkflowContext
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.stages import (
    CloneRepositoryStage, CreateBranchStage,
    GenerateDummyReportStage, CommitStage, PushBranchStage, CreatePullRequestStage
)
from app.workflows.intelligence_stages import (
    GitDiffCollectorStage, FileClassifierStage, MetadataExtractorStage,
    ContextBuilderStage, RepositoryUnderstandingAgentStage
)
from app.workflows.planning_stages import TestPlanningAgentStage
from app.workflows.generation_stages import TestGenerationAgentStage
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService
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
    TestExecutionStage, CoverageAnalysisStage, ReviewAgentStage,
    CoverageAgentStage, FeedbackBuilderStage
)
from app.workflows.iteration import IterationController

def run_ai_sde_workflow(push_event: PushEventSchema):
    """Background task function to execute the AI-SDE workflow using the orchestrator."""
    ref = push_event.ref
    base_branch = ref.replace("refs/heads/", "") if "refs/heads/" in ref else "main"
    
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
    orchestrator = WorkflowOrchestrator(git_service, github_service, llm_service)
    
    # 1. Pre-Loop Stages (Analysis & Planning)
    pre_stages = [
        CloneRepositoryStage(),
        GitDiffCollectorStage(),
        FileClassifierStage(),
        MetadataExtractorStage(),
        ContextBuilderStage(),
        RepositoryUnderstandingAgentStage(),
        TestPlanningAgentStage(),
        CreateBranchStage(),
    ]
    res = orchestrator.run_pipeline(context, pre_stages)
    if res.status == "FAILED":
        logger.error("Pipeline failed during pre-stages. Aborting.")
        return
        
    # 2. AI Quality Loop
    controller = IterationController()
    
    while True:
        generation_execution_stages = [
            TestGenerationAgentStage(),
            TestExecutionStage(),
            CoverageAnalysisStage(),
        ]
        
        res = orchestrator.run_pipeline(context, generation_execution_stages)
        if res.status == "FAILED":
            logger.error("Pipeline failed during generation/execution. Aborting.")
            break
            
        if not controller.should_regenerate(context):
            logger.info("Quality thresholds met or max iterations reached. Exiting loop.")
            break
            
        logger.info(f"Triggering iteration {context.iteration_count + 1} feedback loop...")
        
        feedback_stages = [
            ReviewAgentStage(),
            CoverageAgentStage(),
            FeedbackBuilderStage()
        ]
        res = orchestrator.run_pipeline(context, feedback_stages)
        if res.status == "FAILED":
            logger.error("Pipeline failed during feedback generation. Aborting.")
            break
            
        context.iteration_count += 1
        
    # 3. Post-Loop Stages (Commit & PR)
    post_stages = [
        GenerateDummyReportStage(),
        CommitStage(),
        PushBranchStage(),
        CreatePullRequestStage()
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
