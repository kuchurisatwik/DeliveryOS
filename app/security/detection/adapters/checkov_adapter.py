"""Checkov scanner adapter (Requirement 4.5).

Checkov scans Infrastructure-as-Code for misconfigurations: publicly exposed
cloud resources, weak IAM policies, open security groups, Kubernetes
misconfigurations, and Terraform / CloudFormation risks. It is invoked with
``-o json`` and its native JSON ``results.failed_checks`` array is parsed into
:class:`Finding` objects.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, ScanScope, Severity

# Checkov severity vocabulary (present when using the platform integration) ->
# shared Severity. Checkov often omits severity, so the default is MEDIUM.
_CHECKOV_SEVERITY: dict[str, Severity] = {
    "INFO": Severity.INFO,
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "MODERATE": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}


class CheckovAdapter:
    """Runs Checkov over the scoped IaC files and parses its JSON report."""

    name = "checkov"

    def __init__(self, *, cwd: str | None = None, timeout: int = base.DEFAULT_TIMEOUT) -> None:
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []
        # Checkov accepts repeated `-d <dir>` / `-f <file>`; use `-d` for the
        # scoped paths and `-o json` for the machine-readable report.
        command = ["checkov", "-o", "json", "--compact", "--quiet"]
        for path in scope.paths:
            command.extend(["-d", path])
        result = base.run_scanner(
            command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
        )
        # Checkov exits 0 (all passed) or 1 (failed checks) with JSON on stdout.
        if result.returncode >= 2 and not result.stdout.strip():
            raise ScannerError(
                self.name, f"exited {result.returncode}: {result.stderr.strip()}"
            )
        payload = base.load_json(result.stdout, scanner_name=self.name, stderr=result.stderr)
        return self.parse(payload)

    @classmethod
    def parse(cls, payload: Any) -> list[Finding]:
        """Parse Checkov's native JSON report into :class:`Finding` objects (pure).

        Checkov emits either a single result object or a list of them (one per
        framework, e.g. Terraform + CloudFormation). Both shapes are handled.
        """

        findings: list[Finding] = []
        for block in cls._iter_result_blocks(payload):
            results = block.get("results") or {}
            for check in results.get("failed_checks") or []:
                line_range = check.get("file_line_range") or []
                start = line_range[0] if line_range else None
                end = line_range[1] if len(line_range) > 1 else start
                location = base.make_location(
                    check.get("file_path"),
                    start,
                    end,
                    symbol=check.get("resource"),
                )
                severity = base.map_severity(
                    check.get("severity"), _CHECKOV_SEVERITY, Severity.MEDIUM
                )
                findings.append(
                    Finding(
                        scanner=cls.name,
                        rule_id=str(check.get("check_id") or "unknown"),
                        location=location,
                        severity=severity,
                        message=check.get("check_name") or "",
                        raw=dict(check),
                    )
                )
        return findings

    @staticmethod
    def _iter_result_blocks(payload: Any) -> list[Mapping[str, Any]]:
        if isinstance(payload, list):
            return [b for b in payload if isinstance(b, Mapping)]
        if isinstance(payload, Mapping):
            return [payload]
        return []
