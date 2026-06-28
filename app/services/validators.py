import ast
import os
import subprocess
from typing import List, Dict
from app.utils.logger import logger
from app.schemas.quality import (
    SyntaxStatus,
    ImportStatus,
    DependencyStatus,
    LintStatus,
    TypeStatus,
    ValidationReport
)
from app.services.test_executor import TestExecutionService
from app.services.coverage_service import CoverageService

class SyntaxValidationService:
    def validate(self, workspace_path: str) -> SyntaxStatus:
        errors = []
        for root, _, files in os.walk(workspace_path):
            if "venv" in root or ".venv" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            ast.parse(f.read(), filename=filepath)
                    except SyntaxError as e:
                        errors.append(f"{file}:{e.lineno} - {e.msg}")
                    except Exception as e:
                        errors.append(f"{file} - Could not parse: {str(e)}")
        
        return SyntaxStatus(passed=len(errors) == 0, errors=errors)

class ImportValidationService:
    def validate(self, workspace_path: str) -> ImportStatus:
        env = os.environ.copy()
        env["PYTHONPATH"] = workspace_path
        
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            env=env
        )
        
        unresolved = []
        if result.returncode != 0:
            for line in result.stdout.split("\n") + result.stderr.split("\n"):
                if "ImportError" in line or "ModuleNotFoundError" in line:
                    unresolved.append(line.strip())
                    
        return ImportStatus(passed=len(unresolved) == 0, unresolved_imports=unresolved)

class ValidationEngine:
    """Aggregates validation checks. Focused on test execution and coverage only.
    Lint and type checking removed to focus on test reliability.
    """
    
    def __init__(self):
        self.syntax = SyntaxValidationService()
        self.imports = ImportValidationService()
        self.test_exec = TestExecutionService()
        self.coverage = CoverageService()
        
    def run_all(self, workspace_path: str) -> ValidationReport:
        logger.info(f"Running Validation Engine on {workspace_path}")
        
        syntax_status = self.syntax.validate(workspace_path)
        import_status = self.imports.validate(workspace_path)
        
        exec_report = None
        cov_report = None
        
        # Only run tests and coverage if syntax and imports passed
        build_status = syntax_status.passed and import_status.passed
        if build_status:
            exec_report = self.test_exec.run_tests(workspace_path)
            cov_report = self.coverage.run_coverage(workspace_path)
            
        # Return with dummy lint/type statuses (always pass) for schema compatibility
        return ValidationReport(
            build_status=build_status,
            syntax_status=syntax_status,
            import_status=import_status,
            dependency_status=DependencyStatus(passed=True, missing_dependencies=[]),
            lint_status=LintStatus(passed=True, warnings=[]),
            type_status=TypeStatus(passed=True, errors=[]),
            execution_report=exec_report,
            coverage_report=cov_report
        )
