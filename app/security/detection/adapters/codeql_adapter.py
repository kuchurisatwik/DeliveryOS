"""CodeQL scanner adapter (Requirement 4.3).

CodeQL performs semantic / data-flow analysis: multi-function SQL injection,
taint flow, authorization bypass, and resource leaks. Analysis runs against a
prebuilt CodeQL database and emits SARIF (``--format=sarif-latest``), which is
parsed via the shared SARIF parser into the :class:`Finding` type.

CodeQL is multi-language. When no explicit ``language`` is pinned, the adapter
detects the languages present in the scan scope and builds + analyses **one
database per supported language** (JavaScript/TypeScript, Java/Kotlin, C#, Go,
C/C++, Ruby, Python), unioning the findings. Each language is isolated: a failed
build/analysis for one language (e.g. autobuild failing for a compiled language)
is logged and skipped without losing the others; the scanner only fails as a
whole when *every* attempted language fails. When no CodeQL-supported language is
detected it falls back to Python, preserving the previous behavior.

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
from app.security.detection import languages as lang
from app.security.models import Finding, ScanScope, Severity
from app.utils.logger import logger


class CodeQLAdapter:
    """Analyses one CodeQL database per detected language and parses the SARIF."""

    name = "codeql"

    def __init__(
        self,
        *,
        database: str | None = None,
        source_root: str | None = None,
        query_suite: str | None = None,
        language: str | None = None,
        languages: tuple[str, ...] | None = None,
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        self._database = database
        self._source_root = source_root
        # An explicit (language, query_suite) pins a single language and disables
        # auto-detection (used by tests / overrides). ``languages`` pins an
        # explicit CodeQL language-id set. Both ``None`` => auto-detect from scope.
        self._query_suite = query_suite
        self._language = language
        self._explicit_languages = languages
        self._cwd = cwd
        self._timeout = timeout

    def _resolve_targets(self, scope: ScanScope) -> tuple[tuple[str, str], ...]:
        """Return the ``(codeql_language_id, query_suite)`` targets to analyse."""
        # 1. A fully-pinned single language (back-compat / explicit override).
        if self._language is not None:
            suite = self._query_suite or lang.codeql_suite_for(self._language)
            return ((self._language, suite),)
        # 2. An explicit CodeQL language-id list.
        if self._explicit_languages:
            return tuple(
                (lid, f"codeql/{lid}-queries") for lid in self._explicit_languages
            )
        # 3. Auto-detect from the scope (honouring the SECURITY_LANGUAGES override).
        detected = lang.effective_languages(scope.paths, cwd=self._cwd)
        targets = lang.codeql_targets_for(detected)
        if not targets:
            # No CodeQL-supported language detected → preserve prior behavior by
            # analysing Python (harmless no-op when there is no Python).
            return (("python", lang.codeql_suite_for("python")),)
        if not lang.codeql_compiled_enabled():
            # Compiled languages need a working autobuild (the main cost/failure
            # risk), so they are opt-in. Drop them unless explicitly enabled.
            targets = tuple(
                t for t in targets if t[0] not in lang.CODEQL_COMPILED_LANGUAGES
            )
        return targets

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []

        source_root = self._source_root or self._cwd or "."
        targets = self._resolve_targets(scope)

        all_findings: list[Finding] = []
        failures: list[str] = []
        for language_id, query_suite in targets:
            try:
                all_findings.extend(
                    self._scan_language(language_id, query_suite, source_root)
                )
            except ScannerError as exc:
                # Per-language isolation: one language failing (e.g. a compiled
                # language whose autobuild failed) must not lose the others.
                logger.warning(
                    "CodeQL: language '%s' failed, continuing: %s",
                    language_id,
                    exc.reason,
                )
                failures.append(f"{language_id}: {exc.reason}")

        # Only fail the whole scanner when every attempted language failed.
        if failures and len(failures) == len(targets):
            raise ScannerError(
                self.name, "all language analyses failed — " + "; ".join(failures)
            )

        return _filter_to_scope(all_findings, scope)

    def _scan_language(
        self, language_id: str, query_suite: str, source_root: str
    ) -> list[Finding]:
        """Build and analyse a single-language CodeQL database → findings."""
        db_dir = self._database or os.path.join(
            tempfile.gettempdir(), f"codeql-db-{language_id}"
        )

        # 1. Build the database. Interpreted languages (python, javascript, ruby)
        # need no build; compiled languages rely on CodeQL's default autobuild,
        # which may fail — that surfaces as a per-language ScannerError above.
        create = base.run_scanner(
            [
                "codeql",
                "database",
                "create",
                db_dir,
                f"--language={language_id}",
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
                    query_suite,
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
            return self.parse(payload)
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
