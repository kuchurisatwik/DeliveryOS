import os
from app.workflows.context import WorkflowContext

class ContextBuilder:
    """Prepares the smallest possible context required for code generation."""
    
    def __init__(self):
        self.prompt_template = ""
        prompt_path = os.path.join(os.getcwd(), "app", "prompts", "test_generation.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
                
    def build_prompt(self, context: WorkflowContext) -> str:
        if not context.change_summary or not context.test_plan:
            raise ValueError("Test Generation requires both ChangeSummary and TestPlan.")
            
        lines = []
        lines.append(self.prompt_template)
        lines.append("\n=== REPOSITORY METADATA ===")
        lines.append(f"Language: {context.repository_language}")
        lines.append(f"Framework: {context.framework}")
        
        lines.append("\n=== CHANGE SUMMARY ===")
        lines.append(f"Summary: {context.change_summary.summary}")
        lines.append(f"Affected Modules: {', '.join(context.change_summary.affected_modules)}")
        lines.append(f"LLM Context (Code Snippets): {context.llm_context}")
        
        lines.append("\n=== TARGET TEST PLAN SCENARIOS ===")
        all_scenarios = (
            context.test_plan.unit_test_scenarios +
            context.test_plan.integration_test_scenarios +
            context.test_plan.api_test_scenarios +
            context.test_plan.negative_test_scenarios +
            context.test_plan.boundary_test_scenarios +
            context.test_plan.security_test_scenarios
        )
        
        for s in all_scenarios:
            lines.append(f"[{s.category}] {s.scenario_name}: {s.expected_behaviour}")
            
        return "\n".join(lines)
