# import json  # Remove unused import

# import re  # Remove unused import

from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext, ChangeSummarySchema
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService
from app.services.knowledge_aggregator import RepositoryKnowledgeAggregator

class GitDiffCollectorStage(Stage):
    """Step 1: Collects the structured git diff."""
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: LLMService = None) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set.")
        context.structured_diff = git_service.get_commit_diff(context.workspace, context.commit_sha)

class FileClassifierStage(Stage):
    """Step 2: Classifies changed files by type."""
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: LLMService = None) -> None:
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
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: LLMService = None) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set for MetadataExtractorStage.")
            
        aggregator = RepositoryKnowledgeAggregator()
        knowledge = aggregator.build_or_load(context.workspace)
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
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: LLMService = None) -> None:
        # Build a concise representation
        lines = []
        lines.append(f"Repository: {context.repository}")
        lines.append(f"Commit: {context.commit_sha}")
        lines.append(f"Detected Framework: {context.framework or 'Unknown'}")
        
        lines.append("\n## File Categories")
        for category, files in context.file_categories.items():
            if files:
                lines.append(f"- {category}: {', '.join(files)}")
                
        lines.append("\n## Extracted Metadata (Added/Modified)")
        lines.append(f"- New Routes: {', '.join(context.extracted_metadata['routes']) or 'None'}")
        lines.append(f"- New Classes: {', '.join(context.extracted_metadata['classes']) or 'None'}")
        lines.append(f"- New Functions: {', '.join(context.extracted_metadata['functions']) or 'None'}")
        
        lines.append("\n## Diff Highlights")
        for f in context.structured_diff.get("added", []):
            lines.append(f"\n[ADDED] {f['path']}")
            lines.append(f['diff'][:1000]) # truncated to save tokens
            
        for f in context.structured_diff.get("modified", []):
            lines.append(f"\n[MODIFIED] {f['path']}")
            lines.append(f['diff'][:1000])
            
        # Add filtered repository knowledge
        if context.repository_knowledge:
            lines.append("\n## Repository Knowledge (Relevant to Changes)")
            lines.append("### Classes")
            for f in context.changed_files:
                if f in context.repository_knowledge.class_index:
                    for cls in context.repository_knowledge.class_index[f]:
                        lines.append(f"Class {cls.name}:")
                        for m in cls.methods:
                            lines.append(f"  def {m.name}({', '.join(m.args)}) -> {m.returns}")
            
            lines.append("### Methods")
            for f in context.changed_files:
                if f in context.repository_knowledge.method_index:
                    for m in context.repository_knowledge.method_index[f]:
                        lines.append(f"def {m.name}({', '.join(m.args)}) -> {m.returns}")
                        
            lines.append("### Fixtures")
            for f in context.repository_knowledge.fixture_index.values():
                for fix in f:
                    lines.append(f"@pytest.fixture(scope={fix.scope}) def {fix.name}()")
            
        context.llm_context = "\n".join(lines)

class RepositoryUnderstandingAgentStage(Stage):
    """Step 5, 6, 7: LLM Agent, Validation, and Evaluation."""
    def execute(self, context: WorkflowContext, git_service: GitService, github_service: GitHubService, llm_service: LLMService = None) -> None:
        if not llm_service:
            raise ValueError("LLMService is required for the Repository Understanding Agent.")
            
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
                result: ChangeSummarySchema = llm_service.generate_structured_json(
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
