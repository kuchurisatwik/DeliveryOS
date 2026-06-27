import os
import ast
from app.utils.logger import logger
from app.schemas.quality import PatchArtifact

class WorkspacePatchService:
    """
    Deterministically applies localized string replacements to files in the workspace based on a PatchArtifact.
    Never uses LLMs, relies strictly on precise exact-string matching.
    Includes a syntax validation guard to prevent corrupting source files.
    """
    
    def apply_patches(self, workspace_path: str, patch_artifact: PatchArtifact) -> bool:
        logger.info(f"Applying {len(patch_artifact.patches)} patches to workspace...")
        
        success = True
        
        for patch in patch_artifact.patches:
            # Safely resolve the absolute file path within the workspace
            # Removing leading slashes to prevent absolute path traversal out of workspace
            safe_path = patch.file_path.lstrip("/\\")
            full_path = os.path.join(workspace_path, safe_path)
            
            if not os.path.exists(full_path):
                logger.error(f"Patch failed: File {safe_path} does not exist.")
                success = False
                continue
                
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                    
                if not patch.search_block:
                    # Append mode
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
                
                # SYNTAX VALIDATION GUARD: If it's a .py file, verify the patched
                # content parses without SyntaxError before writing it to disk.
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
                
                # PYTEST COLLECTION GUARD (for framework-level imports/Pydantic errors)
                if safe_path.endswith(".py"):
                    import subprocess
                    try:
                        res = subprocess.run(
                            ["pytest", "--collect-only"], 
                            cwd=workspace_path, 
                            capture_output=True, 
                            text=True
                        )
                        if res.returncode != 0 and "no tests collected" not in res.stdout:
                            # Sometimes no tests collected is exit code 5, which is fine, but Exit code 2 (collection error) is bad.
                            if res.returncode == 2 or "ERROR" in res.stdout or "Error" in res.stderr:
                                logger.error(
                                    f"Patch REJECTED for {safe_path}: introduced collection error (e.g. NameError/Pydantic error). "
                                    f"Stdout snippet: {res.stdout[:200]}"
                                )
                                # Revert
                                with open(full_path, "w", encoding="utf-8") as f:
                                    f.write(original_content)
                                success = False
                                continue
                    except Exception as e:
                        logger.warning(f"Could not run collection guard: {e}")
                        
                logger.info(f"Patch applied successfully to {safe_path}")
                    
            except Exception as e:
                logger.error(f"Failed to apply patch to {safe_path}: {e}")
                success = False
                
        return success
