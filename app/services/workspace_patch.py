import os
import ast
from app.utils.logger import logger
from app.schemas.quality import PatchArtifact

class WorkspacePatchService:
    """
    Deterministically applies localized string replacements to files in the workspace.
    Includes guards:
    - AST syntax guard for .py files
    - Block empty search_block on production (non-test) files
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
    
    def apply_patches(self, workspace_path: str, patch_artifact: PatchArtifact) -> bool:
        logger.info(f"Applying {len(patch_artifact.patches)} patches to workspace...")
        
        success = True
        
        for patch in patch_artifact.patches:
            safe_path = patch.file_path.lstrip("/\\")
            full_path = os.path.join(workspace_path, safe_path)
            
            # Block empty search_block on production files
            if not patch.search_block and not self._is_test_file(safe_path):
                logger.warning(f"BLOCKED: Empty search_block patch on production file {safe_path}. Only test files may use append mode.")
                success = False
                continue
            
            if not os.path.exists(full_path):
                if not patch.search_block and self._is_test_file(safe_path):
                    # Creating a new test file — ensure parent dirs exist
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    try:
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(patch.replace_block)
                        logger.info(f"Created new test file: {safe_path}")
                        continue
                    except Exception as e:
                        logger.error(f"Failed to create test file {safe_path}: {e}")
                        success = False
                        continue
                else:
                    logger.error(f"Patch failed: File {safe_path} does not exist.")
                    success = False
                    continue
                
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                    
                if not patch.search_block:
                    # Append mode (only for test files — already guarded above)
                    new_content = original_content + "\n\n" + patch.replace_block
                    logger.info(f"Appending block to {safe_path}")
                else:
                    # Replace mode
                    if patch.search_block not in original_content:
                        logger.error(f"Patch failed: Search block not found in {safe_path}")
                        success = False
                        continue
                        
                    new_content = original_content.replace(patch.search_block, patch.replace_block, 1)
                    logger.info(f"Replacing block in {safe_path}")
                
                # SYNTAX VALIDATION GUARD
                if safe_path.endswith(".py"):
                    try:
                        ast.parse(new_content, filename=safe_path)
                    except SyntaxError as e:
                        logger.error(
                            f"Patch REJECTED for {safe_path}: would introduce SyntaxError "
                            f"at line {e.lineno}: {e.msg}. File left unchanged."
                        )
                        success = False
                        continue
                
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                logger.info(f"Patch applied successfully to {safe_path}")
                    
            except Exception as e:
                logger.error(f"Failed to apply patch to {safe_path}: {e}")
                success = False
                
        return success
