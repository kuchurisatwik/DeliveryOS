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

class EngineeringTask(BaseModel):
    """Represents a single, focused feature engineering task."""
    feature_name: str = Field(description="The deterministic name of the feature (e.g., 'payment')")
    related_files: List[str] = Field(default_factory=list, description="List of changed file paths belonging to this feature")
    structured_diff: Dict[str, Any] = Field(default_factory=lambda: {"added": [], "modified": [], "deleted": [], "renamed": []}, description="Diff isolated to this task's files")

class WorkflowContext(BaseModel):
    """Data object passed between all workflow stages."""
    repository: str = Field(description="Full name of the repository (e.g., owner/repo)")
    repo_name: str = Field(description="Name of the repository")
    clone_url: str = Field(description="URL to clone the repository")
    branch: str = Field(description="The branch to operate on")
    commit_sha: str = Field(description="The commit SHA that triggered the workflow")
    
    workspace: Optional[str] = Field(None, description="Path to the local cloned repository")
    changed_files: List[str] = Field(default_factory=list, description="List of all files changed in the commit")
    ai_branch_name: Optional[str] = Field(None, description="Name of the newly created branch for AI changes")
    
    # Phase 2.5: Task Planning
    tasks: List[EngineeringTask] = Field(default_factory=list, description="Queue of engineering tasks decomposed from the commit")
    current_task: Optional[EngineeringTask] = Field(None, description="The specific task currently being processed by the loop")
    
    # Phase 3: Repository Intelligence Data
    structured_diff: Dict[str, Any] = Field(default_factory=lambda: {"added": [], "modified": [], "deleted": [], "renamed": []}, description="Structured git diff for the entire commit")
    file_categories: Dict[str, List[str]] = Field(default_factory=dict, description="Categorized changed files")
    extracted_metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted code metadata")
    retrieved_knowledge: Optional[Any] = Field(None, description="Structured Retrieved Context object from SQLite for the current task")
    llm_context: str = Field("", description="Compact context string for the LLM")
    change_summary: Optional[ChangeSummarySchema] = Field(None, description="LLM generated summary of changes")
    engineering_session: Optional[Any] = Field(None, description="Unified engineering session result")
    
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
    repaired_artifact: Optional[Any] = Field(None, description="Completely regenerated files from TestImprovementAgent")
    iteration_history: List[Any] = Field(default_factory=list, description="History of patch iterations to preserve artifacts")
    iteration_count: int = Field(1, description="Current improvement iteration loop")
    merge_confidence: float = Field(0.0, description="Overall confidence (0-100) to merge this commit")

    # Security Pipeline — Layer 2 Detection
    detection_result: Optional[Any] = Field(None, description="Layer 2 DetectionResult: aggregated Findings + per-scanner coverage")

    # Security Pipeline — Layer 3 Intelligence
    intelligence_result: Optional[Any] = Field(None, description="Layer 3 IntelligenceResult: findings partitioned into fixed and remaining")

    # Security Pipeline — Layer 4 Governance
    quality_gate: Optional[Any] = Field(None, description="Layer 4 Quality_Gate evaluation result (status + unsatisfied thresholds)")
    security_merge_confidence: Optional[Any] = Field(None, description="Layer 4 advisory Merge_Confidence for the security pipeline")
    config_substitutions: List[Any] = Field(default_factory=list, description="Repo_Config substitutions applied when malformed values were replaced by defaults (15.2)")
    resolved_config: Optional[Any] = Field(None, description="Immutable Repo_Config ResolvedConfig (thresholds/scanner rules/pipeline settings) resolved before Detection runs (1.5)")
    security_report: Optional[Any] = Field(None, description="Assembled Layer 4 Pull_Request_Report for the security pipeline")
    security_remediation_guide: List[Any] = Field(default_factory=list, description="Batch-triage remediation guide: list of (RuleGroup, RuleAnalysis) for HIGH/CRITICAL findings")
    security_deterministic_guide: List[Any] = Field(default_factory=list, description="Deterministic (no-AI) canned remediation for MEDIUM/LOW rule-groups")
    failed_layer: Optional[str] = Field(None, description="Name of the security layer that terminated with an unrecoverable error; set by layer-failure containment so the report records which layer failed (1.4)")
    security_scan_scope_mode: Optional[str] = Field(None, description="Actual resolved security scan scope for this run ('full' or 'commit'); captured at detection time so the report labels it correctly even after 'auto' onboarding marks the repo scanned")

    pr_url: Optional[str] = Field(None, description="URL of the created pull request")
    status: str = Field("INITIALIZED", description="Current status of the workflow")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated during workflow")
