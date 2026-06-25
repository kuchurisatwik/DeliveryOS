from app.workflows.context import WorkflowContext
from app.services.llm_service import LLMService
from app.schemas.quality import CoverageImprovementPlan

class CoverageAgent:
    """Agent responsible for reasoning about uncovered code lines and suggesting missing tests."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
    def analyze_coverage(self, context: WorkflowContext) -> CoverageImprovementPlan:
        if not context.coverage_report:
            raise ValueError("CoverageAgent requires a coverage_report.")
            
        # If coverage is perfect or close to it, no need to hallucinate improvements
        if context.coverage_report.coverage_percentage >= 95.0:
            return CoverageImprovementPlan(
                missing_branches=[],
                missing_scenarios=[],
                insufficient_edge_cases=[],
                unexecuted_apis=[]
            )
            
        prompt = self._build_prompt(context)
        return self.llm_service.generate_structured_json(
            prompt=prompt,
            schema=CoverageImprovementPlan
        )
        
    def _build_prompt(self, context: WorkflowContext) -> str:
        lines = []
        lines.append("You are an AI Coverage Analyst. Your goal is to map uncovered code to missing test scenarios.")
        
        lines.append("\n=== COVERAGE METRICS ===")
        lines.append(f"Total Lines: {context.coverage_report.total_lines}")
        lines.append(f"Covered Lines: {context.coverage_report.covered_lines}")
        lines.append(f"Coverage: {context.coverage_report.coverage_percentage}%")
        
        lines.append("\n=== MISSING LINES BY FILE ===")
        for missing in context.coverage_report.missing_line_numbers:
            lines.append(f"- {missing}")
            
        lines.append("\n=== REPOSITORY METADATA ===")
        lines.append(f"Summary: {context.change_summary.summary if context.change_summary else 'N/A'}")
        
        lines.append("\nAnalyze the missing lines and produce a CoverageImprovementPlan identifying specific scenarios that must be generated to cover them.")
        return "\n".join(lines)
