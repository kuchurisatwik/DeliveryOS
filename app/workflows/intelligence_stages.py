

from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext, ChangeSummarySchema


from app.services.llm_service import LLMService
from app.services.knowledge_aggregator import RepositoryKnowledgeAggregator

class GitDiffCollectorStage(Stage):
    """Step 1: Collects the structured git diff."""
    from app.services.git_service import GitService
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set.")
        context.structured_diff = self.git_service.get_commit_diff(context.workspace, context.commit_sha)

class FileClassifierStage(Stage):
    """Step 2: Classifies changed files by type."""
    def execute(self, context: WorkflowContext) -> None:
        categories = {
            "Backend": [],
            "Frontend": [],
            "Infrastructure": [],
            "Documentation": [],
            "Configuration": [],
            "Database": []
        }
        
        # Look at all added and modified files
        for f in context.structured_diff.get("added", []) + context.structured_diff.get("modified", []):
            path = f["path"]
            if path.endswith(".py") or path.endswith(".java") or path.endswith(".go"):
                categories["Backend"].append(path)
            elif path.endswith(".js") or path.endswith(".ts") or path.endswith(".jsx") or path.endswith(".tsx") or path.endswith(".css"):
                categories["Frontend"].append(path)
            elif "docker" in path.lower() or path.endswith(".tf") or path.endswith(".yml") or path.endswith(".yaml"):
                if ".github/workflows" in path:
                    categories["Infrastructure"].append(path)
                else:
                    categories["Configuration"].append(path)
            elif path.endswith(".md") or path.endswith(".txt"):
                categories["Documentation"].append(path)
            elif path.endswith(".sql"):
                categories["Database"].append(path)
                
        context.file_categories = categories

class MetadataExtractorStage(Stage):
    """Step 3: Extracts software metadata deterministically."""
    def __init__(self, aggregator: RepositoryKnowledgeAggregator):
        self.aggregator = aggregator
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set for MetadataExtractorStage.")
            
        knowledge = self.aggregator.build_or_load(context.workspace, context.commit_sha)
        context.repository_knowledge = knowledge
        
        # Keep minimal backward compatibility for extracted_metadata
        context.extracted_metadata = {
            "functions": [],
            "classes": [],
            "routes": [],
            "decorators": []
        }
        for file in context.changed_files:
            if file in knowledge.class_index:
                context.extracted_metadata["classes"].extend([c.name for c in knowledge.class_index[file]])
            if file in knowledge.route_index:
                context.extracted_metadata["routes"].extend([r.path for r in knowledge.route_index[file]])

class ContextBuilderStage(Stage):
    """Step 4: Builds a compact string for the LLM."""
    def execute(self, context: WorkflowContext) -> None:
        # Build a concise representation
        lines = []
        lines.append(f"Repository: {context.repository}")
        lines.append(f"Commit: {context.commit_sha}")
        lines.append(f"Detected Framework: {context.framework or 'Unknown'}")
        
        lines.append("\n## Changed Files")
        if context.changed_files:
            for f in context.changed_files:
                lines.append(f"  - {f}")
        else:
            lines.append("  (none detected)")
        
        lines.append("\n## File Categories")
        for category, files in context.file_categories.items():
            if files:
                lines.append(f"- {category}: {', '.join(files)}")
                
        # Build a combined set of target files from both changed_files AND structured_diff
        target_files = list(context.changed_files) if context.changed_files else []
        for change_type in ["added", "modified"]:
            for f in context.structured_diff.get(change_type, []):
                path = f.get("path", "")
                if path and path not in target_files:
                    target_files.append(path)
                
        lines.append("\n## Extracted Metadata (Added/Modified)")
        # Re-extract from target_files to ensure we always have data
        classes_found = []
        routes_found = []
        functions_found = []
        if context.repository_knowledge:
            for f in target_files:
                if f in context.repository_knowledge.class_index:
                    classes_found.extend([c.name for c in context.repository_knowledge.class_index[f]])
                if f in context.repository_knowledge.route_index:
                    routes_found.extend([r.path for r in context.repository_knowledge.route_index[f]])
                if f in context.repository_knowledge.method_index:
                    functions_found.extend([m.name for m in context.repository_knowledge.method_index[f]])
        
        lines.append(f"- New Routes: {', '.join(routes_found) or 'None'}")
        lines.append(f"- New Classes: {', '.join(classes_found) or 'None'}")
        lines.append(f"- New Functions: {', '.join(functions_found) or 'None'}")
        
        # Also update context.extracted_metadata for backward compat
        context.extracted_metadata = {
            "functions": functions_found,
            "classes": classes_found,
            "routes": routes_found,
            "decorators": []
        }
        
        lines.append("\n## Diff Highlights")
        for f in context.structured_diff.get("added", []):
            lines.append(f"\n[ADDED] {f['path']}")
            lines.append(f['diff'][:2000])  # increased from 1000 to 2000
            
        for f in context.structured_diff.get("modified", []):
            lines.append(f"\n[MODIFIED] {f['path']}")
            lines.append(f['diff'][:2000])
            
        # Add filtered repository knowledge
        if context.repository_knowledge:
            lines.append("\n## Repository Knowledge (Relevant to Changes)")
            
            # If no target files from diff, fall back to all known files
            if not target_files:
                target_files = list(set(
                    list(context.repository_knowledge.class_index.keys()) + 
                    list(context.repository_knowledge.method_index.keys())
                ))
                
            lines.append("### Classes")
            for f in target_files:
                if f in context.repository_knowledge.class_index:
                    for cls in context.repository_knowledge.class_index[f]:
                        lines.append(f"Class {cls.name} (in {f}):")
                        for m in cls.methods:
                            lines.append(f"  def {m.name}({', '.join(m.args)}) -> {m.returns}")
            
            lines.append("### Free Functions")
            for f in target_files:
                if f in context.repository_knowledge.method_index:
                    for m in context.repository_knowledge.method_index[f]:
                        lines.append(f"def {m.name}({', '.join(m.args)}) -> {m.returns}  # in {f}")
                        
            lines.append("### Fixtures")
            for f in context.repository_knowledge.fixture_index.values():
                for fix in f:
                    lines.append(f"@pytest.fixture(scope={fix.scope}) def {fix.name}()")
            
        context.llm_context = "\n".join(lines)

class RepositoryUnderstandingAgentStage(Stage):
    """Step 5, 6, 7: LLM Agent, Validation, and Evaluation."""
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
    def execute(self, context: WorkflowContext) -> None:
            
        prompt = f"""
        You are a Senior Software Architect. Understand the following repository changes.
        Determine the business intent, feature intent, architecture impact, and risk level.
        Never return Markdown or explanations. Return strictly valid JSON matching the schema.
        
        Context:
        {context.llm_context}
        """
        
        max_retries = 3
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Step 5 & 6: LLM execution and JSON parsing via Pydantic
                result: ChangeSummarySchema = self.llm_service.generate_structured_json(
                    prompt=prompt,
                    schema=ChangeSummarySchema
                )
                
                context.change_summary = result
                
                # Step 7: Confidence Evaluation
                if result.confidence < 0.8:
                    context.warnings.append(f"Low confidence analysis: {result.confidence}")
                    
                return # Success
                
            except Exception as e:
                last_exception = e
                
        raise ValueError(f"Failed to generate structured JSON after {max_retries} retries. Last error: {last_exception}")
