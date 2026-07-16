"""Semgrep scanner adapter (Requirement 4.2).

Semgrep runs pattern-based rules covering injection and web-app flaws: SQL
injection, command injection, XSS, SSRF, path traversal, authentication /
authorization flaws, plus company-specific rules. It is invoked with ``--json``
and its native JSON ``results`` array is parsed into the shared :class:`Finding`
type.

Semgrep is multi-language. When no explicit ``config`` is supplied, the adapter
detects the languages present in the scan scope and selects the matching Semgrep
registry rule packs (always including the broad ``p/security-audit`` pack), so a
JavaScript/Java/Go/Ruby/… change gets language-appropriate rules instead of only
the Python pack. When nothing is detected it falls back to the historical
Python-centric defaults, so Python-only repositories behave exactly as before.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError
from app.security.detection import languages as lang
from app.security.models import Finding, ScanScope, Severity

# Semgrep `extra.severity` vocabulary -> shared Severity.
_SEMGREP_SEVERITY: dict[str, Severity] = {
    "INFO": Severity.INFO,
    "WARNING": Severity.MEDIUM,
    "ERROR": Severity.HIGH,
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}


class SemgrepAdapter:
    """Runs Semgrep over the scoped files and parses its JSON results."""

    name = "semgrep"

    #: Default rulesets. ``p/security-audit`` is Semgrep's broad security ruleset
    #: (injection, auth, crypto, deserialization, SSRF, path traversal, ...);
    #: ``p/python`` adds the Python-focused pack. Used only when no config is
    #: supplied *and* no languages are detected in the scope.
    DEFAULT_CONFIGS: tuple[str, ...] = lang.DEFAULT_SEMGREP_CONFIGS

    def __init__(
        self,
        *,
        config: str | tuple[str, ...] | list[str] | None = None,
        cwd: str | None = None,
        timeout: int = base.DEFAULT_TIMEOUT,
    ) -> None:
        # ``config is None`` means "auto-select from the scope's languages at scan
        # time"; an explicit config pins the rule packs (used by tests / overrides).
        if config is None:
            self._configs: tuple[str, ...] | None = None
        elif isinstance(config, str):
            self._configs = (config,)
        else:
            self._configs = tuple(config)
        self._cwd = cwd
        self._timeout = timeout

    def _resolve_configs(self, scope: ScanScope) -> tuple[str, ...]:
        """Pick rule packs: explicit override, else language-aware auto-selection."""
        if self._configs is not None:
            return self._configs
        detected = lang.effective_languages(scope.paths, cwd=self._cwd)
        return lang.semgrep_configs_for(detected)

    def scan(self, scope: ScanScope) -> list[Finding]:
        if not scope.paths:
            return []
        config_args: list[str] = []
        for cfg in self._resolve_configs(scope):
            config_args.extend(["--config", cfg])
        command = ["semgrep", *config_args, "--json", "--quiet", *scope.paths]
        result = base.run_scanner(
            command, scanner_name=self.name, cwd=self._cwd, timeout=self._timeout
        )
        # Semgrep exits 0 (clean) or 1 (findings) with a JSON report on stdout.
        # Exit codes >= 2 are fatal errors.
        if result.returncode >= 2 and not result.stdout.strip():
            raise ScannerError(
                self.name, f"exited {result.returncode}: {result.stderr.strip()}"
            )
        payload = base.load_json(result.stdout, scanner_name=self.name, stderr=result.stderr)
        return self.parse(payload)

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> list[Finding]:
        """Parse Semgrep's native JSON report into :class:`Finding` objects (pure)."""

        findings: list[Finding] = []
        for result in payload.get("results") or []:
            extra = result.get("extra") or {}
            start = (result.get("start") or {}).get("line")
            end = (result.get("end") or {}).get("line")
            location = base.make_location(result.get("path"), start, end)
            severity = base.map_severity(
                extra.get("severity"), _SEMGREP_SEVERITY, Severity.MEDIUM
            )
            findings.append(
                Finding(
                    scanner=cls.name,
                    rule_id=str(result.get("check_id") or "unknown"),
                    location=location,
                    severity=severity,
                    message=extra.get("message") or "",
                    raw=dict(result),
                )
            )
        return findings
