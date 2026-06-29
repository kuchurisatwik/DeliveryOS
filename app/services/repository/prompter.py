from typing import Dict
from app.schemas.repository import RepositoryContext
from app.utils.logger import logger

class PromptAssemblyEngine:
    """Assembles the retrieved context into a tightly packed, highly relevant prompt string."""
    
    def assemble_prompt(self, structured_diff: Dict, retrieved_context: RepositoryContext) -> str:
        logger.info("Assembling focused prompt...")
        lines = []
        
        # 1. Git Diff (The most critical signal)
        lines.append("\n=== GIT DIFF (CHANGES TO TEST) ===")
        for change_type in ["added", "modified"]:
            if structured_diff.get(change_type):
                lines.append(f"--- {change_type.upper()} FILES ---")
                for f in structured_diff[change_type]:
                    lines.append(f"\nFile: {f.get('path')}")
                    if "diff" in f and f["diff"]:
                        lines.append("Diff:")
                        lines.append(f["diff"][:5000])  # Cap at 5K chars per diff just in case
                        
        # 2. Target Symbols (Business Logic Changed)
        if retrieved_context.target_symbols:
            lines.append("\n=== TARGET BUSINESS LOGIC (CHANGED SYMBOLS) ===")
            for sym in retrieved_context.target_symbols:
                lines.append(f"\n--- {sym.type.upper()}: {sym.name} (in {sym.file_path}) ---")
                lines.append(sym.body)
                
        # 3. Dependencies (Things the changed code relies on)
        if retrieved_context.dependencies:
            lines.append("\n=== UPSTREAM DEPENDENCIES (MOCK THESE IF NEEDED) ===")
            for sym in retrieved_context.dependencies:
                # For dependencies, just provide the signature/header to save tokens
                header = sym.body.split("\n")[0]
                lines.append(f"{sym.type.capitalize()}: {sym.name} ({sym.file_path}) -> {header}")
                
        # 4. Related Tests (Patterns and Fixtures)
        if retrieved_context.related_tests:
            lines.append("\n=== RELATED TESTS & FIXTURES (REUSE THESE PATTERNS) ===")
            for test in retrieved_context.related_tests:
                lines.append(f"\n--- {test.file_path} ---")
                lines.append(test.body[:3000])  # Cap at 3K chars per test file
                
        assembled = "\n".join(lines)
        logger.info(f"Prompt assembly complete. Size: {len(assembled)} chars.")
        return assembled
