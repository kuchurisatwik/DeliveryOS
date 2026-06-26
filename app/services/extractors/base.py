from abc import ABC, abstractmethod
from app.schemas.knowledge import RepositoryKnowledge

class IntelligenceExtractor(ABC):
    """Base class for all repository intelligence extractors."""
    
    @abstractmethod
    def extract(self, workspace_path: str, knowledge: RepositoryKnowledge) -> None:
        """
        Extract intelligence from the workspace and populate the shared knowledge object.
        
        Args:
            workspace_path: Path to the root of the repository
            knowledge: The shared RepositoryKnowledge object to mutate/populate
        """
        pass
