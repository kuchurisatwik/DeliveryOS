import os
import json
from typing import List
from app.schemas.knowledge import RepositoryKnowledge
from app.services.extractors.base import IntelligenceExtractor
from app.services.extractors.ast_extractor import AstPythonExtractor
from app.utils.logger import logger

class RepositoryKnowledgeAggregator:
    """
    Layer 2: Aggregates intelligence from all configured extractors into a single
    normalized RepositoryKnowledge object, handling caching.
    """
    
    def __init__(self):
        self.extractors: List[IntelligenceExtractor] = [
            AstPythonExtractor()
        ]
        
    def build_or_load(self, workspace_path: str, commit_sha: str = "latest") -> RepositoryKnowledge:
        cache_dir = os.path.join(workspace_path, ".ai_cache")
        cache_file = os.path.join(cache_dir, "repo_knowledge_cache.json")
        
        knowledge = RepositoryKnowledge()
        if os.path.exists(cache_file):
            logger.info("Loading RepositoryKnowledge from cache for differential update.")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    knowledge = RepositoryKnowledge(**data)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}. Rebuilding from scratch...")
        
        logger.info("Running intelligence extractors...")
        
        for extractor in self.extractors:
            try:
                extractor.extract(workspace_path, knowledge)
            except Exception as e:
                logger.error(f"Extractor {extractor.__class__.__name__} failed: {e}")
                
        # Save to cache
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(knowledge.model_dump(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write cache: {e}")
            
        return knowledge
