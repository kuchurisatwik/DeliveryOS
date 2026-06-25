from app.workflows.context import WorkflowContext
from app.services.llm_service import LLMService
from app.schemas.generated_test import GeneratedTestArtifact
from .context_builder import ContextBuilder
from .validator import Validator
from .formatter import Formatter
from .confidence import ConfidenceEvaluator

class TestGenerationAgent:
    """The core Test Generation Agent acting as a Senior SDET."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.context_builder = ContextBuilder()
        self.validator = Validator()
        self.formatter = Formatter()
        self.confidence_evaluator = ConfidenceEvaluator()
        
    def generate_tests(self, context: WorkflowContext) -> GeneratedTestArtifact:
        prompt = self.context_builder.build_prompt(context)
        
        max_retries = 3
        last_exception = None
        
        for _ in range(max_retries):
            try:
                # LLM execution
                result = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=GeneratedTestArtifact
                )
                
                # Validation
                valid_result = self.validator.validate(result)
                
                # Formatting
                formatted_result = self.formatter.format(valid_result)
                
                # Confidence evaluation
                warnings = self.confidence_evaluator.evaluate(formatted_result)
                if warnings:
                    formatted_result.warnings.extend(warnings)
                    
                return formatted_result
                
            except Exception as e:
                last_exception = e
                
        raise ValueError(f"Test Generation Agent failed after {max_retries} retries: {last_exception}")
