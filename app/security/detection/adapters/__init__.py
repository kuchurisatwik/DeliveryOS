"""Scanner adapters for the Detection Layer.

Each adapter implements the :class:`app.security.protocols.ScannerAdapter`
protocol (a ``name`` attribute and a ``scan(scope) -> list[Finding]`` method),
invokes its underlying tool as a subprocess, and parses the tool's native
SARIF/JSON output into the shared :class:`app.security.models.Finding` type.

A tool that is not installed, times out, or exits with an unrecoverable error
raises :class:`app.security.detection.adapters.base.ScannerError`, which the
parallel runner (task 4.1) treats as a per-scanner failure — recording a
``ScannerCoverage`` entry with ``status = "incomplete"`` while retaining the
findings from every other scanner.
"""

from app.security.detection.adapters.base import ScannerError
from app.security.detection.adapters.bandit_adapter import BanditAdapter
from app.security.detection.adapters.semgrep_adapter import SemgrepAdapter
from app.security.detection.adapters.codeql_adapter import CodeQLAdapter
from app.security.detection.adapters.gitleaks_adapter import GitleaksAdapter
from app.security.detection.adapters.checkov_adapter import CheckovAdapter
from app.security.detection.adapters.trivy_adapter import TrivyAdapter
from app.security.detection.adapters.njsscan_adapter import NjsscanAdapter

__all__ = [
    "ScannerError",
    "BanditAdapter",
    "SemgrepAdapter",
    "CodeQLAdapter",
    "GitleaksAdapter",
    "CheckovAdapter",
    "TrivyAdapter",
    "NjsscanAdapter",
]
