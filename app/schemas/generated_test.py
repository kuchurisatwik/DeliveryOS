from pydantic import BaseModel, Field
from typing import List

class GeneratedFile(BaseModel):
    path: str = Field(description="Relative path within the workspace where the file should be written")
    language: str = Field(description="Programming language of the generated file")
    content: str = Field(description="The complete source code of the file")

class GeneratedTestArtifact(BaseModel):
    framework: str = Field(description="The testing framework used (e.g., pytest, jest)")
    generated_files: List[GeneratedFile] = Field(description="List of files to be written to the workspace")
    new_fixtures: List[str] = Field(default_factory=list, description="Names of new fixtures created")
    mock_objects: List[str] = Field(default_factory=list, description="List of dependencies mocked")
    external_dependencies: List[str] = Field(default_factory=list, description="Required dependencies (e.g., pip/npm packages)")
    warnings: List[str] = Field(default_factory=list, description="Warnings or caveats regarding the generated tests")
    confidence: float = Field(description="Confidence score of the generated tests between 0.0 and 1.0")
