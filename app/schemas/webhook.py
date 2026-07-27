from pydantic import BaseModel, Field
from typing import Any, Dict

class RepositorySchema(BaseModel):
    name: str
    full_name: str
    clone_url: str

class PushEventSchema(BaseModel):
    ref: str
    before: str
    after: str
    repository: RepositorySchema
    # Using Any to catch the rest of the payload without strict validation
    pusher: Dict[str, Any] = Field(default_factory=dict)
    sender: Dict[str, Any] = Field(default_factory=dict)
    # Set by the manual "Scan whole repo" trigger from the UI to force a full-repo
    # scan for this run regardless of SECURITY_SCAN_SCOPE. Never set by GitHub.
    force_full_scope: bool = Field(default=False)
