from typing import List
from app.schemas.test_plan import TestPlanSchema

class ConfidenceEvaluator:
    """Evaluates the confidence of the generated test plan."""
    
    def evaluate(self, test_plan: TestPlanSchema) -> List[str]:
        warnings = []
        if test_plan.confidence < 0.8:
            warnings.append(f"Low confidence test plan: {test_plan.confidence}. Ensure all edge cases are manually verified.")
            
        if test_plan.overall_risk.lower() == "high" and not test_plan.security_test_scenarios:
            warnings.append("High risk feature has no security test scenarios planned.")
            
        return warnings
