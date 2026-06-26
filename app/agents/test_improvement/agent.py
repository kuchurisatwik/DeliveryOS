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
            except Exception as e:
                logger.error(f'An error occurred: {e}')
                current_tests = str(context.generated_tests)
        
        user_prompt = TEST_IMPROVEMENT_USER_PROMPT.format(
            improvement_plan=improvement_plan_text,
            current_tests=current_tests,
            repo_analysis=repo_analysis_text
        )
        
        response = self.llm_service.call_llm(
            system_prompt=TEST_IMPROVEMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=PatchArtifact
        )
        
        logger.info("Test Improvement Agent successfully generated patches.")
        return response
