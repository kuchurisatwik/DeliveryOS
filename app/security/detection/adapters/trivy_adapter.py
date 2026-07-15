"""Trivy scanner adapter (Requirement 4.6).

Trivy scans dependencies and containers: dependency CVEs, container / filesystem
vulnerabilities, Kubernetes configuration issues, and OS package vulnerabilities.
It is invoked in ``fs`` (filesystem) mode with ``--format json`` and its native
JSON report — a ``Results`` array containing ``Vulnerabilities``,
``Misconfigurations``, and ``Secrets`` — is parsed into :class:`Finding` objects.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, Location, ScanScope, Severity

# Trivy severity vocabulary -> shared Severity.
_TRIVY_SEVERITY: dict[str, Severity] = {
    "UNKNOWN": Severity.INFO,
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}


class TrivyAdapter:
    """Runs Trivy in filesystem mode over the scope and parses its JSON report."""

    name = "trivy"

    def __init__(
        self,
        *,
        scanners: str = "vuln,misconfig,secret",
        target: str = ".",
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        self._scanners = scanners
        self._target = target
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        # Dependency/OS/container vulns come from manifests & lockfiles that live
        # across the repo, not in one changed file: scan the whole tree (the repo
        # root), NOT just the first scoped path.
        target = self._target
        command = [
            "trivy",
            "fs",
            "--format",
            "json",
            "--scanners",
            self._scanners,
            "--quiet",
            target,
        ]
        result = base.run_scanner(
            command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
        )
        # Trivy exits 0 by default even when vulnerabilities are found (unless
        # `--exit-code` is set). A non-zero exit with no report is a real error.
        if result.returncode != 0 and not result.stdout.strip():
            raise ScannerError(
                self.name, f"exited {result.returncode}: {result.stderr.strip()}"
            )
        payload = base.load_json(result.stdout, scanner_name=self.name, stderr=result.stderr)
        return self.parse(payload)

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> list[Finding]:
        """Parse Trivy's native JSON report into :class:`Finding` objects (pure)."""

        findings: list[Finding] = []
        for block in payload.get("Results") or []:
            target = block.get("Target") or "<unknown>"
            findings.extend(cls._parse_vulnerabilities(block, target))
            findings.extend(cls._parse_misconfigurations(block, target))
            findings.extend(cls._parse_secrets(block, target))
        return findings

    @classmethod
    def _parse_vulnerabilities(cls, block: Mapping[str, Any], target: str) -> list[Finding]:
        findings: list[Finding] = []
        for vuln in block.get("Vulnerabilities") or []:
            severity = base.map_severity(
                vuln.get("Severity"), _TRIVY_SEVERITY, Severity.MEDIUM
            )
            pkg = vuln.get("PkgName")
            findings.append(
                Finding(
                    scanner=cls.name,
                    rule_id=str(vuln.get("VulnerabilityID") or "unknown"),
                    location=Location(path=target, start_line=0, end_line=0, symbol=pkg),
                    severity=severity,
                    message=vuln.get("Title") or vuln.get("Description") or "",
                    raw=dict(vuln),
                    category="dependency",
                )
            )
        return findings

    @classmethod
    def _parse_misconfigurations(cls, block: Mapping[str, Any], target: str) -> list[Finding]:
        findings: list[Finding] = []
        for misc in block.get("Misconfigurations") or []:
            severity = base.map_severity(
                misc.get("Severity"), _TRIVY_SEVERITY, Severity.MEDIUM
            )
            cause = misc.get("CauseMetadata") or {}
            location = base.make_location(
                target, cause.get("StartLine"), cause.get("EndLine")
            )
            findings.append(
                Finding(
                    scanner=cls.name,
                    rule_id=str(misc.get("ID") or "unknown"),
                    location=location,
                    severity=severity,
                    message=misc.get("Title") or misc.get("Message") or "",
                    raw=dict(misc),
                    category="iac",
                )
            )
        return findings

    @classmethod
    def _parse_secrets(cls, block: Mapping[str, Any], target: str) -> list[Finding]:
        findings: list[Finding] = []
        for secret in block.get("Secrets") or []:
            severity = base.map_severity(
                secret.get("Severity"), _TRIVY_SEVERITY, Severity.HIGH
            )
            location = base.make_location(
                target, secret.get("StartLine"), secret.get("EndLine"), symbol=secret.get("RuleID")
            )
            findings.append(
                Finding(
                    scanner=cls.name,
                    rule_id=str(secret.get("RuleID") or "secret"),
                    location=location,
                    severity=severity,
                    message=secret.get("Title") or "Leaked secret detected",
                    raw=dict(secret),
                    category="secret",
                )
            )
        return findings
