import os
from app.workflows.context import WorkflowContext
from app.schemas.session import EngineeringSessionSchema
from app.services.llm_service import LLMService
from app.utils.logger import logger

class EngineeringAgent:
    """The unified Engineering Agent (Architect + QA + SDET)."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.prompt_template = ""
        prompt_path = os.path.join(os.getcwd(), "app", "prompts", "engineering_session.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
                
    def conduct_session(self, context: WorkflowContext) -> EngineeringSessionSchema:
        lines = []
        lines.append(self.prompt_template)
        
        lines.append("\n=== REPOSITORY METADATA ===")
        lines.append(f"Repository: {context.repository}")
        lines.append(f"Branch: {context.branch}")
        lines.append(f"Commit SHA: {context.commit_sha}")
        lines.append(f"Language: {context.repository_language or 'Python'}")
        lines.append(f"Framework: {context.framework or 'FastAPI/Pytest'}")
        
        if context.structured_diff:
            lines.append("\n=== GIT DIFF (CHANGES TO TEST) ===")
            for t in ["added", "modified", "deleted", "renamed"]:
                if context.structured_diff.get(t):
                    lines.append(f"--- {t.upper()} FILES ---")
                    for f in context.structured_diff[t]:
                        lines.append(f"File: {f.get('path')}")
                        if "diff" in f and f["diff"]:
                            lines.append("Diff:")
                            lines.append(f["diff"])
                            lines.append("")
                            
        lines.append("\n=== REPOSITORY KNOWLEDGE (INTERNAL API) ===")
        lines.append(context.llm_context)
        
        if context.workspace and context.changed_files:
            lines.append("\n=== FULL SOURCE CODE (CHANGED FILES) ===")
            for file_rel in context.changed_files:
                if file_rel.endswith(".py"):
                    full_path = os.path.join(context.workspace, file_rel)
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8") as f:
                                lines.append(f"\n--- {file_rel} ---")
                                lines.append(f.read())
                        except Exception:
                            pass
                            
        prompt = "\n".join(lines)
        
        logger.info("Executing unified Engineering Agent (Change Summary + Test Plan + Test Generation)...")
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                result: EngineeringSessionSchema = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=EngineeringSessionSchema
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"EngineeringAgent generation failed (attempt {attempt+1}/{max_retries}): {e}")
                
        raise ValueError(f"Failed to generate EngineeringSessionSchema after {max_retries} attempts. Last error: {last_error}")
