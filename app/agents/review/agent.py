from app.workflows.context import WorkflowContext
from app.services.llm_service import LLMService
from app.schemas.quality import ReviewReport
from app.utils.logger import logger
import json

class ReviewAgent:
    """Agent responsible for reviewing generated tests against execution results."""
    
    def __init__(self):
        self.llm_service = LLMService()
        
    def review_tests(self, context: WorkflowContext) -> ReviewReport:
        logger.info("Calling Review Agent...")
        if not context.validation_report:
            logger.warning("No ValidationReport found for ReviewAgent.")
            return ReviewReport(approved=True)
            
        system_prompt = "You are an AI Code Reviewer specializing in Test Quality.\nAnalyze the Validation Report and Generated Tests. Identify weak assertions, missing mocks, readability issues, and poor naming. Return structural reasoning ONLY."
        user_prompt = self._build_prompt(context)
        
        return self.llm_service.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=ReviewReport
        )
        
    def _build_prompt(self, context: WorkflowContext) -> str:
        lines = []
        lines.append("=== VALIDATION REPORT ===")
        val_dump = context.validation_report.model_dump()
        lines.append(json.dumps(val_dump, indent=2, default=str))
        
        lines.append("\n=== CURRENT TESTS ===")
        if context.generated_tests:
            try:
                for gen_file in context.generated_tests.generated_files:
                    lines.append(f"File: {gen_file.path}")
                    lines.append(f"```python\n{gen_file.content}\n```")
            except Exception as e:
                logger.error(f'An error occurred: {e}')
                lines.append(str(context.generated_tests))
        else:
            lines.append("No generated tests in context.")
            
        return "\n".join(lines)
