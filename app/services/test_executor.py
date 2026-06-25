import subprocess
import time
import os
from app.schemas.quality import TestExecutionReport
from app.utils.logger import logger

class TestExecutionService:
    """Service dedicated to running tests via subprocess deterministically."""
    
    def run_tests(self, workspace_path: str) -> TestExecutionReport:
        logger.info(f"Running pytest in {workspace_path}")
        start_time = time.time()
        
        try:
            # We must inject the workspace_path into PYTHONPATH so the generated tests can import the app modules
            env = os.environ.copy()
            env["PYTHONPATH"] = workspace_path
            
            # Run pytest in the cloned workspace, capturing output
            # We don't fail immediately on non-zero exit code because test failures are expected
            result = subprocess.run(
                ["pytest", "-q"],
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
            
            # Very basic parsing of pytest stdout for passed/failed
            # In a real system, you'd use a pytest json report plugin, but we parse summary here
            passed = stdout.count("PASSED")
            failed = stdout.count("FAILED")
            errors = stdout.count("ERROR")
            
            # Simple extraction of failed test names
            failed_test_names = []
            for line in stdout.split("\n"):
                if "FAILED" in line and ".py::" in line:
                    parts = line.split("FAILED")
                    if len(parts) > 1:
                        failed_test_names.append(parts[1].strip().split()[0])
            
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
            
            logger.info(f"Pytest execution finished in {duration:.2f}s. Exit code: {exit_code}")
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
