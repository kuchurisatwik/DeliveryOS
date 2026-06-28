import os
import re
from app.workflows.context import WorkflowContext
from app.schemas.repair import RepairSessionSchema
from app.services.llm_service import LLMService
from app.utils.logger import logger

class RepairAgent:
    """The unified Repair Agent. 
    Feeds iteration history and structured failure summaries for reliable convergence.
    """
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.prompt_template = ""
        prompt_path = os.path.join(os.getcwd(), "app", "prompts", "repair_session.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
                
    def _extract_failure_summary(self, context: WorkflowContext) -> str:
        """Pre-processes the validation report into a concise, structured failure summary
        instead of dumping the entire JSON blob."""
        val = context.validation_report
        if not val:
            return "No validation report available."
            
        lines = []
        
        # Build status
        lines.append(f"Build Status: {'PASS' if val.build_status else 'FAIL'}")
        if not val.syntax_status.passed:
            lines.append(f"Syntax Errors: {'; '.join(val.syntax_status.errors)}")
        if not val.import_status.passed:
            lines.append(f"Import Errors: {'; '.join(val.import_status.unresolved_imports)}")
            
        # Test execution — the most important part
        if val.execution_report:
            er = val.execution_report
            lines.append(f"\nTest Results: {er.passed} passed, {er.failed} failed, {er.errors} errors (exit code {er.exit_code})")
            
            if er.failed_test_names:
                lines.append("\nFailed Tests:")
                for name in er.failed_test_names:
                    lines.append(f"  - {name}")
            
            # Extract only the FAILURES and ERRORS sections from pytest stdout
            if er.stdout:
                # Get the short test summary and any tracebacks
                failure_section = ""
                in_failures = False
                for line in er.stdout.split("\n"):
                    if "FAILURES" in line or "ERRORS" in line or "short test summary" in line:
                        in_failures = True
                    if in_failures:
                        failure_section += line + "\n"
                
                if failure_section:
                    lines.append(f"\nPytest Failure Details:\n{failure_section[:5000]}")
                    
            if er.stderr and er.stderr.strip():
                lines.append(f"\nStderr:\n{er.stderr[:2000]}")
        
        # Coverage
        if val.coverage_report:
            lines.append(f"\nCoverage: {val.coverage_report.coverage_percentage:.1f}%")
            
        return "\n".join(lines)
    
    def _format_iteration_history(self, context: WorkflowContext) -> str:
        """Formats previous repair attempts so the LLM knows what was already tried."""
        if not context.iteration_history:
            return ""
            
        lines = ["\n=== PREVIOUS REPAIR ATTEMPTS (DO NOT REPEAT THESE) ==="]
        for i, patch_artifact in enumerate(context.iteration_history):
            lines.append(f"\n--- Attempt {i+1} ---")
            for p in patch_artifact.patches:
                lines.append(f"File: {p.file_path}")
                if p.search_block:
                    lines.append(f"Search: {p.search_block[:200]}...")
                lines.append(f"Replace: {p.replace_block[:200]}...")
        
        lines.append("\nThese previous attempts FAILED. Try a different approach.")
        return "\n".join(lines)
                
    def conduct_session(self, context: WorkflowContext) -> RepairSessionSchema:
        lines = []
        lines.append(self.prompt_template)
        
        # Structured failure summary instead of raw JSON dump
        lines.append("\n=== VALIDATION REPORT (STRUCTURED) ===")
        lines.append(self._extract_failure_summary(context))
        
        # Previous iteration history
        history = self._format_iteration_history(context)
        if history:
            lines.append(history)
            
        # Generated test source code
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
        
        # Original changed files context
        if context.workspace and context.changed_files:
            lines.append("\n=== ORIGINAL CHANGED SOURCE CODE ===")
            for file_rel in context.changed_files:
                full_path = os.path.join(context.workspace, file_rel)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            lines.append(f"\n--- {file_rel} ---")
                            lines.append(f.read())
                    except Exception:
                        pass
        
        # Critical rules at the end (recency bias)
        lines.append("\n=== REMINDER ===")
        lines.append("You may ONLY patch files in the tests/ directory. NEVER modify production code under app/.")
        lines.append("Return strictly valid JSON matching the schema provided.")
                        
        prompt = "\n".join(lines)
        
        logger.info(f"Executing unified Repair Agent... (prompt size: {len(prompt)} chars)")
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                result: RepairSessionSchema = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=RepairSessionSchema,
                    skip_cache=True  # Never cache repair sessions
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"RepairAgent generation failed (attempt {attempt+1}/{max_retries}): {e}")
                
        raise ValueError(f"Failed to generate RepairSessionSchema after {max_retries} attempts. Last error: {last_error}")
