from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class RetrievedSymbol(BaseModel):
    name: str
    type: str
    file_path: str
    body: str

class RetrievedTest(BaseModel):
    file_path: str
    body: str

class RelatedSymbol(BaseModel):
    """A symbol resolved from the call/dependency graph as related to the Changed_Feature.

    `relation` records HOW the symbol relates to a changed symbol:
      * "caller"   – it calls into the changed symbol (incoming call edge)
      * "callee"   – it is called by the changed symbol (outgoing call edge)
      * "imported" – it is a module/name imported by the changed file (dependency edge)
    """
    name: str
    qualified_name: Optional[str] = None
    type: str = "unknown"
    file_path: Optional[str] = None
    relation: str = "callee"
    import_path: Optional[str] = None

class SymbolReachability(BaseModel):
    """Per-symbol reachability signals derived from the call graph.

    These are raw inputs (counts + booleans) that Layer 3 enrichment consumes to
    derive its numeric `reachability` factor; they are intentionally not normalized
    here so enrichment owns the scoring policy.
    """
    symbol_name: str
    qualified_name: Optional[str] = None
    file_path: str
    caller_count: int = 0
    callee_count: int = 0
    has_callers: bool = False
    reachable_from_entrypoint: bool = False

class ChangedFeature(BaseModel):
    """The set of files, functions, and classes affected by the current commit,
    together with the symbols related to them via the call/dependency graph.

    Maps `context.changed_files` / `context.structured_diff` into the shape the
    security layers consume (Requirement 2.1, 2.4, 2.5)."""
    files: List[str] = Field(default_factory=list, description="Changed file paths")
    functions: List[RetrievedSymbol] = Field(default_factory=list, description="Changed function symbols")
    classes: List[RetrievedSymbol] = Field(default_factory=list, description="Changed class symbols")
    related_symbols: List[RelatedSymbol] = Field(default_factory=list, description="Callers/callees/imports related via the graphs")

class RepositoryContext(BaseModel):
    """The highly targeted structural context retrieved from SQLite based on the git diff."""
    target_symbols: List[RetrievedSymbol] = Field(default_factory=list, description="Directly modified classes/functions")
    dependencies: List[RetrievedSymbol] = Field(default_factory=list, description="Symbols used by the target symbols")
    related_tests: List[RetrievedTest] = Field(default_factory=list, description="Existing tests mapping to these symbols")

    # --- Security-pipeline additions (backward-compatible: all default to empty/None) ---
    related_symbols: List[RelatedSymbol] = Field(
        default_factory=list,
        description="Symbols related to the changed feature via the call/dependency graph (callers, callees, imported modules)",
    )
    reachability: List[SymbolReachability] = Field(
        default_factory=list,
        description="Per-symbol reachability inputs derived from the call graph, consumed by Layer 3 enrichment",
    )
    changed_feature: Optional[ChangedFeature] = Field(
        default=None,
        description="The Changed_Feature (files/functions/classes/related symbols) used by the security layers",
    )
