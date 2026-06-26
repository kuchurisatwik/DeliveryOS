from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from app.schemas.test_plan import TestPlanSchema

class ChangeSummarySchema(BaseModel):
    summary: str = Field(description="Summary of the changes")
    feature_type: str = Field(description="Type of feature (e.g., Bugfix, Feature, Refactor)")
    risk_level: str = Field(description="Risk level (Low, Medium, High)")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    affected_modules: List[str] = Field(description="List of affected module names")
    affected_services: List[str] = Field(description="List of affected services")
    affected_routes: List[str] = Field(description="List of affected API routes")
    affected_database_tables: List[str] = Field(description="List of affected database tables")
    breaking_change: bool = Field(description="Whether this introduces breaking changes")
    architecture_impact: str = Field(description="Impact on the overall architecture")
    reasoning: str = Field(description="Reasoning for the analysis")

class WorkflowContext(BaseModel):
    """Data object passed between all workflow stages."""
    repository: str = Field(description="Full name of the repository (e.g., owner/repo)")
    repo_name: str = Field(description="Name of the repository")
    clone_url: str = Field(description="URL to clone the repository")
    branch: str = Field(description="The branch to operate on")
    commit_sha: str = Field(description="The commit SHA that triggered the workflow")
    
    workspace: Optional[str] = Field(None, description="Path to the local cloned repository")
    changed_files: List[str] = Field(default_factory=list, description="List of files changed in the commit")
    ai_branch_name: Optional[str] = Field(None, description="Name of the newly created branch for AI changes")
    
    # Phase 3: Repository Intelligence Data
    structured_diff: Dict[str, Any] = Field(default_factory=lambda: {"added": [], "modified": [], "deleted": [], "renamed": []}, description="Structured git diff")
    file_categories: Dict[str, List[str]] = Field(default_factory=dict, description="Categorized changed files")
    extracted_metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted code metadata")
    llm_context: str = Field("", description="Compact context string for the LLM")
    change_summary: Optional[ChangeSummarySchema] = Field(None, description="LLM generated summary of changes")
    
    repository_language: Optional[str] = Field(None, description="Detected primary language")
    framework: Optional[str] = Field(None, description="Detected framework")
    
    # Phase 4: Test Planning Data
    test_plan: Optional[TestPlanSchema] = Field(None, description="Test plan from planning agent")
    planning_confidence: float = Field(0.0, description="Confidence of the generated test plan")
    planning_summary: str = Field("", description="Summary of the test planning phase")
    planning_warnings: List[str] = Field(default_factory=list, description="Warnings from test planning")
    recommended_test_levels: Optional[Any] = Field(None, description="Recommended test levels")
    
    # Phase 5: Test Generation Data
    generated_tests: Optional[Any] = Field(None, description="The full GeneratedTestArtifact")
    generated_files_count: int = Field(0, description="Number of files generated")
    generated_test_framework: Optional[str] = Field(None, description="Testing framework used for generation")
    generation_confidence: float = Field(0.0, description="Confidence of the generation")
    generation_warnings: List[str] = Field(default_factory=list, description="Warnings from generation")
    workspace_changes: List[str] = Field(default_factory=list, description="List of paths written to the workspace")
    
    # Phase 6: Validation & Improvement Engine Data
    validation_report: Optional[Any] = Field(None, description="Aggregated validation report from all deterministic services")
    review_report: Optional[Any] = Field(None, description="Review report from ReviewAgent")
    coverage_analysis: Optional[Any] = Field(None, description="Coverage analysis from CoverageAnalysisAgent")
    improvement_plan: Optional[Any] = Field(None, description="Deterministic plan for test improvement")
    patch_artifact: Optional[Any] = Field(None, description="Targeted patch instructions from TestImprovementAgent")
    iteration_history: List[Any] = Field(default_factory=list, description="History of patch iterations to preserve artifacts")
    iteration_count: int = Field(1, description="Current improvement iteration loop")
    merge_confidence: float = Field(0.0, description="Overall confidence (0-100) to merge this commit")
    
    pr_url: Optional[str] = Field(None, description="URL of the created pull request")
    status: str = Field("INITIALIZED", description="Current status of the workflow")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated during workflow")
