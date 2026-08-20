"""ZapClient — a thin synchronous wrapper over OWASP ZAP's REST API.

ZAP runs as a long-lived daemon in its own container (Req 1.1, 1.2); this client
drives it over the REST API rather than starting a JVM per scan. It owns *no scan
policy* — it just exposes the ZAP operations the adapter needs, keyed by the ZAP
host, port, and API key read from :data:`dast.config.dast_settings`.

The single contract that matters to callers: **every method wraps transport failure
as** :class:`~app.security.detection.adapters.base.ScannerError`. A caller never has
to distinguish an ``httpx`` connection error, a non-200 REST response, or a
ZAP-reported error object — any of them surface as one ``ScannerError`` with a
human-readable reason, which the runner turns into an ``incomplete`` coverage entry
(Req 13.1, 13.2). This is why the client is the sole place that talks ``httpx``.

The REST surface (conceptual → ZAP component/action), all issued as HTTP GETs
against ``/JSON/{component}/{view|action}/{name}/``:

===============================  ===========================================
Purpose                          ZAP REST operation
===============================  ===========================================
Confirm sidecar reachable        ``core.version``
Fresh session per scan           ``core.newSession`` (unique name, overwrite)
Exclude logout URL               ``core.excludeFromProxy`` +
                                 ``spider.excludeFromScan`` +
                                 ``ascan.excludeFromScan``
Inject auth header everywhere    ``replacer.addRule`` (REQ_HEADER)
Seed site tree from spec         ``openapi.importUrl`` (fallback ``spider.scan``)
Passive scan                     poll ``pscan.recordsToScan`` to 0
Active scan                      ``ascan.scan`` started, ``ascan.status`` polled
Fetch alerts                     ``core.alerts`` (paged)
Request evidence                 ``core.numberOfMessages`` + ``stats.allSitesStats``
Canary detection                 query ``core.alerts`` for the canary path
===============================  ===========================================

The exact endpoint names are an implementation detail; the design commitments are
that request evidence is read from ZAP's *own* counters (never inferred) and that
transport failures are never swallowed into an empty-but-clean result.
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

import httpx

from app.security.detection.adapters.base import ScannerError
from app.utils.logger import logger
from dast.config import DastSettings, dast_settings

#: Scanner name used on every :class:`ScannerError` raised here and, downstream, on
#: the ``ToolActivity``/``ToolCoverage`` the adapter builds.
SCANNER_NAME = "zap"

#: ZAP replacer ``matchType`` for a request header rule — the mechanism that stamps
#: the Authorization header onto *every* outgoing request (seeding, passive, active).
_MATCH_TYPE_REQ_HEADER = "REQ_HEADER"

#: Default seconds between status polls while waiting for a scan phase to finish.
_DEFAULT_POLL_INTERVAL = 2.0

#: Per-REST-call HTTP timeout. Short: an individual REST call to the daemon is a
#: local, fast operation; long-running work (spider/active scan) is polled, not
#: blocked on. A hung REST call degrades to a ``ScannerError`` rather than stalling.
_REST_TIMEOUT = 30.0


class ZapClient:
    """Synchronous REST client for a single ZAP sidecar daemon.

    Keyed by host/port/API key from config. All methods raise
    :class:`ScannerError` on any transport or REST-level failure so callers do not
    have to catch ``httpx`` exceptions.
    """

    def __init__(
        self,
        *,
        settings: DastSettings = dast_settings,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
        import_timeout: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._host = host or settings.DAST_ZAP_HOST
        self._port = int(port if port is not None else settings.DAST_ZAP_PORT)
        # An empty string and None both mean "no API key"; normalise to None so the
        # apikey param is simply omitted rather than sent blank.
        self._api_key = api_key if api_key is not None else settings.DAST_ZAP_API_KEY
        #: Hard ceiling for a whole scan *phase* (passive/active), used as the wait
        #: deadline in the polling helpers.
        self._phase_timeout = int(
            timeout if timeout is not None else settings.DAST_ZAP_TIMEOUT
        )
        #: Generous per-call ceiling for the (synchronous, endpoint-fetching)
        #: seeding import, kept separate from the short default REST timeout.
        self._import_timeout = int(
            import_timeout if import_timeout is not None else settings.DAST_ZAP_IMPORT_TIMEOUT
        )
        self._base_url = f"http://{self._host}:{self._port}"
        # A persistent client keeps the connection to the warm daemon alive across
        # the many small REST calls one scan makes. Injectable for tests.
        self._client = client or httpx.Client(base_url=self._base_url, timeout=_REST_TIMEOUT)
        self._owns_client = client is None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ZapClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Low-level REST plumbing — the ONLY place that touches httpx
    # ------------------------------------------------------------------ #
    def _call(
        self,
        component: str,
        kind: str,
        action: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Issue one ZAP REST call and return its decoded JSON object.

        ``kind`` is ``"view"`` (read) or ``"action"`` (mutating REST operation).
        ``timeout`` overrides the client's default per-call timeout for calls that
        legitimately run long (the seeding import, which fetches every endpoint).
        Every failure mode — connection refused, timeout, non-2xx status, undecodable
        body, or a ZAP-reported error object — is wrapped as :class:`ScannerError`.
        """
        path = f"/JSON/{component}/{kind}/{action}/"
        query: dict[str, Any] = {}
        if self._api_key:
            # ZAP accepts the key as a query param on every call; it also honours an
            # X-ZAP-API-Key header, but the param keeps this uniform and simple.
            query["apikey"] = self._api_key
        if params:
            # Drop None values so optional params are simply omitted, and coerce the
            # rest to str (ZAP treats everything as strings on the wire).
            query.update({k: str(v) for k, v in params.items() if v is not None})

        # Only override the client's configured timeout when a caller asks for it,
        # so ordinary fast calls keep the short default.
        get_kwargs: dict[str, Any] = {"params": query}
        if timeout is not None:
            get_kwargs["timeout"] = timeout
        try:
            response = self._client.get(path, **get_kwargs)
        except httpx.HTTPError as exc:
            raise ScannerError(
                SCANNER_NAME,
                f"ZAP REST call {component}/{action} failed to reach the sidecar "
                f"at {self._base_url}: {exc}",
            ) from exc

        if response.status_code != 200:
            # ZAP signals API errors with a non-200 and a JSON body carrying a code
            # and message; surface that reason verbatim when present.
            detail = _error_detail(response)
            raise ScannerError(
                SCANNER_NAME,
                f"ZAP REST call {component}/{action} returned HTTP "
                f"{response.status_code}{f': {detail}' if detail else ''}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ScannerError(
                SCANNER_NAME,
                f"ZAP REST call {component}/{action} returned an undecodable body",
            ) from exc
        if not isinstance(payload, dict):
            raise ScannerError(
                SCANNER_NAME,
                f"ZAP REST call {component}/{action} returned an unexpected payload "
                f"of type {type(payload).__name__}",
            )
        return payload

    def _view(
        self, component: str, action: str, *, _timeout: float | None = None, **params: Any
    ) -> dict[str, Any]:
        return self._call(component, "view", action, params, timeout=_timeout)

    def _action(
        self, component: str, action: str, *, _timeout: float | None = None, **params: Any
    ) -> dict[str, Any]:
        return self._call(component, "action", action, params, timeout=_timeout)

    # ------------------------------------------------------------------ #
    # Reachability (Req 1.1, 1.3, 13.1)
    # ------------------------------------------------------------------ #
    def reachable(self) -> bool:
        """Return ``True`` when the sidecar answers a ``core.version`` ping.

        Called first in every scan. Raises :class:`ScannerError` when the daemon
        cannot be reached so the adapter aborts *before* issuing scan commands
        (Req 1.3) and the runner records an ``incomplete`` entry (Req 13.1).
        """
        payload = self._view("core", "version")
        version = payload.get("version")
        if not version:
            raise ScannerError(
                SCANNER_NAME, "ZAP sidecar responded without a version — not a ZAP daemon?"
            )
        logger.info("ZAP sidecar reachable at %s (version %s)", self._base_url, version)
        return True

    # ------------------------------------------------------------------ #
    # Fresh session (Req 2.1, 2.2)
    # ------------------------------------------------------------------ #
    def new_session(self, name: str) -> None:
        """Start a fresh, empty ZAP session, discarding all prior state.

        A new session has an empty site tree and no alerts, so last week's findings
        cannot bleed into this scan (Req 2.1, 2.2). ``overwrite=true`` makes a
        re-used session name idempotent. Raises :class:`ScannerError` on failure so
        the runner records ``incomplete`` (Req 2.3).
        """
        self._action("core", "newSession", name=name, overwrite="true")
        logger.info("ZAP started fresh session '%s'", name)

    # ------------------------------------------------------------------ #
    # Exclusions (Req 4.1, 4.2)
    # ------------------------------------------------------------------ #
    def exclude_from_scan(self, pattern: str) -> None:
        """Exclude every URL matching ``pattern`` from all ZAP traffic.

        Registered on the proxy, the spider, and the active scanner so the logout
        URL is untouched by seeding, passive, and active phases alike (Req 4.1) —
        the scanner cannot log itself out mid-scan.
        """
        # Each component excludes independently; register on all three so no phase
        # can send a request the others were told to avoid.
        self._action("core", "excludeFromProxy", regex=pattern)
        self._action("spider", "excludeFromScan", regex=pattern)
        self._action("ascan", "excludeFromScan", regex=pattern)
        logger.info("ZAP excluded pattern from all scanning: %s", pattern)

    # ------------------------------------------------------------------ #
    # Auth injection (Req 3.1, 3.3, 5.4)
    # ------------------------------------------------------------------ #
    def set_replacer_rule(
        self, header_value: str, *, header_name: str = "Authorization"
    ) -> None:
        """Add a replacer rule stamping ``header_name: header_value`` on every request.

        A single ``REQ_HEADER`` replacer rule applies uniformly to seeding, passive,
        and active traffic, so the whole authenticated surface is covered rather
        than only the login page (Req 3.1, 3.3, 5.4). Callers skip this entirely
        when scanning anonymously (Req 3.2).
        """
        self._action(
            "replacer",
            "addRule",
            description=f"dast-auth-{header_name.lower()}",
            enabled="true",
            matchType=_MATCH_TYPE_REQ_HEADER,
            matchRegex="false",
            matchString=header_name,
            replacement=header_value,
            # Empty initiators = apply to requests from every ZAP component.
            initiators="",
        )
        logger.info("ZAP replacer rule set: injecting %s on every request", header_name)

    # ------------------------------------------------------------------ #
    # Rate limiting (Req 12.1, 12.2)
    # ------------------------------------------------------------------ #
    def set_rate_limit(self, requests_per_second: int) -> None:
        """Cap ZAP's outgoing request rate to ``requests_per_second``.

        Our staging target is typically a single worker; firing ZAP at full speed
        jams the door and the scan looks clean because requests never landed. A
        global rate-limit rule (matching every host) applies uniformly to seeding,
        passive, and active traffic — the whole scan policy, not one phase.

        A non-positive value means "no cap"; the rule is simply not registered.
        """
        if not requests_per_second or requests_per_second <= 0:
            return
        try:
            self._action(
                "network",
                "addRateLimitRule",
                description="dast-rate-limit",
                enabled="true",
                matchRegex="true",
                matchString=".*",
                requestsPerSecond=requests_per_second,
                groupBy="rule",
            )
        except ScannerError as exc:
            # Rate-limit rules live in ZAP's *global* network config, not the
            # per-scan session, so a rule added by an earlier phase (the passive
            # adapter) or an earlier scan is still present when the next adapter
            # runs. ZAP then rejects the duplicate with "already_exists". That is
            # not a failure: our rule — same description, same rate — is already in
            # force, which is exactly the cap we wanted. Any other error still
            # surfaces as an incomplete scan.
            if "already_exists" in str(exc).lower() or "already exists" in str(exc).lower():
                logger.info(
                    "ZAP rate limit rule already present (%d req/s); reusing it",
                    requests_per_second,
                )
                return
            raise
        logger.info("ZAP rate limit set to %d request(s)/sec", requests_per_second)

    # ------------------------------------------------------------------ #
    # Seeding the site tree (Req 5.1, 5.4)
    # ------------------------------------------------------------------ #
    def import_openapi(self, spec_url: str, *, target_url: str | None = None) -> None:
        """Seed the site tree by importing an OpenAPI spec by URL.

        Importing by URL (rather than uploading a file) means the import request
        itself flows through ZAP and therefore carries the auth replacer rule
        (Req 5.4). ``target_url`` overrides the host the spec's paths are resolved
        against when the spec is served from a different origin than the target.
        """
        self._action(
            "openapi",
            "importUrl",
            _timeout=self._import_timeout,
            url=spec_url,
            hostOverride=target_url,
        )
        logger.info("ZAP imported OpenAPI spec from %s", spec_url)

    def spider(self, target_url: str, *, timeout: int | None = None) -> None:
        """Seed the site tree by spidering ``target_url`` (fallback when no spec).

        Blocks (by polling ``spider.status``) until the crawl reaches 100% or the
        phase timeout is hit, so callers can treat seeding as complete on return.
        """
        payload = self._action(
            "spider", "scan", _timeout=self._import_timeout, url=target_url
        )
        scan_id = payload.get("scan")
        self._poll(
            lambda: self._int(self._view("spider", "status", scanId=scan_id), "status"),
            target=100,
            timeout=timeout,
            what="spider",
        )
        logger.info("ZAP spider completed for %s", target_url)

    def urls(self, base_url: str | None = None) -> list[str]:
        """Return the URLs currently on ZAP's site tree.

        Lets the adapter measure how many endpoints seeding actually placed on the
        map (Req 5.2) and compute under-seeding against the spec count (Req 10.1).
        """
        payload = self._view("core", "urls", baseurl=base_url)
        found = payload.get("urls")
        return [str(u) for u in found] if isinstance(found, list) else []

    # ------------------------------------------------------------------ #
    # Passive scan (Req 6.1)
    # ------------------------------------------------------------------ #
    def passive_scan_wait(self, *, timeout: int | None = None) -> None:
        """Block until ZAP's passive scan queue has fully drained.

        Passive scanning inspects traffic already on the map and sends no attack
        payloads; the work is done when ``pscan.recordsToScan`` reaches 0.
        """
        self._poll(
            lambda: self._int(self._view("pscan", "recordsToScan"), "recordsToScan"),
            target=0,
            timeout=timeout,
            what="passive scan",
            descending=True,
        )
        logger.info("ZAP passive scan queue drained")

    # ------------------------------------------------------------------ #
    # Active scan (Req 6.3)
    # ------------------------------------------------------------------ #
    def set_active_scan_options(
        self,
        *,
        thread_per_host: int | None = None,
        host_per_scan: int | None = None,
        delay_ms: int | None = None,
    ) -> None:
        """Throttle the active scanner's concurrency and request rate.

        ``thread_per_host`` is the main lever: it caps how many attack requests are
        in flight against one host at once (set 1 for effectively serial scanning).
        ``host_per_scan`` bounds parallel hosts (1 for a single target). ``delay_ms``
        spaces out consecutive requests so a single-worker target is not saturated.

        Only the options the caller specifies are set; the rest keep ZAP's defaults.
        """
        if thread_per_host is not None:
            self._action("ascan", "setOptionThreadPerHost", Integer=thread_per_host)
        if host_per_scan is not None:
            self._action("ascan", "setOptionHostPerScan", Integer=host_per_scan)
        if delay_ms is not None:
            self._action("ascan", "setOptionDelayInMs", Integer=delay_ms)
        logger.info(
            "ZAP active scan throttle set: thread_per_host=%s host_per_scan=%s delay_ms=%s",
            thread_per_host,
            host_per_scan,
            delay_ms,
        )

    def active_scan(
        self,
        target_url: str,
        *,
        timeout: int | None = None,
        recurse: bool = True,
        tolerate_timeouts: int = 0,
    ) -> None:
        """Run an active scan against ``target_url`` and block until it finishes.

        Active scanning sends real attack payloads to every mapped endpoint; the
        caller is responsible for only invoking this against a non-production target
        under the deep profile (policy lives in the adapter, not here).

        ``recurse=False`` scans only ``target_url`` itself (not its descendants),
        which lets a caller queue endpoints one at a time to bound peak load.
        ``tolerate_timeouts`` allows that many *consecutive* transient status-poll
        failures before giving up: under heavy active-scan load ZAP's own REST API
        can briefly stall, and a single blip should not abort a scan that is in fact
        still running.
        """
        payload = self._action(
            "ascan", "scan", url=target_url, recurse="true" if recurse else "false"
        )
        scan_id = payload.get("scan")
        self._poll(
            lambda: self._int(self._view("ascan", "status", scanId=scan_id), "status"),
            target=100,
            timeout=timeout,
            what="active scan",
            tolerate_errors=tolerate_timeouts,
        )
        logger.info("ZAP active scan completed for %s", target_url)

    # ------------------------------------------------------------------ #
    # Alerts (Req 8.1)
    # ------------------------------------------------------------------ #
    def alerts(self, *, base_url: str | None = None, page_size: int = 500) -> list[dict[str, Any]]:
        """Return every alert ZAP has recorded, paging through ``core.alerts``.

        ZAP returns alerts in pages; this walks them all so no finding is dropped
        for a target that produced more alerts than one page holds.
        """
        collected: list[dict[str, Any]] = []
        start = 0
        while True:
            payload = self._view(
                "core", "alerts", baseurl=base_url, start=start, count=page_size
            )
            page = payload.get("alerts")
            if not isinstance(page, list) or not page:
                break
            collected.extend(a for a in page if isinstance(a, dict))
            if len(page) < page_size:
                break
            start += page_size
        return collected

    # ------------------------------------------------------------------ #
    # Request evidence — read from ZAP's OWN counters, never inferred (Req 9.3)
    # ------------------------------------------------------------------ #
    def requests_made(self, *, base_url: str | None = None) -> int:
        """Count the requests ZAP actually sent to the target (``core.numberOfMessages``).

        This is the liveness signal: a scan reporting zero findings *and* zero
        requests never reached the target and must not read as clean (Req 9.3, 9.4).
        """
        return self._int(
            self._view("core", "numberOfMessages", baseurl=base_url), "numberOfMessages"
        )

    def request_errors(self) -> int:
        """Count outgoing requests that failed (connection/IO errors), from ZAP stats."""
        return self._sum_stats(("network.socket.error", "network.io.error", ".error."))

    def timeouts(self) -> int:
        """Count outgoing requests that timed out, from ZAP stats."""
        return self._sum_stats(("network.socket.timeout", ".timeout."))

    def _stats(self) -> dict[str, Any]:
        """Fetch ZAP's aggregate site statistics as a flat ``{key: count}`` map."""
        payload = self._view("stats", "allSitesStats", keyPrefix="")
        stats = payload.get("statistics") or payload.get("allSitesStats")
        # ZAP has returned this as either a dict or a list of single-key dicts across
        # versions; normalise both shapes to one flat mapping.
        flat: dict[str, Any] = {}
        if isinstance(stats, dict):
            flat.update(stats)
        elif isinstance(stats, list):
            for entry in stats:
                if isinstance(entry, dict):
                    flat.update(entry)
        return flat

    def _sum_stats(self, needles: Sequence[str]) -> int:
        """Sum every stat whose key contains any of ``needles`` (case-insensitive).

        The exact ZAP stat key names vary by version, so matching on substrings
        keeps the evidence readable across upgrades rather than pinned to one build.
        """
        total = 0
        for key, value in self._stats().items():
            lowered = str(key).lower()
            if any(n in lowered for n in needles):
                try:
                    total += int(value)
                except (TypeError, ValueError):
                    continue
        return total

    # ------------------------------------------------------------------ #
    # Canary detection (Req 7.1, 7.2)
    # ------------------------------------------------------------------ #
    def canary_detected(self, canary_path: str) -> bool:
        """Return ``True`` when ZAP has raised an alert for the canary path.

        The canary is a deliberately vulnerable route we control; ZAP raising an
        alert against it proves the scanner's own detection is working. The adapter
        checks this at both scan boundaries (Req 7.1, 7.2) to keep a false "clean"
        impossible.
        """
        if not canary_path:
            return False
        needle = canary_path.rstrip("/") or canary_path
        for alert in self.alerts():
            url = str(alert.get("url") or "")
            if needle in url:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Polling helper
    # ------------------------------------------------------------------ #
    def _poll(
        self,
        read: Any,
        *,
        target: int,
        what: str,
        timeout: int | None = None,
        descending: bool = False,
        poll_interval: float = _DEFAULT_POLL_INTERVAL,
        tolerate_errors: int = 0,
    ) -> None:
        """Poll ``read()`` until it reaches ``target`` or the deadline is hit.

        ``descending=False`` waits for progress to climb *to* ``target`` (e.g. a
        spider/active-scan percentage reaching 100); ``descending=True`` waits for a
        queue length to fall *to* ``target`` (e.g. passive records reaching 0).
        Exceeding the phase timeout is wrapped as :class:`ScannerError` so a stuck
        phase degrades to ``incomplete`` rather than hanging the scan.

        ``tolerate_errors`` permits that many *consecutive* ``read()`` failures
        (e.g. a transient REST timeout while ZAP is saturated) before the failure is
        propagated. Any successful read resets the counter, so only a sustained
        outage — not a momentary stall — aborts the poll.
        """
        deadline = time.monotonic() + (timeout if timeout is not None else self._phase_timeout)
        consecutive_errors = 0
        while time.monotonic() < deadline:
            try:
                current = read()
            except ScannerError:
                if consecutive_errors >= tolerate_errors:
                    raise
                consecutive_errors += 1
                logger.warning(
                    "%s: transient poll failure %d/%d — retrying",
                    what,
                    consecutive_errors,
                    tolerate_errors,
                )
                time.sleep(poll_interval)
                continue
            consecutive_errors = 0
            done = current <= target if descending else current >= target
            if done:
                return
            time.sleep(poll_interval)
        raise ScannerError(
            SCANNER_NAME,
            f"{what} did not finish within the configured timeout",
        )

    # ------------------------------------------------------------------ #
    # Small parsing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _int(payload: Mapping[str, Any], key: str) -> int:
        """Read an integer field from a ZAP view payload (values arrive as strings)."""
        try:
            return int(payload.get(key))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ScannerError(
                SCANNER_NAME,
                f"ZAP returned a non-integer '{key}': {payload.get(key)!r}",
            ) from exc


def _error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of ZAP's error message from a non-200 response."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:200]
    if isinstance(body, dict):
        message = body.get("message") or body.get("detail")
        code = body.get("code")
        if message and code:
            return f"{code}: {message}"
        if message:
            return str(message)
    return str(body)[:200]
