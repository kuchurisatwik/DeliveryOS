from app.workflows.context import WorkflowContext
from app.services.llm_service import LLMService
from app.schemas.test_plan import TestPlanSchema
from .prompt_builder import PromptBuilder
from .validator import JSONValidator
from .confidence import ConfidenceEvaluator

class TestPlannerAgent:
    """The core Test Planning Agent that coordinates the pipeline."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.prompt_builder = PromptBuilder()
        self.validator = JSONValidator()
        self.confidence_evaluator = ConfidenceEvaluator()
        
    def generate_plan(self, context: WorkflowContext) -> TestPlanSchema:
        prompt = self.prompt_builder.build_prompt(context)
        
        max_retries = 3
        last_exception = None
        
        for _ in range(max_retries):
            try:
                # LLM execution
                result = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=TestPlanSchema
                )
                
                # Validation
                valid_result = self.validator.validate(result)
                
                # Confidence Check
                warnings = self.confidence_evaluator.evaluate(valid_result)
                context.planning_warnings.extend(warnings)
                
                return valid_result
            except Exception as e:
                last_exception = e
                
        raise ValueError(f"Test Planning Agent failed after {max_retries} retries: {last_exception}")
