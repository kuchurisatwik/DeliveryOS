import json
from app.services.llm_service import LLMService
from app.schemas.quality import PatchArtifact
from app.agents.test_improvement.prompts import (
    TEST_IMPROVEMENT_SYSTEM_PROMPT,
    TEST_IMPROVEMENT_USER_PROMPT
)
from app.workflows.context import WorkflowContext
from app.utils.logger import logger

class TestImprovementAgent:
    def __init__(self):
        self.llm_service = LLMService()
        
    def generate_patches(self, context: WorkflowContext) -> PatchArtifact:
        logger.info("Calling Test Improvement Agent (Senior Test Engineer)...")
        
        improvement_plan_text = json.dumps(context.improvement_plan.model_dump(), indent=2) if context.improvement_plan else "[]"
        repo_analysis_text = json.dumps(context.change_summary.model_dump(), indent=2) if context.change_summary else "{}"
        
        # We need the current state of tests. If not natively in context, we could fetch from workspace,
        # but context.generated_tests usually has the initial raw strings. We'll use a stringified version.
        current_tests = "No existing tests passed in context."
        if context.generated_tests:
            # Assuming generated_tests is an object with a 'files' array
            try:
                current_tests = json.dumps(context.generated_tests.model_dump(), indent=2)
            except Exception:
                current_tests = str(context.generated_tests)
                current_tests = str(context.generated_tests)
                
        execution_logs = ""
        if context.validation_report:
            vr = context.validation_report
            logs = []
            if vr.execution_report:
                logs.append(f"Pytest stdout:\n{vr.execution_report.stdout}")
                logs.append(f"Pytest stderr:\n{vr.execution_report.stderr}")
            if not vr.type_status.passed:
                logs.append("Mypy Errors:\n" + "\n".join(vr.type_status.errors))
            if not vr.lint_status.passed:
                logs.append("Ruff Warnings:\n" + "\n".join(vr.lint_status.warnings))
            execution_logs = "\n\n".join(logs)
            
        repo_knowledge = "{}"
        if context.repository_knowledge:
            repo_knowledge = context.repository_knowledge.model_dump_json(indent=2)
        
        user_prompt = TEST_IMPROVEMENT_USER_PROMPT.format(
            improvement_plan=improvement_plan_text,
            current_tests=current_tests,
            repo_analysis=repo_analysis_text,
            execution_logs=execution_logs,
            repo_knowledge=repo_knowledge
        )
        
        full_prompt = TEST_IMPROVEMENT_SYSTEM_PROMPT + "\n\n" + user_prompt
        
        response = self.llm_service.generate_structured_json(
            prompt=full_prompt,
            schema=PatchArtifact
        )
        
        logger.info("Test Improvement Agent successfully generated patches.")
        return response
