from pydantic import BaseModel, Field
from typing import List, Optional

class TestExecutionReport(BaseModel):
    passed: int = Field(default=0, description="Number of tests passed")
    failed: int = Field(default=0, description="Number of tests failed")
    errors: int = Field(default=0, description="Number of test errors")
    duration_seconds: float = Field(default=0.0, description="Execution time in seconds")
    stdout: str = Field(default="", description="Standard output from test runner")
    stderr: str = Field(default="", description="Standard error from test runner")
    exit_code: int = Field(default=0, description="Exit code of the test process")
    failed_test_names: List[str] = Field(default_factory=list, description="Names of failed tests")

class CoverageReport(BaseModel):
    total_lines: int = Field(default=0, description="Total executable lines")
    covered_lines: int = Field(default=0, description="Number of covered lines")
    missing_lines: int = Field(default=0, description="Number of uncovered lines")
    coverage_percentage: float = Field(default=0.0, description="Percentage of lines covered")
    missing_line_numbers: List[str] = Field(default_factory=list, description="List of missing lines or line ranges per file")

class ReviewReport(BaseModel):
    weak_assertions: List[str] = Field(default_factory=list, description="Issues with weak or missing assertions")
    duplicate_tests: List[str] = Field(default_factory=list, description="Identified duplicate tests")
    poor_naming: List[str] = Field(default_factory=list, description="Tests with unclear naming conventions")
    readability_issues: List[str] = Field(default_factory=list, description="Issues with code readability or maintainability")
    missing_mocks: List[str] = Field(default_factory=list, description="Missing or incorrect mock implementations")
    approved: bool = Field(description="Whether the tests meet the review standards")

class CoverageImprovementPlan(BaseModel):
    missing_branches: List[str] = Field(default_factory=list, description="Branches that are not covered")
    missing_scenarios: List[str] = Field(default_factory=list, description="Logical scenarios missing from coverage")
    insufficient_edge_cases: List[str] = Field(default_factory=list, description="Edge cases that need to be added")
    unexecuted_apis: List[str] = Field(default_factory=list, description="API endpoints that were not exercised")

class GenerationFeedback(BaseModel):
    failed_tests: List[str] = Field(default_factory=list, description="List of tests that failed during execution")
    missing_scenarios: List[str] = Field(default_factory=list, description="Scenarios missing based on coverage analysis")
    weak_assertions: List[str] = Field(default_factory=list, description="Assertions that need strengthening")
    coverage_gaps: List[str] = Field(default_factory=list, description="Specific files or lines lacking coverage")
    priority: str = Field(default="High", description="Priority of the feedback iteration")
