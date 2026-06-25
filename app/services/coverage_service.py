import subprocess
import json
import os
from app.schemas.quality import CoverageReport
from app.utils.logger import logger

class CoverageService:
    """Service dedicated to running coverage via subprocess deterministically."""
    
    def run_coverage(self, workspace_path: str) -> CoverageReport:
        logger.info(f"Running pytest coverage in {workspace_path}")
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = workspace_path
            
            # Run pytest with coverage json report
            # We install pytest-cov in requirements if needed
            subprocess.run(
                ["pytest", "--cov=.", "--cov-report=json"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            
            coverage_file = os.path.join(workspace_path, "coverage.json")
            if not os.path.exists(coverage_file):
                logger.warning("coverage.json was not generated. Check if pytest-cov is installed.")
                return CoverageReport()
                
            with open(coverage_file, "r", encoding="utf-8") as f:
                cov_data = json.load(f)
                
            totals = cov_data.get("totals", {})
            total_lines = totals.get("num_statements", 0)
            covered_lines = totals.get("covered_lines", 0)
            missing_lines = totals.get("missing_lines", 0)
            coverage_percentage = totals.get("percent_covered", 0.0)
            
            missing_line_numbers = []
            files = cov_data.get("files", {})
            for filename, file_data in files.items():
                missing = file_data.get("missing_lines", [])
                if missing:
                    missing_line_numbers.append(f"{filename}: lines {missing}")
            
            report = CoverageReport(
                total_lines=total_lines,
                covered_lines=covered_lines,
                missing_lines=missing_lines,
                coverage_percentage=coverage_percentage,
                missing_line_numbers=missing_line_numbers
            )
            
            logger.info(f"Coverage execution finished. Total coverage: {coverage_percentage:.2f}%")
            return report
            
        except Exception as e:
            logger.error(f"Failed to execute coverage subprocess: {e}")
            return CoverageReport()
