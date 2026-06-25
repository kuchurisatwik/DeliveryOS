from typing import List
from app.schemas.generated_test import GeneratedTestArtifact

class ConfidenceEvaluator:
    """Evaluates the confidence of the generated tests."""
    
    def evaluate(self, artifact: GeneratedTestArtifact) -> List[str]:
        warnings = []
        if artifact.confidence < 0.8:
            warnings.append(f"Low confidence generation ({artifact.confidence}). Review logic carefully.")
            
        if not artifact.new_fixtures and "pytest" in artifact.framework.lower():
            warnings.append("No new fixtures generated. Ensure tests are not duplicating setup code.")
            
        return warnings
