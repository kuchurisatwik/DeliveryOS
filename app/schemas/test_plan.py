from pydantic import BaseModel, Field
from typing import List, Optional

class TestScenarioSchema(BaseModel):
    scenario_name: str = Field(description="Name of the test scenario")
    purpose: str = Field(description="Purpose of the test")
    priority: str = Field(description="Priority (High, Medium, Low)")
    expected_behaviour: str = Field(description="Expected outcome of the test")
    category: str = Field(description="Category (e.g., Success, Validation Failure, Auth Failure, Edge Case)")

class RecommendedTestLevelsSchema(BaseModel):
    unit: bool = Field(description="Whether unit tests are recommended")
    integration: bool = Field(description="Whether integration tests are recommended")
    api: bool = Field(description="Whether API tests are recommended")
    e2e: bool = Field(description="Whether End-to-End tests are recommended")

class TestPlanSchema(BaseModel):
    summary: str = Field(description="Summary of the overall test plan")
    overall_risk: str = Field(description="Overall risk level evaluated for testing")
    confidence: float = Field(description="Confidence score in the test plan (0.0 to 1.0)")
    
    recommended_test_levels: RecommendedTestLevelsSchema = Field(description="Recommended levels of testing")
    
    unit_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="Unit testing scenarios")
    integration_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="Integration testing scenarios")
    api_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="API testing scenarios")
    negative_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="Negative testing scenarios")
    boundary_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="Boundary/Edge case scenarios")
    security_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="Security testing scenarios")
    performance_test_scenarios: List[TestScenarioSchema] = Field(default_factory=list, description="Performance testing scenarios")
    
    regression_areas: List[str] = Field(default_factory=list, description="Areas to check for regression")
    mock_dependencies: List[str] = Field(default_factory=list, description="Dependencies that require mocking")
    external_services: List[str] = Field(default_factory=list, description="External services involved")
    required_test_data: List[str] = Field(default_factory=list, description="Specific data needed for testing")
    priority: str = Field(description="Overall priority of testing this feature")
