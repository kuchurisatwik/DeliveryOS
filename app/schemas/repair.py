from pydantic import BaseModel, Field
from typing import List

class RepairedFile(BaseModel):
    file_path: str = Field(description="The path to the file to modify")
    content: str = Field(description="The complete, regenerated content of the file. This will entirely overwrite the existing file.")

class RepairSessionSchema(BaseModel):
    """
    The unified result of the Repair Session.
    Takes the deterministic ValidationReport and generates complete repaired files.
    """
    reasoning: str = Field(description="The AI's reasoning for why tests failed and how to fix them based on the validation report.")
    repaired_files: List[RepairedFile] = Field(default_factory=list, description="List of completely regenerated files.")
