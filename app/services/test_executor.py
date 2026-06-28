import subprocess
import re
import time
import os
from app.schemas.quality import TestExecutionReport
from app.utils.logger import logger

class TestExecutionService:
    """Service dedicated to running tests via subprocess deterministically.
    Uses pytest -v --tb=short for cleaner, parseable output.
    """
    
    def run_tests(self, workspace_path: str) -> TestExecutionReport:
        logger.info(f"Running pytest in {workspace_path}")
        start_time = time.time()
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = workspace_path
            
            # Use -v --tb=short for verbose output with short tracebacks
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            
            duration = time.time() - start_time
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
            
            # Parse the summary line: "X passed, Y failed, Z errors in N.NNs"
            passed = 0
            failed = 0
            errors = 0
            
            summary_match = re.search(r'(\d+) passed', stdout)
            if summary_match:
                passed = int(summary_match.group(1))
                
            failed_match = re.search(r'(\d+) failed', stdout)
            if failed_match:
                failed = int(failed_match.group(1))
                
            error_match = re.search(r'(\d+) error', stdout)
            if error_match:
                errors = int(error_match.group(1))
            
            # Extract failed test names from verbose output
            failed_test_names = []
            for line in stdout.split("\n"):
                if "FAILED" in line and "::" in line:
                    # Format: "tests/test_foo.py::test_bar FAILED"
                    parts = line.strip().split(" ")
                    if parts:
                        test_name = parts[0].strip()
                        if "::" in test_name:
                            failed_test_names.append(test_name)
            
            report = TestExecutionReport(
                passed=passed,
                failed=failed,
                errors=errors,
                duration_seconds=duration,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                failed_test_names=failed_test_names
            )
            
            logger.info(f"Pytest execution finished in {duration:.2f}s. Exit code: {exit_code}. Passed: {passed}, Failed: {failed}, Errors: {errors}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to execute pytest subprocess: {e}")
            duration = time.time() - start_time
            return TestExecutionReport(
                errors=1,
                duration_seconds=duration,
                stderr=str(e),
                exit_code=-1
            )
