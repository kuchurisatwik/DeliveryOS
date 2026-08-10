"""Nuclei adapter — known-vulnerability detection against a running target.

Nuclei runs a large set of community "templates" (declarative YAML checks) against
a URL. Each template says *send this request, look for this exact signature*, so a
match is almost never a guess — which is why this is the one DAST tool that can be
gated on from day one.

Its limit is the flip side of the same property: it only finds what someone has
already written a template for. It will never find a bug we wrote last week. That
is ZAP's job.

Design notes:

* ``scan()`` is impure (runs the binary); :meth:`NucleiAdapter.parse` is a pure
  classmethod over decoded JSONL events, so tests use a saved fixture and never
  touch the network.
* Templates are **pinned** to a directory baked into the image and update checks
  are disabled. Templates are executable code — they issue HTTP requests, and the
  ``code`` protocol runs commands — so letting them silently auto-update would mean
  the thing deciding whether our build passes changes without review.
* Requests are rate limited. Our target is typically one uvicorn worker; at full
  speed nuclei jams the door, requests time out, and timed-out templates report
  nothing — a scan that looks clean because it never landed.
"""

from __future__ import annotations

import re
import time
from typing import Any, Iterable, Sequence

from app.security.detection.adapters import base as sast_base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, Severity
from dast.adapters.base import load_jsonl, make_web_location
from dast.config import dast_settings
from dast.models import DastScope, ScanOutcome, ToolActivity

#: Nuclei's severity vocabulary maps 1:1 onto the shared enum — no translation loss.
_SEVERITY_MAP: dict[str, Severity] = {
    "INFO": Severity.INFO,
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}

#: Nuclei's protocol (``type``) → the shared finding category. One tool produces
#: several kinds of finding, so category is set per-finding rather than per-scanner
#: (the same approach the Trivy adapter takes on the SAST side).
_CATEGORY_BY_PROTOCOL: dict[str, str] = {
    "ssl": "tls",
    "network": "network",
    "tcp": "network",
    "dns": "network",
    "whois": "network",
}
DEFAULT_CATEGORY = "dast"

#: Nuclei logs this to stderr before scanning. Necessary but NOT sufficient as a
#: liveness signal — it counts templates read off disk, not requests that reached
#: the target. See :data:`_STATS_LINE`.
_TEMPLATES_LOADED = re.compile(r"Templates loaded for current scan:\s*(\d+)")

#: The ``-stats`` progress output, which is the *real* liveness signal: ``requests``
#: proves traffic actually left the scanner, ``errors`` proves whether it arrived.
#: Nuclei emits this periodically in ONE OF TWO formats, and which one you get
#: depends on other flags — with ``-jsonl`` it silently switches to JSON:
#:   [0:00:31] | Templates: 6915 | ... | Errors: 0 | Requests: 6915/6915 (100%)
#:   {"duration":"0:01:24","errors":"54","requests":"3881","matched":"3",...}
#: Both are matched so the signal cannot go missing because a flag changed.
_STATS_REQUESTS = (
    re.compile(r"Requests:\s*(\d+)/\d+"),
    re.compile(r'"requests"\s*:\s*"?(\d+)"?'),
)
_STATS_ERRORS = (
    re.compile(r"Errors:\s*(\d+)"),
    re.compile(r'"errors"\s*:\s*"?(\d+)"?'),
)
#: Emitted per request that exceeded the per-request timeout.
_TIMEOUT_HINT = re.compile(r"context deadline exceeded|Timeout", re.IGNORECASE)


