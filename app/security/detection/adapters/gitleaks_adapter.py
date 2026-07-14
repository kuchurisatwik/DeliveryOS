"""Gitleaks scanner adapter (Requirement 4.4).

Gitleaks detects leaked secrets: API keys, cloud credentials, SSH private keys,
tokens, database passwords, and ``.env`` leaks. It is invoked in ``detect`` mode
with ``--report-format json --report-path -`` so its native JSON report (a flat
array of leak objects) is written to stdout and parsed into :class:`Finding`
objects. Leaked secrets have no native severity, so they are reported as HIGH.
"""

from __future__ import annotations

from typing import Any

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, ScanScope, Severity


class GitleaksAdapter:
    """Runs Gitleaks over the scoped source tree and parses its JSON report."""

    name = "gitleaks"

    def __init__(
        self,
        *,
        source: str = ".",
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        self._source = source
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        # Gitleaks scans a source tree (directory / repo). The scope's first path
        # narrows the scan when it is a directory; otherwise the configured source.
        source = scope.paths[0] if scope.paths else self._source
        command = [
            "gitleaks",
            "detect",
            "--no-git",
            "--source",
            source,
            "--report-format",
            "json",
            "--report-path",
            "-",
        ]
        result = base.run_scanner(
            command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
        )
        # Gitleaks exits 0 (no leaks) or 1 (leaks found), both with a JSON array
        # on stdout. Higher exit codes indicate a real error.
        if result.returncode >= 2 and not result.stdout.strip():
            raise ScannerError(
                self.name, f"exited {result.returncode}: {result.stderr.strip()}"
            )
        payload = base.load_json(result.stdout, scanner_name=self.name, stderr=result.stderr)
        return self.parse(payload)

    @classmethod
    def parse(cls, payload: Any) -> list[Finding]:
        """Parse Gitleaks' native JSON array into :class:`Finding` objects (pure).

        Gitleaks emits ``null`` (not ``[]``) when there are no leaks.
        """

        findings: list[Finding] = []
        for leak in payload or []:
            location = base.make_location(
                leak.get("File"),
                leak.get("StartLine"),
                leak.get("EndLine"),
                symbol=leak.get("RuleID"),
            )
            findings.append(
                Finding(
                    scanner=cls.name,
                    rule_id=str(leak.get("RuleID") or "secret"),
                    location=location,
                    severity=Severity.HIGH,
                    message=leak.get("Description") or "Leaked secret detected",
                    raw=dict(leak),
                )
            )
        return findings
