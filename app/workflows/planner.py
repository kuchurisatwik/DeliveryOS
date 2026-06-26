from app.schemas.quality import (
    ValidationReport,
    ReviewReport,
    CoverageAnalysis,
    ImprovementPlan
)
from typing import Optional
from app.utils.logger import logger

class ImprovementPlanner:
    """
    Deterministically merges various reports into a single ImprovementPlan.
    This defines WHAT must change, without invoking an LLM.
    """
    
    def build_plan(
        self,
        validation: Optional[ValidationReport],
        review: Optional[ReviewReport],
        coverage: Optional[CoverageAnalysis]
    ) -> ImprovementPlan:
        
        logger.info("Building Improvement Plan...")
        actions = []
        
        # 1. Validation Report Issues
        if validation:
            if not validation.syntax_status.passed:
                for err in validation.syntax_status.errors:
                    actions.append(f"Fix syntax error: {err}")
            
            if not validation.import_status.passed:
                for imp in validation.import_status.unresolved_imports:
                    actions.append(f"Resolve import error: {imp}")
                    
            if not validation.lint_status.passed:
                for warn in validation.lint_status.warnings:
                    actions.append(f"Fix lint warning: {warn}")
                    
            if not validation.type_status.passed:
                for err in validation.type_status.errors:
                    actions.append(f"Fix type error: {err}")
                    
            if validation.execution_report and validation.execution_report.failed > 0:
                for test in validation.execution_report.failed_test_names:
                    actions.append(f"Fix failing test: {test}")
                    
        # 2. Review Report Issues
        if review:
            for wa in review.weak_assertions:
                actions.append(f"Strengthen weak assertion: {wa}")
            for mm in review.missing_mocks:
                actions.append(f"Add missing mock: {mm}")
            for rt in review.readability_issues:
                actions.append(f"Improve readability: {rt}")
                
        # 3. Coverage Analysis Issues
        if coverage:
            for mb in coverage.missing_branches:
                actions.append(f"Cover missing branch: {mb}")
            for ms in coverage.missing_scenarios:
                actions.append(f"Implement missing scenario: {ms}")
            for ec in coverage.insufficient_edge_cases:
                actions.append(f"Add edge case: {ec}")
                
        logger.info(f"Generated Improvement Plan with {len(actions)} required actions.")
        return ImprovementPlan(actions=actions)
