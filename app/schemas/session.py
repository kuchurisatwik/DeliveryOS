from pydantic import BaseModel, Field


from app.workflows.context import ChangeSummarySchema
from app.schemas.test_plan import TestPlanSchema
from app.schemas.generated_test import GeneratedTestArtifact

class EngineeringSessionSchema(BaseModel):
    """
    The unified result of the Engineering Session.
    Combines Repository Understanding, Test Planning, and Test Generation
    into a single structured AI response.
    """
    change_summary: ChangeSummarySchema = Field(description="The analysis of the requested feature or bugfix.")
    test_plan: TestPlanSchema = Field(description="The deterministic plan of exactly what needs to be tested.")
    generated_tests: GeneratedTestArtifact = Field(description="The physical files and code to write to the repository.")
