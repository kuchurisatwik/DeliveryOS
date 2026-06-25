import os
from typing import List
from app.schemas.generated_test import GeneratedTestArtifact
from app.utils.logger import logger

class WorkspaceWriterService:
    """Service dedicated to writing generated code to the local file system securely."""
    
    def write_artifact(self, workspace_path: str, artifact: GeneratedTestArtifact) -> List[str]:
        """
        Writes the generated files from the artifact into the workspace.
        
        Args:
            workspace_path: Absolute path to the cloned repository workspace.
            artifact: The strictly typed GeneratedTestArtifact from the TestGenerationAgent.
            
        Returns:
            List of absolute paths to the files that were written.
        """
        if not os.path.exists(workspace_path):
            raise ValueError(f"Workspace path does not exist: {workspace_path}")
            
        written_files = []
        
        for generated_file in artifact.generated_files:
            # Ensure path is relative and doesn't try to escape the workspace
            safe_relative_path = generated_file.path.lstrip("/\\")
            absolute_path = os.path.join(workspace_path, safe_relative_path)
            
            # Additional safety check against path traversal
            if not os.path.abspath(absolute_path).startswith(os.path.abspath(workspace_path)):
                logger.warning(f"Skipping dangerous file path: {generated_file.path}")
                continue
                
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
            
            # Write the file
            try:
                with open(absolute_path, "w", encoding="utf-8") as f:
                    f.write(generated_file.content)
                logger.info(f"Successfully wrote generated test file to: {safe_relative_path}")
                written_files.append(absolute_path)
            except Exception as e:
                logger.error(f"Failed to write file {safe_relative_path}: {e}")
                
        return written_files
