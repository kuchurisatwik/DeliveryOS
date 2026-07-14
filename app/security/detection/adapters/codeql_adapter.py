"""CodeQL scanner adapter (Requirement 4.3).

CodeQL performs semantic / data-flow analysis: multi-function SQL injection,
taint flow, authorization bypass, and resource leaks. Analysis runs against a
prebuilt CodeQL database and emits SARIF (``--format=sarif-latest``), which is
parsed via the shared SARIF parser into the :class:`Finding` type.

Because CodeQL analyses a whole database rather than a file list, findings are
filtered to the :class:`ScanScope` paths after parsing so the adapter honours
the shared scope like every other scanner.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, ScanScope, Severity


class CodeQLAdapter:
    """Analyses a CodeQL database and parses the SARIF output."""

    name = "codeql"

    def __init__(
        self,
        *,
        database: str = "codeql-db",
        query_suite: str = "python-security-and-quality.qls",
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        self._database = database
        self._query_suite = query_suite
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []
        # `--output -` writes SARIF to stdout so no temp file management is needed.
        command = [
            "codeql",
            "database",
            "analyze",
            self._database,
            self._query_suite,
            "--format=sarif-latest",
            "--output=-",
        ]
        result = base.run_scanner(
            command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
        )
        if result.returncode != 0 and not result.stdout.strip():
            raise ScannerError(
                self.name, f"exited {result.returncode}: {result.stderr.strip()}"
            )
        payload = base.load_json(result.stdout, scanner_name=self.name, stderr=result.stderr)
        findings = self.parse(payload)
        return _filter_to_scope(findings, scope)

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> list[Finding]:
        """Parse a CodeQL SARIF document into :class:`Finding` objects (pure)."""

        return base.parse_sarif(payload, scanner_name=cls.name, default_severity=Severity.MEDIUM)


def _filter_to_scope(findings: list[Finding], scope: ScanScope) -> list[Finding]:
    """Keep findings whose path lies within one of the scope paths."""

    scoped_paths = tuple(p.replace("\\", "/") for p in scope.paths)
    if not scoped_paths:
        return findings

    def in_scope(path: str) -> bool:
        normalized = path.replace("\\", "/")
        return any(
            normalized == sp or normalized.startswith(sp.rstrip("/") + "/") or sp in normalized
            for sp in scoped_paths
        )

    return [f for f in findings if in_scope(f.location.path)]
