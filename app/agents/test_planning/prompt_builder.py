import os
from app.workflows.context import WorkflowContext

class PromptBuilder:
    """Builds the prompt for the Test Planning Agent based strictly on the Change Summary."""
    
    def __init__(self):
        self.prompt_template = ""
        prompt_path = os.path.join(os.getcwd(), "app", "prompts", "test_planner.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r") as f:
                self.prompt_template = f.read()
                
    def build_prompt(self, context: WorkflowContext) -> str:
        if not context.change_summary:
            raise ValueError("No change_summary found in WorkflowContext. Repository understanding must be completed first.")
            
        lines = []
        lines.append(self.prompt_template)
        lines.append("\n\n=== ARCHITECTURE & CHANGE SUMMARY ===")
        lines.append(f"Summary: {context.change_summary.summary}")
        lines.append(f"Feature Type: {context.change_summary.feature_type}")
        lines.append(f"Risk Level: {context.change_summary.risk_level}")
        lines.append(f"Breaking Change: {context.change_summary.breaking_change}")
        lines.append(f"Affected Modules: {', '.join(context.change_summary.affected_modules)}")
        lines.append(f"Affected Services: {', '.join(context.change_summary.affected_services)}")
        lines.append(f"Affected Routes: {', '.join(context.change_summary.affected_routes)}")
        lines.append(f"Affected Database Tables: {', '.join(context.change_summary.affected_database_tables)}")
        lines.append(f"Architecture Impact: {context.change_summary.architecture_impact}")
        
        if getattr(context, "repository_knowledge", None):
            lines.append("\n=== REPOSITORY KNOWLEDGE (FACTUAL API) ===")
            lines.append("Use ONLY the methods and routes listed below to create your scenarios. Do not invent scenarios for methods that do not exist.")
            lines.append(context.repository_knowledge.model_dump_json(indent=2))
        
        return "\n".join(lines)
