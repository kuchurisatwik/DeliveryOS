from pydantic import BaseModel, Field
from typing import List, Dict

class RetrievedSymbol(BaseModel):
    name: str
    type: str
    file_path: str
    body: str

class RetrievedTest(BaseModel):
    file_path: str
    body: str

class RepositoryContext(BaseModel):
    """The highly targeted structural context retrieved from SQLite based on the git diff."""
    target_symbols: List[RetrievedSymbol] = Field(default_factory=list, description="Directly modified classes/functions")
    dependencies: List[RetrievedSymbol] = Field(default_factory=list, description="Symbols used by the target symbols")
    related_tests: List[RetrievedTest] = Field(default_factory=list, description="Existing tests mapping to these symbols")
