import time
import traceback
from typing import List
from app.utils.logger import logger
from app.workflows.context import WorkflowContext
from app.workflows.results import WorkflowResult
from app.workflows.stages import Stage






class WorkflowOrchestrator:
    """Coordinates workflow stages and manages state."""
    
    def run_pipeline(self, context: WorkflowContext, stages: List[Stage]) -> WorkflowResult:
        """Executes a list of stages sequentially."""
        start_time = time.time()
        completed_stages = []
        errors = []
        
        logger.info(f"Starting workflow for repository: {context.repository}")
        context.status = "RUNNING"
        
        for stage in stages:
            stage_name = stage.name
            logger.info(f"--- Stage Started: {stage_name} ---")
            stage_start_time = time.time()
            
            try:
                stage.execute(context)
                
                stage_duration = time.time() - stage_start_time
                completed_stages.append(stage_name)
                logger.info(f"--- Stage Completed: {stage_name} | Status: SUCCESS | Duration: {stage_duration:.2f}s ---")
                
            except Exception as e:
                stage_duration = time.time() - stage_start_time
                error_msg = f"{stage_name} failed: {str(e)}"
                errors.append(error_msg)
                logger.error(f"--- Stage Completed: {stage_name} | Status: FAILED | Duration: {stage_duration:.2f}s ---")
                logger.error(f"Traceback: {traceback.format_exc()}")
                context.status = "FAILED"
                break # Stop execution on first failure
                
        duration = time.time() - start_time
        status = "SUCCESS" if not errors else "FAILED"
        if status == "SUCCESS":
            context.status = "COMPLETED"
            
        result = WorkflowResult(
            status=status,
            duration=duration,
            completed_stages=completed_stages,
            errors=errors
        )
        
        logger.info(f"Workflow finished. Status: {result.status}. Duration: {result.duration:.2f}s")
        return result
