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

class SyntaxStatus(BaseModel):
    passed: bool = Field(description="True if syntax is valid")
    errors: List[str] = Field(default_factory=list, description="Syntax errors found")

class ImportStatus(BaseModel):
    passed: bool = Field(description="True if imports can be resolved")
    unresolved_imports: List[str] = Field(default_factory=list, description="List of unresolved imports")

class DependencyStatus(BaseModel):
    passed: bool = Field(description="True if all dependencies are present")
    missing_dependencies: List[str] = Field(default_factory=list, description="List of missing dependencies")

class LintStatus(BaseModel):
    passed: bool = Field(description="True if linting passed")
    warnings: List[str] = Field(default_factory=list, description="List of linting warnings/errors")

class TypeStatus(BaseModel):
    passed: bool = Field(description="True if type checking passed")
    errors: List[str] = Field(default_factory=list, description="List of type checking errors")

class ValidationReport(BaseModel):
    build_status: bool = Field(default=False, description="True if build/install passed")
    syntax_status: SyntaxStatus
    import_status: ImportStatus
    dependency_status: DependencyStatus
    lint_status: LintStatus
    type_status: TypeStatus
    execution_report: Optional[TestExecutionReport] = None
    coverage_report: Optional[CoverageReport] = None

class ReviewReport(BaseModel):
    weak_assertions: List[str] = Field(default_factory=list, description="Issues with weak or missing assertions")
    duplicate_tests: List[str] = Field(default_factory=list, description="Identified duplicate tests")
    poor_naming: List[str] = Field(default_factory=list, description="Tests with unclear naming conventions")
    readability_issues: List[str] = Field(default_factory=list, description="Issues with code readability or maintainability")
    missing_mocks: List[str] = Field(default_factory=list, description="Missing or incorrect mock implementations")
    approved: bool = Field(description="Whether the tests meet the review standards")

class CoverageAnalysis(BaseModel):
    missing_branches: List[str] = Field(default_factory=list, description="Branches that are not covered")
    missing_scenarios: List[str] = Field(default_factory=list, description="Logical scenarios missing from coverage")
    insufficient_edge_cases: List[str] = Field(default_factory=list, description="Edge cases that need to be added")
    unexecuted_apis: List[str] = Field(default_factory=list, description="API endpoints that were not exercised")

class ImprovementPlan(BaseModel):
    actions: List[str] = Field(default_factory=list, description="Deterministic list of actions to take to improve tests")

class PatchBlock(BaseModel):
    file_path: str = Field(description="The path to the file to modify")
    search_block: str = Field(default="", description="The exact block of code to search for and replace. If empty, the replace_block is appended to the file.")
    replace_block: str = Field(description="The code to replace the search_block with, or to append if search_block is empty.")

class PatchArtifact(BaseModel):
    patches: List[PatchBlock] = Field(default_factory=list, description="List of targeted patches to apply")

class GenerationFeedback(BaseModel):
    # Retaining for backward compatibility, but primarily using ImprovementPlan going forward
    failed_tests: List[str] = Field(default_factory=list, description="List of tests that failed during execution")
    missing_scenarios: List[str] = Field(default_factory=list, description="Scenarios missing based on coverage analysis")
    weak_assertions: List[str] = Field(default_factory=list, description="Assertions that need strengthening")
    coverage_gaps: List[str] = Field(default_factory=list, description="Specific files or lines lacking coverage")
    priority: str = Field(default="High", description="Priority of the feedback iteration")
