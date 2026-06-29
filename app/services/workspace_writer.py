import os
import ast
from app.utils.logger import logger
from app.schemas.repair import RepairSessionSchema

class DuplicateDefinitionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.defined_names = set()
        self.has_duplicates = False
        self.duplicate_name = None

    def visit_FunctionDef(self, node):
        if node.name in self.defined_names:
            self.has_duplicates = True
            self.duplicate_name = node.name
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        if node.name in self.defined_names:
            self.has_duplicates = True
            self.duplicate_name = node.name
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        if node.name in self.defined_names:
            self.has_duplicates = True
            self.duplicate_name = node.name
        self.defined_names.add(node.name)
        # Do not visit class body so we don't count methods as duplicates of top-level functions unless we want to.
        # But wait, it's safer to just check top level. If we want to check methods, we should scope it.
        # Let's just do top-level for now.
        pass

class WorkspaceWriterService:
    """
    Writes generated or repaired files to the workspace.
    Supports complete file overwriting for AI-generated tests, explicitly blocking incremental patching.
    """
    
    def _is_test_file(self, safe_path: str) -> bool:
        """Returns True if the path is a test file."""
        return (
            safe_path.startswith("tests/") or 
            safe_path.startswith("test/") or 
            safe_path.startswith("tests\\") or 
            safe_path.startswith("test\\") or 
            safe_path == "conftest.py"
        )
        
    def _validate_ast(self, content: str, file_path: str) -> bool:
        """Validates Python syntax and checks for duplicate definitions."""
        try:
            tree = ast.parse(content, filename=file_path)
            
            # Check for duplicate classes/functions at the module level
            visitor = DuplicateDefinitionVisitor()
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name in visitor.defined_names:
                        logger.error(f"Validation failed for {file_path}: Duplicate definition of '{node.name}' found.")
                        return False
                    visitor.defined_names.add(node.name)
            
            return True
        except SyntaxError as e:
            logger.error(f"Validation failed for {file_path}: SyntaxError at line {e.lineno}: {e.msg}.")
            return False
            
    def write_repaired_files(self, workspace_path: str, repair_session: RepairSessionSchema) -> bool:
        logger.info(f"Applying complete file regeneration for {len(repair_session.repaired_files)} files...")
        
        success = True
        
        for repaired_file in repair_session.repaired_files:
            safe_path = repaired_file.file_path.lstrip("/\\")
            full_path = os.path.join(workspace_path, safe_path)
            content = repaired_file.content
            
            # Mode 1: Developer-owned files (Future support only)
            if not self._is_test_file(safe_path):
                logger.warning(f"BLOCKED: Overwriting production file {safe_path} is currently not supported.")
                success = False
                continue
                
            # Mode 2: AI-generated files (Overwrite mode)
            
            # Validation 1: Not empty
            if not content or not content.strip():
                logger.error(f"Validation failed for {safe_path}: File content is empty.")
                success = False
                continue
                
            # Validation 2: Language
            if not safe_path.endswith(".py"):
                logger.error(f"Validation failed for {safe_path}: Only Python files are supported.")
                success = False
                continue
                
            # Validation 3: Size reduction drop
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
                
                if len(old_content) > 0 and len(content) < (len(old_content) * 0.5):
                    logger.error(f"Validation failed for {safe_path}: Size dropped by >50% (from {len(old_content)} to {len(content)}). Suspected accidental deletion.")
                    success = False
                    continue
            
            # Validation 4: AST and duplicates
            if not self._validate_ast(content, safe_path):
                success = False
                continue
                
            # All validations passed, write file
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Successfully overwrote {safe_path} with completely regenerated content.")
            except Exception as e:
                logger.error(f"Failed to write file {safe_path}: {e}")
                success = False
                
        return success

    def write_artifact(self, workspace_path: str, artifact: 'GeneratedTestArtifact') -> list[str]:
        """Writes the newly generated test files to the workspace."""
        written_files = []
        for gen_file in artifact.generated_files:
            safe_path = gen_file.path.lstrip("/\\")
            full_path = os.path.join(workspace_path, safe_path)
            
            # Validation 4: AST and duplicates
            if safe_path.endswith(".py"):
                if not self._validate_ast(gen_file.content, safe_path):
                    logger.warning(f"Initial generated file {safe_path} failed AST validation. It will be passed to Repair loop.")
            
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(gen_file.content)
                written_files.append(safe_path)
            except Exception as e:
                logger.error(f"Failed to write generated test file {safe_path}: {e}")
                
        return written_files
