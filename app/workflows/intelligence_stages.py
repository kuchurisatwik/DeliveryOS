from app.workflows.stages import Stage
from app.workflows.context import WorkflowContext, ChangeSummarySchema
from app.services.git_service import GitService
from app.services.llm_service import LLMService

from app.services.repository.indexer import RepositoryIndexer
from app.services.repository.retriever import ContextRetrievalEngine
from app.services.repository.prompter import PromptAssemblyEngine

class GitDiffCollectorStage(Stage):
    """Step 1: Collects the structured git diff."""
    def __init__(self, git_service: GitService):
        self.git_service = git_service
        
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set.")
        context.structured_diff = self.git_service.get_commit_diff(context.workspace, context.commit_sha)

class RepositoryIndexerStage(Stage):
    """Step 2: Builds or updates the SQLite repository index via AST parsing."""
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set.")
        indexer = RepositoryIndexer(context.workspace)
        indexer.index_repository()

class ContextRetrievalStage(Stage):
    """Step 3: Queries the SQLite index to find symbols affected by the git diff."""
    def execute(self, context: WorkflowContext) -> None:
        if not context.workspace:
            raise ValueError("Workspace is not set.")
            
        retriever = ContextRetrievalEngine(context.workspace)
        # Use both changed_files and files found in structured diff
        target_files = list(context.changed_files) if context.changed_files else []
        for change_type in ["added", "modified"]:
            for f in context.structured_diff.get(change_type, []):
                path = f.get("path", "")
                if path and path not in target_files:
                    target_files.append(path)
                    
        # Store for the prompt assembler
        context.retrieved_knowledge = retriever.retrieve(target_files)

class PromptAssemblyStage(Stage):
    """Step 4: Assembles the highly targeted 15KB prompt string."""
    def execute(self, context: WorkflowContext) -> None:
        if not hasattr(context, 'retrieved_knowledge') or not context.retrieved_knowledge:
            context.llm_context = ""
            return
            
        prompter = PromptAssemblyEngine()
        context.llm_context = prompter.assemble_prompt(context.structured_diff, context.retrieved_knowledge)

# NOTE: RepositoryUnderstandingAgentStage is legacy and unused in the unified 1-Call setup, 
# but kept here if other parts of the system still reference it dynamically.
class RepositoryUnderstandingAgentStage(Stage):
    """Legacy Step 5."""
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
    def execute(self, context: WorkflowContext) -> None:
        pass
