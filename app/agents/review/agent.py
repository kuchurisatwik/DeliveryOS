from app.workflows.context import WorkflowContext
from app.services.llm_service import LLMService
from app.schemas.quality import ReviewReport

class ReviewAgent:
    """Agent responsible for reviewing generated tests against execution results."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
    def review_tests(self, context: WorkflowContext) -> ReviewReport:
        if not context.generated_tests or not context.test_execution_report:
            raise ValueError("ReviewAgent requires both generated tests and an execution report.")
            
        prompt = self._build_prompt(context)
        
        return self.llm_service.generate_structured_json(
            prompt=prompt,
            schema=ReviewReport
        )
        
    def _build_prompt(self, context: WorkflowContext) -> str:
        lines = []
        lines.append("You are an AI Code Reviewer specializing in Test Quality.")
        lines.append("Analyze the provided Generated Tests and their Execution Report.")
        lines.append("Identify weak assertions, duplicated tests, poor naming, or missing mocks.")
        lines.append("\n=== EXECUTION REPORT ===")
        lines.append(f"Passed: {context.test_execution_report.passed}")
        lines.append(f"Failed: {context.test_execution_report.failed}")
        lines.append(f"Errors: {context.test_execution_report.errors}")
        lines.append(f"Stdout:\n{context.test_execution_report.stdout[:2000]}") # Truncate stdout to fit context
        
        lines.append("\n=== GENERATED TESTS ===")
        for gen_file in context.generated_tests.generated_files:
            lines.append(f"File: {gen_file.path}")
            lines.append(f"```python\n{gen_file.content}\n```")
            
        return "\n".join(lines)
