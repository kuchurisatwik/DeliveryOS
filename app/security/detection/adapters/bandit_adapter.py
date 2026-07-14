"""Bandit scanner adapter (Requirement 4.1).

Bandit statically analyses Python source for common security issues: unsafe
``subprocess`` / ``os.system`` use, ``eval``/``exec``, unsafe deserialization
(``pickle``/``marshal``), weak crypto, hardcoded passwords, and unsafe YAML
loading. It is invoked with ``-f json`` and its native JSON report is parsed into
the shared :class:`Finding` type.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, ScanScope, Severity

# Bandit issue_severity vocabulary -> shared Severity.
_BANDIT_SEVERITY: dict[str, Severity] = {
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "UNDEFINED": Severity.INFO,
}


class BanditAdapter:
    """Runs Bandit over the scoped Python files and parses its JSON report."""

    name = "bandit"

    def __init__(self, *, cwd: str | None = None, timeout: int = base.DEFAULT_TIMEOUT) -> None:
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []
        # Write the JSON report to a file (`-o`) instead of stdout: on Windows
        # Bandit's startup logging goes to stderr and stdout can come back empty,
        # which broke JSON parsing. `-r` recurses into any scoped directories.
        report = base.new_temp_report(".json")
        try:
            command = ["bandit", "-r", "-f", "json", "-o", report, *scope.paths]
            result = base.run_scanner(
                command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
            )
            text = base.read_report(report)
            # Bandit exits 0 (no issues) or 1 (issues found). Exit >= 2 with no
            # report written is a genuine usage/internal error.
            if result.returncode >= 2 and not text.strip():
                raise ScannerError(
                    self.name, f"exited {result.returncode}: {result.stderr.strip()}"
                )
            if not text.strip():
                # No report produced (e.g. no Python files in scope) → no findings.
                return []
            payload = base.load_json(text, scanner_name=self.name, stderr=result.stderr)
            return self.parse(payload)
        finally:
            base.cleanup(report)

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> list[Finding]:
        """Parse Bandit's native JSON report into :class:`Finding` objects (pure)."""

        findings: list[Finding] = []
        for issue in payload.get("results") or []:
            location = base.make_location(
                issue.get("filename"),
                issue.get("line_number"),
                (issue.get("line_range") or [issue.get("line_number")])[-1],
                symbol=issue.get("test_name"),
            )
            severity = base.map_severity(
                issue.get("issue_severity"), _BANDIT_SEVERITY, Severity.MEDIUM
            )
            findings.append(
                Finding(
                    scanner=cls.name,
                    rule_id=str(issue.get("test_id") or issue.get("test_name") or "unknown"),
                    location=location,
                    severity=severity,
                    message=issue.get("issue_text") or "",
                    raw=dict(issue),
                )
            )
        return findings