class NucleiAdapter:
    """Runs nuclei against a live target and returns shared ``Finding`` objects."""

    name = "nuclei"
    #: Read-only: nuclei mostly issues GETs against known paths (destructive
    #: template tags are excluded by config), so it is safe to run concurrently
    #: with other read-only tools, and safe enough to point at production.
    mutating = False

    def __init__(
        self,
        *,
        templates: str | None = None,
        severity: str | None = None,
        exclude_tags: str | None = None,
        rate_limit: int | None = None,
        concurrency: int | None = None,
        timeout: int | None = None,
        binary: str = "nuclei",
    ) -> None:
        self._templates = templates or dast_settings.DAST_NUCLEI_TEMPLATES
        self._severity = severity or dast_settings.DAST_NUCLEI_SEVERITY
        self._exclude_tags = (
            exclude_tags
            if exclude_tags is not None
            else dast_settings.DAST_NUCLEI_EXCLUDE_TAGS
        )
        self._rate_limit = rate_limit or dast_settings.DAST_NUCLEI_RATE_LIMIT
        self._concurrency = concurrency or dast_settings.DAST_NUCLEI_CONCURRENCY
        self._timeout = timeout or dast_settings.DAST_NUCLEI_TIMEOUT
        self._binary = binary

    # ------------------------------------------------------------------ #
    # Impure: run the tool
    # ------------------------------------------------------------------ #
    def scan(self, scope: DastScope) -> ScanOutcome:
        report = sast_base.new_temp_report(".jsonl")
        started = time.monotonic()
        try:
            result = sast_base.run_scanner(
                self._build_command(scope, report),
                scanner_name=self.name,
                timeout=self._timeout,
            )
            duration = time.monotonic() - started

            # Nuclei splits its diagnostics across both streams — the banner and
            # warnings go to stderr, the -stats progress line to stdout. Scan the
            # combined text so the liveness signal cannot be missed depending on
            # which stream a given nuclei build happens to use.
            diagnostics = f"{result.stderr}\n{result.stdout}"

            templates_loaded = _extract_int(_TEMPLATES_LOADED, diagnostics)
            activity = ToolActivity(
                units_executed=templates_loaded,
                # Read the LAST stats line — it carries the final totals.
                requests_made=_extract_last_int(_STATS_REQUESTS, diagnostics),
                request_errors=_extract_last_int(_STATS_ERRORS, diagnostics) or 0,
                timeouts=len(_TIMEOUT_HINT.findall(diagnostics)),
                exit_code=result.returncode,
                duration_seconds=round(duration, 2),
            )

            # An empty report is legitimate — it means nothing matched. But an
            # empty report from a run that loaded no templates means the scan never
            # happened, and reporting that as "clean" is the failure mode this
            # whole service exists to avoid.
            if templates_loaded == 0:
                raise ScannerError(
                    self.name,
                    "no templates loaded — check the pinned template path "
                    f"'{self._templates}' and the severity/tag filters",
                )
            if result.returncode != 0 and templates_loaded is None:
                raise ScannerError(
                    self.name,
                    f"exited {result.returncode}: {result.stderr.strip()[:500]}",
                )

            events = load_jsonl(
                sast_base.read_report(report), scanner_name=self.name
            )
            return ScanOutcome(
                findings=tuple(self.parse(events, spec_paths=scope.spec_paths)),
                activity=activity,
            )
        finally:
            sast_base.cleanup(report)

    def _build_command(self, scope: DastScope, report: str) -> list[str]:
        command = [
            self._binary,
            "-target", scope.target_url,
            "-jsonl",
            "-output", report,
            "-templates", self._templates,
            # Never phone home for template updates mid-scan: the pinned set in the
            # image is the reviewed set, and a scan must be reproducible.
            "-disable-update-check",
            "-rate-limit", str(self._rate_limit),
            "-concurrency", str(self._concurrency),
            # Do not colourise stderr — we parse it for the liveness signal.
            "-no-color",
            # Emit the progress/stats line. This is what proves requests actually
            # reached the target; without it a scan that resolved no DNS and sent
            # nothing is indistinguishable from a clean result.
            "-stats",
        ]
        if self._severity:
            command += ["-severity", self._severity]
        if self._exclude_tags:
            command += ["-exclude-tags", self._exclude_tags]
        if scope.auth_header:
            command += ["-header", f"Authorization: {scope.auth_header}"]

        # Out-of-band detection calls an interact.sh server to catch blind
        # SSRF/RCE. The default server is public, so target hostnames and payload
        # data would leave our network on every scan. Off unless self-hosted.
        if dast_settings.DAST_NUCLEI_INTERACTSH:
            if dast_settings.DAST_NUCLEI_INTERACTSH_SERVER:
                command += [
                    "-interactsh-server",
                    dast_settings.DAST_NUCLEI_INTERACTSH_SERVER,
                ]
        else:
            command.append("-no-interactsh")
        return command

    # ------------------------------------------------------------------ #
    # Pure: parse the payload
    # ------------------------------------------------------------------ #
    @classmethod
    def parse(
        cls, events: Sequence[Any], *, spec_paths: Iterable[str] = ()
    ) -> list[Finding]:
        """Convert decoded nuclei JSONL events into shared ``Finding`` objects.

        Pure and deterministic — unit-testable against a saved fixture.
        """
        findings: list[Finding] = []
        spec = tuple(spec_paths)

        for event in events:
            if not isinstance(event, dict):
                continue
            info = event.get("info") or {}
            protocol = str(event.get("type") or "").lower()

            # ``matched-at`` is the exact URL (or host:port) that fired; fall back
            # to the host when a template does not report one.
            matched_at = event.get("matched-at") or event.get("host") or ""

            findings.append(
                Finding(
                    scanner=cls.name,
                    # The template id is nuclei's stable identifier. The human-
                    # readable name gets reworded between releases, and since the
                    # rule id feeds the finding hash, using the name would re-ID
                    # every finding on a template bump.
                    rule_id=str(event.get("template-id") or "unknown-template"),
                    location=make_web_location(
                        str(matched_at),
                        param=event.get("matcher-name") or None,
                        spec_paths=spec,
                    ),
                    severity=sast_base.map_severity(
                        info.get("severity"), _SEVERITY_MAP, Severity.MEDIUM
                    ),
                    message=_build_message(info, event),
                    raw=dict(event),
                    category=_CATEGORY_BY_PROTOCOL.get(protocol, DEFAULT_CATEGORY),
                )
            )
        return findings


def _build_message(info: dict[str, Any], event: dict[str, Any]) -> str:
    """Human-readable summary: what matched, and where."""
    name = str(info.get("name") or "Nuclei template matched").strip()
    matcher = event.get("matcher-name")
    if matcher:
        name = f"{name} ({matcher})"
    cves = ((info.get("classification") or {}).get("cve-id")) or []
    if cves:
        name = f"{name} [{', '.join(str(c).upper() for c in cves)}]"
    return name


def _extract_int(pattern: re.Pattern[str], text: str) -> int | None:
    """Pull the first integer captured by ``pattern`` from ``text``, if present."""
    match = pattern.search(text or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def _extract_last_int(
    patterns: Sequence[re.Pattern[str]] | re.Pattern[str], text: str
) -> int | None:
    """Pull the LAST integer matched by any of ``patterns`` from ``text``.

    ``-stats`` prints a progress update every few seconds; only the final one
    holds the totals for the whole run. Several alternative patterns are accepted
    because nuclei renders those stats differently depending on the other flags.
    """
    candidates = [patterns] if isinstance(patterns, re.Pattern) else list(patterns)
    for pattern in candidates:
        matches = pattern.findall(text or "")
        if matches:
            try:
                return int(matches[-1])
            except (TypeError, ValueError):  # pragma: no cover - defensive
                continue
    return None
