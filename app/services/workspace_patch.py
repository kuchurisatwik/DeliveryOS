import os
from app.utils.logger import logger
from app.schemas.quality import PatchArtifact

class WorkspacePatchService:
    """
    Deterministically applies localized string replacements to files in the workspace based on a PatchArtifact.
    Never uses LLMs, relies strictly on precise exact-string matching.
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
                    content = f.read()
                    
                if not patch.search_block:
                    # Append mode
                    content = content + "\n\n" + patch.replace_block
                    logger.info(f"Appended block to {safe_path}")
                else:
                    # Replace mode
                    if patch.search_block not in content:
                        logger.error(f"Patch failed: Search block not found in {safe_path}")
                        success = False
                        continue
                        
                    content = content.replace(patch.search_block, patch.replace_block, 1)
                    logger.info(f"Replaced block in {safe_path}")
                    
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    
            except Exception as e:
                logger.error(f"Failed to apply patch to {safe_path}: {e}")
                success = False
                
        return success
