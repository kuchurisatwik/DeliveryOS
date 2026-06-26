
import re
from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext, ChangeSummarySchema
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService

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
        metadata = {
            "functions": [],
            "classes": [],
            "routes": [],
            "decorators": []
        }
        
        # Very simple regex parsing for Python (expandable later or replace with AST)
        func_regex = re.compile(r"^\+?\s*def\s+([a-zA-Z0-9_]+)\s*\(", re.MULTILINE)
        class_regex = re.compile(r"^\+?\s*class\s+([a-zA-Z0-9_]+)", re.MULTILINE)
        route_regex = re.compile(r"^\+?\s*@app\.(get|post|put|delete|patch)\(\"([^\"]+)\"", re.MULTILINE)
        
        for f in context.structured_diff.get("added", []) + context.structured_diff.get("modified", []):
            diff_text = f.get("diff", "")
            
            for match in func_regex.finditer(diff_text):
                metadata["functions"].append(match.group(1))
            for match in class_regex.finditer(diff_text):
                metadata["classes"].append(match.group(1))
            for match in route_regex.finditer(diff_text):
                metadata["routes"].append(f"{match.group(1).upper()} {match.group(2)}")
                context.framework = "FastAPI" # Auto-detect FastAPI
                
        context.extracted_metadata = metadata

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
