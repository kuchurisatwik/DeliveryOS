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
from app.services.knowledge_aggregator import RepositoryKnowledgeAggregator
from app.services.validators import ValidationEngine
from app.agents.engineering.agent import EngineeringAgent
from app.agents.repair.agent import RepairAgent
from app.services.workspace_patch import WorkspacePatchService
from app.workflows.intelligence_stages import (
    GitDiffCollectorStage, FileClassifierStage, MetadataExtractorStage,
    ContextBuilderStage
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
    ValidationEngineStage, WorkspacePatchStage
)



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
    
    aggregator = RepositoryKnowledgeAggregator()
    engineering_agent = EngineeringAgent(llm_service)
    validation_engine = ValidationEngine()
    repair_agent = RepairAgent(llm_service)
    patch_service = WorkspacePatchService()
    
    orchestrator = WorkflowOrchestrator()
    
    # 1. Engineering Session (Understanding, Planning, Generation in 1-Call)
    pre_stages = [
        CloneRepositoryStage(git_service),
        AnalyzeFilesStage(git_service),
        GitDiffCollectorStage(git_service),
        FileClassifierStage(),
        MetadataExtractorStage(aggregator),
        ContextBuilderStage(),
        CreateBranchStage(git_service),
        EngineeringAgentStage(engineering_agent),
    ]
    res = orchestrator.run_pipeline(context, pre_stages)
    if res.status == "FAILED":
        logger.error("Pipeline failed during Engineering Session. Aborting.")
        return
        
    # 3. Validation & Improvement Engine Loop
    from app.workflows.iteration import IterationController
    controller = IterationController(max_iterations=5)
    
    while True:
        # Step 3a: Deterministic Validation
        val_stage = [ValidationEngineStage(validation_engine)]
        res = orchestrator.run_pipeline(context, val_stage)
        if res.status == "FAILED":
            logger.error("Pipeline failed during Validation. Aborting.")
            break
            
        if not controller.should_improve(context):
            logger.info("Quality thresholds met or max iterations reached. Exiting Improvement loop.")
            break
            
        logger.info(f"Triggering improvement iteration {context.iteration_count}...")
        
        # Step 3b: Unified Repair Session
        improvement_stages = [
            RepairAgentStage(repair_agent),
            WorkspacePatchStage(patch_service)
        ]
        res = orchestrator.run_pipeline(context, improvement_stages)
        if res.status == "FAILED":
            logger.error("Pipeline failed during improvement stages. Aborting.")
            break
            
        context.iteration_count += 1
        
    # 4. Calculate Final Merge Confidence
    controller.calculate_merge_confidence(context)
        
    # 5. Post-Loop Stages (Commit & PR)
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
