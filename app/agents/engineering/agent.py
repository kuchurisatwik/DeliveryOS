import os
import glob
from app.workflows.context import WorkflowContext
from app.schemas.session import EngineeringSessionSchema
from app.services.llm_service import LLMService
from app.utils.logger import logger

class EngineeringAgent:
    """The unified Engineering Agent (Architect + QA + SDET).
    Constructs a focused prompt with commit context and rules at the bottom for recency bias.
    """
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.prompt_template = ""
        prompt_path = os.path.join(os.getcwd(), "app", "prompts", "engineering_session.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
                
    def conduct_session(self, context: WorkflowContext) -> EngineeringSessionSchema:
        # Early exit: if no meaningful changes, skip test generation
        has_changes = bool(context.changed_files)
        has_diff = bool(
            context.structured_diff.get("added") or 
            context.structured_diff.get("modified")
        )
        if not has_changes and not has_diff:
            logger.warning("No changed files and no diff entries. Skipping test generation for empty commit.")
            raise ValueError("No meaningful code changes detected in this commit. Cannot generate tests.")
        
        lines = []
        
        # Section 1: Repository Metadata
        lines.append("=== REPOSITORY METADATA ===")
        lines.append(f"Repository: {context.repository}")
        lines.append(f"Branch: {context.branch}")
        lines.append(f"Commit SHA: {context.commit_sha}")
        lines.append(f"Language: {context.repository_language or 'Python'}")
        lines.append(f"Framework: {context.framework or 'FastAPI/Pytest'}")
        
        # Section 2: Changed Files List
        if context.changed_files:
            lines.append("\n=== CHANGED FILES IN THIS COMMIT ===")
            for f in context.changed_files:
                lines.append(f"  - {f}")
        

        # Section 4: Target Context (Retrieved Symbols and Tests)
        if hasattr(context, 'llm_context') and context.llm_context:
            lines.append("\n=== REPOSITORY CONTEXT ===")
            # lines.append("IMPORTANT: Do not try to write tests for all files. Pick the SINGLE most critical changed class/function below and write ONE complete test file for it.")
            lines.append(context.llm_context)

        # Section 5: Critical Rules at the END (Recency Bias)
        lines.append("\n=== CRITICAL INSTRUCTIONS (READ CAREFULLY) ===")
        lines.append(self.prompt_template)
        
        prompt = "\n".join(lines)
        
        logger.info("Executing unified Engineering Agent (Change Summary + Test Plan + Test Generation)...")
        logger.info(f"Prompt size: {len(prompt)} chars, changed_files: {len(context.changed_files)}")
        
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                result: EngineeringSessionSchema = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=EngineeringSessionSchema,
                    skip_cache=(attempt > 0)
                )
                
                # Force retry if the model gives up on generating test files
                if not result.generated_tests.generated_files:
                    raise ValueError("Model returned an empty generated_files list. You MUST generate at least one test file.")
                    
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"EngineeringAgent generation failed (attempt {attempt+1}/{max_retries}): {e}")
                import time
                time.sleep(3)
                
        raise ValueError(f"Failed to generate EngineeringSessionSchema after {max_retries} attempts. Last error: {last_error}")
