from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class MethodSignature(BaseModel):
    name: str
    args: List[str]
    returns: Optional[str] = None
    is_async: bool = False

class ClassSignature(BaseModel):
    name: str
    methods: List[MethodSignature]
    bases: List[str]
    docstring: Optional[str] = None

class RouteSignature(BaseModel):
    method: str
    path: str
    handler: str

class FixtureSignature(BaseModel):
    name: str
    scope: str = "function"

class RepositoryKnowledge(BaseModel):
    language: str = Field(default="python")
    framework: Optional[str] = None
    testing_framework: str = Field(default="pytest")
    
    # Indexes mapping file paths (or module paths) to lists of objects
    class_index: Dict[str, List[ClassSignature]] = Field(default_factory=dict)
    method_index: Dict[str, List[MethodSignature]] = Field(default_factory=dict) # Free functions
    route_index: Dict[str, List[RouteSignature]] = Field(default_factory=dict)
    fixture_index: Dict[str, List[FixtureSignature]] = Field(default_factory=dict)
    exception_index: Dict[str, List[ClassSignature]] = Field(default_factory=dict)
    model_index: Dict[str, List[ClassSignature]] = Field(default_factory=dict)
    
    # Simple dependency tracking mapping file -> list of imported modules/classes
    imports_index: Dict[str, List[str]] = Field(default_factory=dict)
    
    # Differential caching
    mtimes: Dict[str, float] = Field(default_factory=dict)
