import os
from app.workflows.context import WorkflowContext
from app.schemas.repair import RepairSessionSchema
from app.services.llm_service import LLMService
from app.utils.logger import logger

class RepairAgent:
    """The unified Repair Agent."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.prompt_template = ""
        prompt_path = os.path.join(os.getcwd(), "app", "prompts", "repair_session.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
                
    def conduct_session(self, context: WorkflowContext) -> RepairSessionSchema:
        lines = []
        lines.append(self.prompt_template)
        
        lines.append("\n=== VALIDATION REPORT ===")
        if context.validation_report:
            lines.append(context.validation_report.model_dump_json(indent=2))
        else:
            lines.append("No Validation Report available.")
            
        if context.workspace and context.workspace_changes:
            lines.append("\n=== GENERATED TESTS SOURCE ===")
            for file_path in context.workspace_changes:
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines.append(f"\n--- {file_path} ---")
                            lines.append(f.read())
                    except Exception:
                        pass
        
        # Also include original changed files context if needed
        if context.workspace and context.changed_files:
            lines.append("\n=== ORIGINAL CHANGED SOURCE CODE ===")
            for file_rel in context.changed_files:
                full_path = os.path.join(context.workspace, file_rel)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            lines.append(f"\n--- {full_path} ---")
                            lines.append(f.read())
                    except Exception:
                        pass
                        
        prompt = "\n".join(lines)
        
        logger.info("Executing unified Repair Agent...")
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                result: RepairSessionSchema = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=RepairSessionSchema
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"RepairAgent generation failed (attempt {attempt+1}/{max_retries}): {e}")
                
        raise ValueError(f"Failed to generate RepairSessionSchema after {max_retries} attempts. Last error: {last_error}")
