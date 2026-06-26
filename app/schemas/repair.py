from pydantic import BaseModel, Field
from typing import List

class PatchBlock(BaseModel):
    file_path: str = Field(description="The path to the file to modify")
    search_block: str = Field(default="", description="The exact block of code to search for and replace. If empty, the replace_block is appended to the file.")
    replace_block: str = Field(description="The code to replace the search_block with, or to append if search_block is empty.")

class RepairSessionSchema(BaseModel):
    """
    The unified result of the Repair Session.
    Takes the deterministic ValidationReport and generates targeted patches.
    """
    reasoning: str = Field(description="The AI's reasoning for why tests failed and how to fix them based on the validation report.")
    patches: List[PatchBlock] = Field(default_factory=list, description="List of targeted patches to apply to fix the issues.")
