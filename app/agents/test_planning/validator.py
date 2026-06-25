from app.schemas.test_plan import TestPlanSchema

class JSONValidator:
    """Validates that the output matches the required test plan schema."""
    
    # In this specific architecture, Pydantic handles validation,
    # but this class serves as the abstraction layer in case we 
    # introduce more complex business validation rules.
    
    def validate(self, result: any) -> TestPlanSchema:
        if not isinstance(result, TestPlanSchema):
            raise ValueError(f"Expected TestPlanSchema, got {type(result)}")
        return result
