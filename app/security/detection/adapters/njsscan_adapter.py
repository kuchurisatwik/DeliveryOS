"""njsscan scanner adapter — JavaScript/TypeScript SAST (MobSF njsscan).

njsscan is a static analyzer focused on insecure Node.js / JavaScript / TypeScript
patterns: SQL injection, command injection (``child_process``), ``eval`` code
injection, path traversal, insecure crypto, hardcoded secrets, and Express/
template XSS. It complements Semgrep and CodeQL for the JS/TS ecosystem — in
testing, Semgrep/CodeQL missed some JS/TS sinks that njsscan catches.

The tool is invoked with ``--json`` (report written to a file to avoid stdout
banner pollution). Its native JSON groups results by section (``nodejs`` /
``templates`` / ``secrets``), each mapping a rule id to ``{files, metadata}``.

The adapter is **language-gated**: it only runs when the scan scope contains
JavaScript/TypeScript, otherwise it returns no findings without invoking the tool
(so it never fails a Python-only or Go-only scan).
"""

from __future__ import annotations

from typing import Any, Mapping

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.detection import languages as lang
from app.security.models import Finding, ScanScope, Severity

# njsscan metadata.severity vocabulary -> shared Severity.
_NJSSCAN_SEVERITY: dict[str, Severity] = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
    "GOOD": Severity.INFO,
}

#: The JSON sections njsscan emits, each a ``{rule_id: {files, metadata}}`` map.
_RESULT_SECTIONS = ("nodejs", "templates", "secrets")

#: Languages that make njsscan worth running.
_JS_TS_LANGUAGES = frozenset({"javascript", "typescript"})


class NjsscanAdapter:
    """Runs njsscan over scoped JS/TS files and parses its JSON report."""

    name = "njsscan"

    def __init__(self, *, cwd: str | None = None, timeout: int = base.DEFAULT_TIMEOUT) -> None:
        self._cwd = cwd
        self._timeout = timeout

    def _applies_to(self, scope: ScanScope) -> bool:
        """True when the scope contains JavaScript/TypeScript (else skip the tool)."""
        detected = lang.detect_languages(scope.paths, cwd=self._cwd)
        return bool(detected & _JS_TS_LANGUAGES)

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []
        # Language gate: only run when JS/TS is present in the scope.
        if not self._applies_to(scope):
            return []

        report = base.new_temp_report(".json")
        try:
            command = ["njsscan", "--json", "-o", report, *scope.paths]
            result = base.run_scanner(
                command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
            )
            text = base.read_report(report)
            # njsscan exits non-zero when it finds issues; a genuine failure leaves
            # no report file behind.
            if not text.strip():
                if result.returncode not in (0, 1):
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
    def parse(cls, payload: Mapping[str, Any]) -> list[Finding]:
        """Parse njsscan's native JSON report into :class:`Finding` objects (pure)."""
        findings: list[Finding] = []
        for section in _RESULT_SECTIONS:
            rules = payload.get(section) or {}
            if not isinstance(rules, Mapping):
                continue
            for rule_id, entry in rules.items():
                if not isinstance(entry, Mapping):
                    continue
                metadata = entry.get("metadata") or {}
                severity = base.map_severity(
                    metadata.get("severity"), _NJSSCAN_SEVERITY, Severity.MEDIUM
                )
                message = (
                    metadata.get("description")
                    or metadata.get("owasp")
                    or str(rule_id)
                )
                for file_entry in entry.get("files") or []:
                    if not isinstance(file_entry, Mapping):
                        continue
                    match_lines = file_entry.get("match_lines") or []
                    start = match_lines[0] if match_lines else None
                    end = match_lines[1] if len(match_lines) > 1 else start
                    location = base.make_location(
                        file_entry.get("file_path"), start, end
                    )
                    findings.append(
                        Finding(
                            scanner=cls.name,
                            rule_id=str(rule_id),
                            location=location,
                            severity=severity,
                            message=message,
                            raw=dict(file_entry),
                        )
                    )
        return findings
