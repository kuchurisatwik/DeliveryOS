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

import os
import tempfile
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
        database: str | None = None,
        source_root: str | None = None,
        query_suite: str = "codeql/python-queries",
        language: str = "python",
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        self._database = database
        self._source_root = source_root
        self._query_suite = query_suite
        self._language = language
        self._cwd = cwd
        self._timeout = timeout

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []

        # CodeQL analyses a prebuilt *database*, so we build one from the scanned
        # source root first (nothing else in the pipeline creates it). The source
        # root is the cloned workspace; findings are filtered back down to the
        # ScanScope after analysis so the adapter still honours the shared scope.
        source_root = self._source_root or self._cwd or "."
        db_dir = self._database or os.path.join(
            tempfile.gettempdir(), f"codeql-db-{self._language}"
        )

        # 1. Build the database (Python needs no explicit build command).
        create = base.run_scanner(
            [
                "codeql",
                "database",
                "create",
                db_dir,
                f"--language={self._language}",
                f"--source-root={source_root}",
                "--overwrite",
                "--quiet",
            ],
            scanner_name=self.name,
            cwd=self._cwd,
            timeout=self._timeout,
        )
        if create.returncode != 0:
            raise ScannerError(
                self.name,
                f"database create exited {create.returncode}: {create.stderr.strip()[:500]}",
            )

        # 2. Analyze the database, writing SARIF to a file (NOT stdout): CodeQL
        # streams its query-evaluation progress to stdout, which collided with a
        # `--output=-` SARIF stream and broke JSON parsing. `--download` fetches
        # the query pack from the registry when absent.
        sarif = base.new_temp_report(".sarif")
        try:
            result = base.run_scanner(
                [
                    "codeql",
                    "database",
                    "analyze",
                    db_dir,
                    self._query_suite,
                    "--format=sarif-latest",
                    f"--output={sarif}",
                    "--download",
                ],
                scanner_name=self.name,
                cwd=self._cwd,
                timeout=self._timeout,
            )
            text = base.read_report(sarif)
            if result.returncode != 0 and not text.strip():
                raise ScannerError(
                    self.name, f"exited {result.returncode}: {result.stderr.strip()[:500]}"
                )
            payload = base.load_json(text, scanner_name=self.name, stderr=result.stderr)
            findings = self.parse(payload)
            return _filter_to_scope(findings, scope)
        finally:
            base.cleanup(sarif)

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
