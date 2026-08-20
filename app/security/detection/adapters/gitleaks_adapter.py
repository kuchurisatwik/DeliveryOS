"""Gitleaks scanner adapter (Requirement 4.4).

Gitleaks detects leaked secrets: API keys, cloud credentials, SSH private keys,
tokens, database passwords, and ``.env`` leaks. It is invoked in ``detect`` mode
with ``--report-format json --report-path <file>`` so its native JSON report (a
flat array of leak objects) is written to a file and parsed into :class:`Finding`
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
        # Secrets are repo-wide, not per-changed-file: scan the whole source tree
        # (the cloned repo root), NOT just the first scoped path. Scoping secret
        # detection to a single changed file misses secrets everywhere else.
        source = self._source
        # Write the JSON report to a temp FILE rather than stdout ("-"): gitleaks
        # 8.18+ does not reliably emit the JSON array on stdout (only the human
        # summary, on stderr), which silently dropped real findings. A report file
        # is version-robust and matches the bandit/njsscan adapters.
        report = base.new_temp_report(".json")
        try:
            command = [
                "gitleaks",
                "detect",
                "--no-git",
                "--source",
                source,
                "--report-format",
                "json",
                "--report-path",
                report,
            ]
            result = base.run_scanner(
                command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
            )
            text = base.read_report(report)
            # Gitleaks exits 0 (no leaks) or 1 (leaks found); both write the JSON
            # array to the report file. Higher exit codes indicate a real error.
            if not text.strip():
                if result.returncode >= 2:
                    raise ScannerError(
                        self.name,
                        f"exited {result.returncode}: {result.stderr.strip()[:500]}",
                    )
                return []
            payload = base.load_json(text, scanner_name=self.name, stderr=result.stderr)
            return self.parse(payload)
        finally:
            base.cleanup(report)

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
