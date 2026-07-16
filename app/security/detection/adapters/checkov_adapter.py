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

    def __init__(
        self,
        *,
        directory: str = ".",
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        self._directory = directory
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        # Checkov auto-discovers IaC files (Terraform, CloudFormation, K8s,
        # Dockerfiles, ...) under a directory, so we point it at the repo root
        # ONCE rather than passing individual `.py` files with `-d` (which is the
        # wrong granularity — `-d` expects directories, and IaC is repo-wide).
        command = [
            "checkov",
            "-d",
            self._directory,
            "-o",
            "json",
            "--compact",
            "--quiet",
        ]
        result = base.run_scanner(
            command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
        )
        # Checkov exits 0 (all passed) or 1 (failed checks). Exit >= 2 with no
        # output is a genuine error.
        if result.returncode >= 2 and not result.stdout.strip():
            raise ScannerError(
                self.name, f"exited {result.returncode}: {result.stderr.strip()}"
            )
        if not result.stdout.strip():
            # No IaC discovered → no findings.
            return []
        # Checkov emits one JSON document per framework, back-to-back; decode all.
        blocks = base.load_json_multi(
            result.stdout, scanner_name=self.name, stderr=result.stderr
        )
        return self.parse(blocks)

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
        """Collect every Checkov result block, flattening arbitrary list nesting.

        Checkov's shape varies by version/invocation: a single result object, a
        top-level JSON array of per-framework objects, OR — once wrapped by
        :func:`base.load_json_multi` (which returns a list of decoded documents) —
        a *list containing that array* (list-of-list). Walking recursively and
        collecting every ``Mapping`` handles all of these without the previous
        single-level assumption that silently dropped a nested array (yielding 0
        findings even when Checkov reported failures)."""

        blocks: list[Mapping[str, Any]] = []

        def _walk(node: Any) -> None:
            if isinstance(node, Mapping):
                blocks.append(node)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        return blocks
