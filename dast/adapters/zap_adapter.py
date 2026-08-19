"""ZAP adapter — finding *our own* injection/XSS/access-control flaws.

Where :class:`~dast.adapters.nuclei_adapter.NucleiAdapter` answers "are we exposed
to anything already publicly known?", the ``ZapAdapter`` answers "does *our own
code* have a bug we wrote last week?". ZAP only attacks URLs already on its internal
site tree, so an unseeded scan reports a false all-clear — making that failure mode
impossible to report as clean is the point of the surrounding :mod:`dast.runner`
trust model, not of this parser.

Design notes:

* One adapter instance carries exactly one ``mutating`` flag, chosen at construction
  by ``active``. A passive instance (``"zap-passive"``, ``mutating = False``) runs in
  the concurrent read-only tier alongside nuclei; an active instance
  (``"zap-active"``, ``mutating = True``) runs serialised in the mutating tier. The
  profile decides *which instances exist*, so the runner reads ``mutating`` once.
* ``scan()`` is impure (drives the ZAP daemon over REST); :meth:`ZapAdapter.parse`
  is a pure classmethod over ZAP's decoded alert JSON, so tests use a saved fixture
  and never touch the network — mirroring ``NucleiAdapter``.
* Both faces share the same ``rule_id``/endpoint-identity chain, so a finding seen
  passively and confirmed actively still dedupes to one ``finding_id``. Active
  findings are marked ``advisory`` so they never gate a release (Req 6.5).
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from app.security.detection.adapters import base as sast_base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, Severity
from app.utils.logger import logger
from dast.adapters.base import make_web_location
from dast.config import DastSettings, dast_settings
from dast.models import DastScope, ScanOutcome, ToolActivity

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    # The REST plumbing lives in a sibling module implemented in parallel; import it
    # only for annotations so this module compiles even before that file lands.
    from dast.adapters.zap_client import ZapClient

#: ZAP's risk vocabulary → the shared enum. ZAP has no "critical" band — its top
#: risk is "High" — so the map tops out there. ``map_severity`` upper-cases the key,
#: so entries are upper-case; both ZAP's spelled-out "Informational" and the short
#: "Info" fold onto :attr:`Severity.INFO`.
_SEVERITY_MAP: dict[str, Severity] = {
    "INFORMATIONAL": Severity.INFO,
    "INFO": Severity.INFO,
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
}

#: ZAP's numeric risk code, used as a fallback when the spelled-out ``risk`` string
#: is absent: 0=Informational, 1=Low, 2=Medium, 3=High.
_RISKCODE_MAP: dict[str, Severity] = {
    "0": Severity.INFO,
    "1": Severity.LOW,
    "2": Severity.MEDIUM,
    "3": Severity.HIGH,
}

DEFAULT_CATEGORY = "dast"


class ZapAdapter:
    """Runs OWASP ZAP against a live target and returns shared ``Finding`` objects.

    Two construction modes, selected by ``active``: passive (read-only, concurrent)
    and active (mutating, serialised). ``name`` and ``mutating`` are set per-instance
    from that flag so the runner tiers the two faces correctly.
    """

    def __init__(
        self,
        *,
        active: bool,
        client: "ZapClient | None" = None,
        settings: DastSettings = dast_settings,
    ) -> None:
        self._active = active
        #: Distinct names so the two tiers appear as separate ``coverage`` and
        #: baseline entries; both share the same ``rule_id``/endpoint identity.
        self.name = "zap-active" if active else "zap-passive"
        #: Active scanning sends attack payloads and mutates target state, so it must
        #: be serialised; passive scanning is read-only and runs concurrently.
        self.mutating = active
        self._client = client
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Impure: drive the tool (implemented in task 5.1)
    # ------------------------------------------------------------------ #
    def scan(self, scope: DastScope) -> ScanOutcome:
        """Drive one ZAP scan against ``scope`` and return findings + evidence.

        Orchestrates the fixed sequence from the design: reachability → fresh
        session → logout exclusion → auth injection → seed from the OpenAPI spec →
        start-of-scan canary → passive scan → (active scan, active adapter only) →
        alerts + request evidence → end-of-scan canary → under-seeding tolerance →
        ``ScanOutcome``.

        Two channels signal an untrustworthy run, matching the runner's contract:

        * **Hard failures** (unreachable sidecar, unseeded map, broken/regressed
          canary, under-seeded map, production refusal) raise
          :class:`ScannerError`; :func:`dast.runner._run_one` records an
          ``incomplete`` coverage entry with the reason and keeps scanning the
          other tools.
        * **Soft evidence** (zero requests, all-errors, timeout flood) is returned
          in a truthful :class:`ToolActivity`; the existing ``_assess_activity``
          classifies it.

        The whole point is that there is no path to a clean, empty, ``complete``
        ZAP result without the scanner having demonstrably reached and exercised
        the target.
        """
        # Import here (rather than at module load) so the module still compiles if
        # the REST wrapper is unavailable, and so tests can inject a fake client
        # without the real one ever being constructed.
        from dast.adapters.zap_client import ZapClient

        settings = self._settings
        # When no client was injected we own the one we build and must close it;
        # an injected client (tests, or a shared instance) is the caller's to close.
        owns_client = self._client is None
        client = self._client or ZapClient(settings=settings)
        started = time.monotonic()
        try:
            # 1. Reachability (Req 1.3, 13.1) — abort before issuing scan commands.
            client.reachable()

            # 2. Fresh session (Req 2.1, 2.2) — empty site tree + no prior alerts, so
            #    last week's findings cannot bleed into this scan (Req 2.3 on failure).
            client.new_session(self._session_name(scope))

            # 3. Logout exclusion (Req 4.1, 4.2) — registered before ANY traffic so
            #    seeding, passive, and active phases all leave the logout URL alone.
            if settings.DAST_ZAP_LOGOUT_EXCLUDE:
                client.exclude_from_scan(settings.DAST_ZAP_LOGOUT_EXCLUDE)

            # Rate limit (Req 12.2) — cap outgoing req/s so a single-worker target is
            # not jammed into timing out (a scan that looks clean because it never
            # landed). Applied to the scan policy before any request is sent.
            client.set_rate_limit(settings.DAST_ZAP_RATE_LIMIT)

            # 4. Auth injection (Req 3.1-3.3) — one replacer rule stamps the header on
            #    EVERY outgoing request (seed/passive/active). Unset ⇒ scan anonymously
            #    (Req 3.2): skip the rule entirely rather than sending a blank header.
            if scope.auth_header:
                client.set_replacer_rule(scope.auth_header)

            # 5. Seed the site tree from the spec (Req 5.1-5.4). ZAP only attacks URLs
            #    already on its map, so an unseeded scan is a false all-clear — refuse
            #    to continue as clean (Req 5.3). Import by URL so the request carries
            #    the auth replacer rule (Req 5.4).
            if not scope.spec_paths:
                raise ScannerError(self.name, "site tree not seeded from spec")
            # Prefer the spec the service synthesised from the source-extracted
            # endpoint inventory (served back to us at ``scope.spec_url``) so a
            # target that publishes no ``/openapi.json`` of its own is still seeded
            # from our inventory. Falling back to the target's own spec path keeps
            # spec-publishing targets behaving exactly as before. Either way the
            # import flows through ZAP and so carries the auth replacer (Req 5.4),
            # and ``target_url`` is the host override so paths resolve to the target.
            spec_url = scope.spec_url or (
                scope.target_url.rstrip("/") + settings.DAST_OPENAPI_PATH
            )
            client.import_openapi(spec_url, target_url=scope.target_url)
            # Endpoints ZAP actually placed on the map — the "units" it executed
            # (Req 5.2); an empty map is zero units and reads as incomplete.
            seeded_count = len(client.urls(base_url=scope.target_url))

            # 6. Passive scan (Req 6.1) — always runs, both profiles; sends no attack
            #    payloads. Drain ZAP's passive queue for the seeding traffic *before*
            #    the start-of-scan canary check: the canary is a passive detection on
            #    the seeded canary route, so its alert only exists once the passive
            #    queue has processed the seeding responses. Checking the canary before
            #    this drain races the async passive scanner and reads a false negative.
            client.passive_scan_wait()

            # 7. Start-of-scan canary (Req 7.1, 7.3) — the deliberately vulnerable
            #    route proves ZAP's own detection works. If it cannot be flagged, no
            #    "clean" result from this run is trustworthy.
            canary_path = settings.DAST_ZAP_CANARY_PATH
            if not client.canary_detected(canary_path):
                raise ScannerError(
                    self.name, "scanner's own detection is not working"
                )

            # 8. Active scan (Req 6.2, 6.3) — only on the active adapter, and never
            #    against a production target: refuse, send zero payloads, and record
            #    the refusal as incomplete (Req 6.4). The passive adapter is
            #    unaffected, so production still gets passive coverage. Drain the
            #    passive queue again afterwards so passive rules that fired on the
            #    active-scan traffic are captured in the alerts collected below.
            if self._active:
                prod_pattern = settings.DAST_ZAP_PROD_URL_PATTERN
                if prod_pattern and re.search(prod_pattern, scope.target_url):
                    raise ScannerError(
                        self.name, "active scan refused against production target"
                    )
                client.active_scan(scope.target_url)
                client.passive_scan_wait()

            # 9. Collect alerts + request evidence (Req 8.1, 9.3). Counts come from
            #    ZAP's OWN counters, never inferred, so a blind scan cannot read clean.
            alerts = client.alerts(base_url=scope.target_url)
            requests_made = client.requests_made(base_url=scope.target_url)
            request_errors = client.request_errors()
            timeouts = client.timeouts()

            # 10. End-of-scan canary (Req 7.2, 7.4, 7.5) — detected at start but gone
            #     at the end means something began blocking the scanner mid-scan;
            #     detected at both boundaries means the alarm held for the whole run.
            if not client.canary_detected(canary_path):
                raise ScannerError(
                    self.name, "something began blocking the scanner mid-scan"
                )

            # 11. Under-seeding tolerance (Req 10.1, 10.2) — the spec count is known
            #     only to the adapter, so surface a short map as a hard failure with
            #     an explicit D-of-N reason rather than a quiet clean result.
            spec_count = len(scope.spec_paths)
            if spec_count and seeded_count < settings.DAST_ZAP_COVERAGE_TOLERANCE * spec_count:
                raise ScannerError(
                    self.name,
                    f"map under-seeded: {seeded_count} of {spec_count} endpoints",
                )

            # 12. Build the outcome. Active-scan findings are advisory (Req 6.5) so the
            #     eventual gate treats them as report-only.
            activity = ToolActivity(
                units_executed=seeded_count,
                requests_made=requests_made,
                request_errors=request_errors,
                timeouts=timeouts,
                duration_seconds=round(time.monotonic() - started, 2),
            )
            findings = self.parse(
                alerts,
                spec_paths=scope.spec_paths,
                scanner_name=self.name,
                advisory=self._active,
            )
            logger.info(
                "ZAP %s scan complete: %d finding(s), %d endpoint(s) seeded, "
                "%s request(s) made",
                self.name,
                len(findings),
                seeded_count,
                requests_made,
            )
            return ScanOutcome(findings=tuple(findings), activity=activity)
        finally:
            if owns_client:
                client.close()

    def _session_name(self, scope: DastScope) -> str:
        """A per-scan session name, unique enough to avoid re-using stale state."""
        stamp = int(time.time() * 1000)
        commit = scope.commit_sha or "nocommit"
        return f"dast-{self.name}-{commit}-{stamp}"

    # ------------------------------------------------------------------ #
    # Pure: parse the payload
    # ------------------------------------------------------------------ #
    @classmethod
    def parse(
        cls,
        alerts: Sequence[Any],
        *,
        spec_paths: Iterable[str] = (),
        scanner_name: str = "zap",
        advisory: bool = False,
    ) -> list[Finding]:
        """Convert decoded ZAP alert objects into shared ``Finding`` objects.

        Pure and deterministic — unit-testable against a saved ``core.alerts``
        fixture with no network. ``advisory`` is stamped onto every produced finding
        (``True`` for active-scan findings, ``False`` for passive), so the eventual
        gate can treat active findings as report-only.
        """
        findings: list[Finding] = []
        spec = tuple(spec_paths)

        for alert in alerts:
            if not isinstance(alert, dict):
                continue

            # ``url`` is the exact request that fired; fall back to an empty string
            # so ``make_web_location`` still produces a stable (host-less) identity.
            url = str(alert.get("url") or "")
            method = alert.get("method") or None
            param = alert.get("param") or None

            findings.append(
                Finding(
                    scanner=scanner_name,
                    # ``pluginId`` is ZAP's stable rule identifier. The human-readable
                    # ``alert``/``name`` gets reworded between releases, and since the
                    # rule id feeds the finding hash, using the name would re-ID every
                    # finding on a ZAP bump.
                    rule_id=str(alert.get("pluginId") or "unknown-plugin"),
                    location=make_web_location(
                        url,
                        method=str(method) if method else None,
                        param=str(param) if param else None,
                        spec_paths=spec,
                    ),
                    severity=_map_zap_severity(alert),
                    message=_build_message(alert),
                    raw=dict(alert),
                    category=DEFAULT_CATEGORY,
                    advisory=advisory,
                )
            )
        return findings


def _map_zap_severity(alert: dict[str, Any]) -> Severity:
    """Map a ZAP alert's risk onto the shared enum.

    Prefers the spelled-out ``risk``/``riskdesc`` string; falls back to the numeric
    ``riskcode`` when the string is missing, and finally to ``MEDIUM``.
    """
    risk = alert.get("risk")
    if risk is None:
        # ``riskdesc`` is often "High (Medium)" — take the leading word.
        riskdesc = alert.get("riskdesc")
        if isinstance(riskdesc, str) and riskdesc.strip():
            risk = riskdesc.split("(")[0]
    if risk is not None:
        return sast_base.map_severity(str(risk), _SEVERITY_MAP, Severity.MEDIUM)
    riskcode = alert.get("riskcode")
    if riskcode is not None:
        return _RISKCODE_MAP.get(str(riskcode).strip(), Severity.MEDIUM)
    return Severity.MEDIUM


def _build_message(alert: dict[str, Any]) -> str:
    """Human-readable summary: what fired, and on which parameter."""
    name = str(
        alert.get("alert") or alert.get("name") or "ZAP alert"
    ).strip()
    param = alert.get("param")
    if param:
        name = f"{name} (param: {param})"
    return name
