from app.workflows.context import WorkflowContext
from app.services.llm_service import LLMService
from app.schemas.quality import CoverageAnalysis
from app.utils.logger import logger

class CoverageAgent:
    """Agent responsible for reasoning about uncovered code lines and suggesting missing tests."""
    
    def __init__(self):
        self.llm_service = LLMService()
        
    def analyze_coverage(self, context: WorkflowContext) -> CoverageAnalysis:
        logger.info("Calling Coverage Agent...")
        if not context.validation_report or not context.validation_report.coverage_report:
            logger.warning("No coverage_report found for CoverageAgent.")
            return CoverageAnalysis()
            
        coverage = context.validation_report.coverage_report
        # If coverage is perfect or close to it, no need to hallucinate improvements
        if coverage.coverage_percentage >= 95.0:
            return CoverageAnalysis()
            
        system_prompt = "You are an AI Coverage Analyst. Your goal is to map uncovered code to missing test scenarios based on the TestPlan. Return structural reasoning ONLY."
        user_prompt = self._build_prompt(context, coverage)
        
        return self.llm_service.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=CoverageAnalysis
        )
        
    def _build_prompt(self, context: WorkflowContext, coverage) -> str:
        lines = []
        lines.append("=== COVERAGE METRICS ===")
        lines.append(f"Total Lines: {coverage.total_lines}")
        lines.append(f"Covered Lines: {coverage.covered_lines}")
        lines.append(f"Coverage: {coverage.coverage_percentage}%")
        
        lines.append("\n=== MISSING LINES BY FILE ===")
        for missing in coverage.missing_line_numbers:
            lines.append(f"- {missing}")
            
        lines.append("\n=== TEST PLAN ===")
        if context.test_plan:
            lines.append(str(context.test_plan.model_dump()))
            
        lines.append("\nAnalyze the missing lines and produce a CoverageAnalysis identifying specific scenarios that must be generated to cover them.")
        return "\n".join(lines)
