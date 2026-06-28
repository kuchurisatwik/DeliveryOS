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
        
        # Section 3: Git Diff (the actual code changes — the PRIMARY signal)
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
                            
        # Section 4: FULL SOURCE CODE of changed files (CRITICAL for context)
        if context.workspace and context.changed_files:
            lines.append("\n=== FULL SOURCE CODE (CHANGED FILES) ===")
            for file_rel in context.changed_files:
                if file_rel.endswith(".py"):
                    full_path = os.path.join(context.workspace, file_rel)
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            lines.append(f"\n--- {file_rel} ---")
                            lines.append(content)
                        except Exception:
                            pass
        
        # Section 5: EXISTING TEST FILES (so AI matches patterns, fixtures, conftest)
        if context.workspace:
            lines.append("\n=== EXISTING TEST FILES (MATCH THESE PATTERNS) ===")
            test_dirs = [
                os.path.join(context.workspace, "tests"),
                os.path.join(context.workspace, "test"),
            ]
            test_files_found = 0
            for test_dir in test_dirs:
                if os.path.isdir(test_dir):
                    for root, _, files in os.walk(test_dir):
                        for fname in sorted(files):
                            if fname.endswith(".py") and test_files_found < 5:
                                test_path = os.path.join(root, fname)
                                rel = os.path.relpath(test_path, context.workspace).replace("\\", "/")
                                try:
                                    with open(test_path, "r", encoding="utf-8") as f:
                                        content = f.read()
                                    if len(content) < 8000:
                                        lines.append(f"\n--- {rel} ---")
                                        lines.append(content)
                                        test_files_found += 1
                                except Exception:
                                    pass
            
            # Also check for conftest.py at root
            conftest = os.path.join(context.workspace, "conftest.py")
            if os.path.exists(conftest):
                try:
                    with open(conftest, "r", encoding="utf-8") as f:
                        lines.append("\n--- conftest.py ---")
                        lines.append(f.read())
                except Exception:
                    pass

        # Section 6: Critical Rules at the END (Recency Bias — LLM remembers what it read last)
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
                    schema=EngineeringSessionSchema
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"EngineeringAgent generation failed (attempt {attempt+1}/{max_retries}): {e}")
                
        raise ValueError(f"Failed to generate EngineeringSessionSchema after {max_retries} attempts. Last error: {last_error}")
