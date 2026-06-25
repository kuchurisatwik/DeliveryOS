from pydantic import BaseModel, Field
from typing import List, Dict, Any

class WorkflowResult(BaseModel):
    """Result object returned by the WorkflowOrchestrator."""
    status: str = Field(description="SUCCESS or FAILED")
    duration: float = Field(description="Total execution time in seconds")
    completed_stages: List[str] = Field(default_factory=list, description="List of stages that completed successfully")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered during execution")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
