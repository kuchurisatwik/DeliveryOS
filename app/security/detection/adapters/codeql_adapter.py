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
import shutil
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
        commit_sha: str | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self._database = database
        self._source_root = source_root
        # Per-commit DB cache: when both a commit SHA and a cache dir are given,
        # the database is stored at a SHA-keyed path and reused if it already
        # exists (safe — same commit = same code = same DB). Only the newest DB
        # per language is kept, so the cache stays bounded to ~1 DB per language.
        self._commit_sha = (commit_sha or "").strip()
        self._cache_dir = (cache_dir or "").strip()
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

    def _resolve_db_dir(self, language_id: str) -> tuple[str, bool]:
        """Return ``(db_dir, is_valid_cache_hit)`` for a language.

        Precedence: explicit ``database`` override → SHA-keyed cache (when a
        commit SHA + cache dir are set) → a plain temp dir (no caching, preserves
        the original behavior for tests and the verification re-run).
        """
        if self._database:
            return self._database, False
        if self._cache_dir and self._commit_sha:
            db_dir = os.path.join(
                self._cache_dir, f"codeql-db-{language_id}-{self._commit_sha[:12]}"
            )
            return db_dir, _is_valid_db(db_dir)
        return os.path.join(tempfile.gettempdir(), f"codeql-db-{language_id}"), False

    def _prune_old_dbs(self, language_id: str, *, keep: str) -> None:
        """Delete cached DBs for ``language_id`` other than ``keep`` (bounds disk)."""
        if not (self._cache_dir and self._commit_sha):
            return
        prefix = f"codeql-db-{language_id}-"
        try:
            for name in os.listdir(self._cache_dir):
                if not name.startswith(prefix):
                    continue
                full = os.path.join(self._cache_dir, name)
                if os.path.abspath(full) == os.path.abspath(keep):
                    continue
                shutil.rmtree(full, ignore_errors=True)
        except OSError:  # pragma: no cover - best effort cleanup
            pass

    def _scan_language(
        self, language_id: str, query_suite: str, source_root: str
    ) -> list[Finding]:
        """Build and analyse a single-language CodeQL database → findings."""
        db_dir, cached = self._resolve_db_dir(language_id)

        # 1. Build the database, UNLESS a valid cached DB for this exact commit
        # already exists (same SHA = same code = same DB, so reuse is safe and
        # skips the expensive extraction). Interpreted languages need no build;
        # compiled languages rely on CodeQL autobuild.
        if cached:
            logger.info(
                "CodeQL: reusing cached %s database for commit %s (skipping build).",
                language_id, self._commit_sha[:12],
            )
        else:
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
            # New DB built: drop stale DBs for this language (other commits) so
            # the cache never grows beyond ~1 DB per language.
            self._prune_old_dbs(language_id, keep=db_dir)

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


def _is_valid_db(db_dir: str) -> bool:
    """True when ``db_dir`` looks like a complete CodeQL database (cache hit)."""
    # CodeQL writes 'codeql-database.yml' at the DB root once creation succeeds.
    return os.path.isfile(os.path.join(db_dir, "codeql-database.yml"))


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
