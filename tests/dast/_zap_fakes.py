"""In-memory fake ZAP client for property/unit tests.

The real :class:`dast.adapters.zap_client.ZapClient` is the *only* thing that talks
``httpx`` to a live ZAP daemon. Everything above it — the adapter's orchestration and
the trust invariants derived from it (auth-on-every-request, logout exclusion, fresh
session, seeding count, canary boundaries, request evidence) — is pure logic that must
hold over arbitrary inputs. To check those invariants with Hypothesis and no network,
the design (`Testing Strategy → Fakes over network`) calls for an **in-memory fake
ZAP** substituted for the client.

:class:`FakeZapClient` mirrors the *exact* public surface of the real ``ZapClient`` so
an adapter constructed with ``client=FakeZapClient(...)`` behaves identically minus the
wire. On top of that surface it exposes two things the real client cannot: **inspectable
recorded state** (every request it would have sent, with headers; the site tree; the
session generation) and **configurable responses** (reachability, seedable endpoints,
canary detection at each boundary, alerts, and the request-evidence counters).

What it faithfully models, and why each matters to a property:

- **Session generation (Property 7).** :meth:`new_session` bumps a generation counter
  and clears *all prior alerts, seeded endpoints, and recorded requests*, so a fresh
  session provably carries no prior state.
- **Outgoing requests with headers (Properties 5, 6).** Every request the fake would
  send is recorded as a :class:`SentRequest` capturing the URL and a snapshot of the
  currently-injected headers (including the replacer's ``Authorization`` value), so a
  test can assert auth is present on every request and that no excluded (logout) URL was
  ever sent.
- **Exclusions (Property 6).** A URL matching any configured exclusion pattern is never
  recorded and never placed on the site tree — the scanner cannot contact it.
- **Seeding (Properties 8, 9).** :meth:`import_openapi` / :meth:`spider` place the
  test-configured endpoints on the site tree (minus exclusions), so a test can assert
  the seeded count and drive under-seeding by configuring fewer endpoints than the spec.
- **Canary detection (Property 10).** :meth:`canary_detected` returns the configured
  start value on its first call and the configured end value thereafter, matching the
  adapter's start/end boundary checks.
- **Request evidence (Properties 11, 13).** :meth:`requests_made`, :meth:`request_errors`
  and :meth:`timeouts` return configurable counters so the runner's activity → coverage
  trust rules can be exercised across arbitrary evidence combinations.

This module is test infrastructure only; it is never imported by production code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.security.detection.adapters.base import ScannerError

#: Scanner name used on any :class:`ScannerError` this fake raises, matching the real
#: client so error-path assertions read identically.
SCANNER_NAME = "zap"


@dataclass(frozen=True)
class SentRequest:
    """One outgoing request the fake would have caused ZAP to send.

    ``headers`` is a snapshot taken *at send time*, so it reflects whatever replacer
    rule was in force when the request was recorded — this is what lets a test assert
    the injected ``Authorization`` value rode along on every request.
    """

    url: str
    headers: dict[str, str] = field(default_factory=dict)
    #: The scan phase that produced the request: ``"seed"`` | ``"active"``. Useful for
    #: tests that want to distinguish seeding traffic from active-scan traffic.
    phase: str = "seed"


class FakeZapClient:
    """A drop-in, in-memory stand-in for :class:`dast.adapters.zap_client.ZapClient`.

    Construct it with the responses a test wants (reachability, the endpoints seeding
    will discover, canary detection at each boundary, alerts, evidence counters), pass
    it to a :class:`ZapAdapter` as ``client=...``, then inspect the recorded state
    (:attr:`sent_requests`, :attr:`site_tree`, :attr:`session_generation`) afterwards.
    """

    def __init__(
        self,
        *,
        reachable: bool = True,
        seedable_endpoints: list[str] | None = None,
        alerts: list[dict[str, Any]] | None = None,
        canary_at_start: bool = True,
        canary_at_end: bool = True,
        requests_made: int | None = None,
        request_errors: int = 0,
        timeouts: int = 0,
    ) -> None:
        # ---- configurable responses (set by the test) ------------------------ #
        #: When False, :meth:`reachable` raises like an unreachable sidecar.
        self.reachable_ok = reachable
        #: Full URLs a seeding call (import/spider) will place on the site tree.
        self.seedable_endpoints: list[str] = list(seedable_endpoints or [])
        #: Alert objects :meth:`alerts` returns (ZAP ``core.alerts`` shape).
        self.configured_alerts: list[dict[str, Any]] = list(alerts or [])
        #: Canary detection outcome on the first (start) and later (end) checks.
        self.canary_at_start = canary_at_start
        self.canary_at_end = canary_at_end
        #: Override for :meth:`requests_made`; when ``None`` the count of recorded
        #: requests is returned instead, tying evidence to real recorded traffic.
        self.requests_made_override = requests_made
        #: Values returned by the error/timeout evidence counters.
        self.request_errors_count = request_errors
        self.timeouts_count = timeouts

        # ---- recorded state (mutable; reset by new_session) ------------------ #
        #: Bumped on every :meth:`new_session`; a proxy for ZAP's session identity.
        self.session_generation = 0
        #: Name of the current session, or ``None`` before the first session.
        self.session_name: str | None = None
        #: Every request the fake would have sent, in order.
        self.sent_requests: list[SentRequest] = []
        #: URLs currently on the fake's site tree (seeded endpoints, deduped).
        self.site_tree: list[str] = []

        # ---- persistent config not tied to a single session ------------------ #
        #: Exclusion regexes registered via :meth:`exclude_from_scan`.
        self.exclusions: list[str] = []
        #: Headers a replacer rule injects onto every request, ``{name: value}``.
        self.replacer_headers: dict[str, str] = {}
        #: Last outgoing rate cap the adapter requested via :meth:`set_rate_limit`.
        self.rate_limit: int | None = None
        #: Last active-scan throttle options requested, or ``None`` if never set.
        self.active_scan_options: dict[str, int | None] | None = None

        # ---- internal counters ----------------------------------------------- #
        self._canary_calls = 0
        #: Every session name ever started, for tests asserting fresh-session usage.
        self.session_names: list[str] = []

    # ------------------------------------------------------------------ #
    # Test helpers (not part of the ZapClient interface)
    # ------------------------------------------------------------------ #
    def preload_prior_session(
        self,
        *,
        alerts: list[dict[str, Any]] | None = None,
        urls: list[str] | None = None,
        requests: list[SentRequest] | None = None,
    ) -> None:
        """Seed *prior* session state, to be cleared by the next :meth:`new_session`.

        Used by the fresh-session property (Property 7): fill the fake with arbitrary
        prior alerts / site-tree entries / recorded requests, start a new session, then
        assert everything is empty again.
        """
        if alerts is not None:
            self.configured_alerts = list(alerts)
        if urls is not None:
            self.site_tree = list(urls)
        if requests is not None:
            self.sent_requests = list(requests)

    def _excluded(self, url: str) -> bool:
        """True when ``url`` matches any registered exclusion pattern."""
        return any(re.search(pattern, url) for pattern in self.exclusions)

    def _record_request(self, url: str, *, phase: str) -> None:
        """Record one outgoing request unless it is excluded.

        The header snapshot is taken here so it reflects the replacer rule in force at
        send time — the mechanism behind the auth-on-every-request property.
        """
        if self._excluded(url):
            return
        self.sent_requests.append(
            SentRequest(url=url, headers=dict(self.replacer_headers), phase=phase)
        )

    def _seed(self) -> None:
        """Place the configured endpoints on the site tree and record the traffic.

        Excluded URLs are skipped entirely (never contacted, never mapped). Endpoints
        already on the tree are not duplicated, but each contact is still recorded.
        """
        for url in self.seedable_endpoints:
            if self._excluded(url):
                continue
            self._record_request(url, phase="seed")
            if url not in self.site_tree:
                self.site_tree.append(url)

    # ------------------------------------------------------------------ #
    # Lifecycle (context-manager parity with the real client)
    # ------------------------------------------------------------------ #
    def close(self) -> None:  # pragma: no cover - trivial no-op
        return None

    def __enter__(self) -> "FakeZapClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Reachability
    # ------------------------------------------------------------------ #
    def reachable(self) -> bool:
        """Return ``True`` when configured reachable, else raise like the real client."""
        if not self.reachable_ok:
            raise ScannerError(SCANNER_NAME, "fake ZAP sidecar is unreachable")
        return True

    # ------------------------------------------------------------------ #
    # Fresh session — clears ALL prior alerts, endpoints, and requests
    # ------------------------------------------------------------------ #
    def new_session(self, name: str) -> None:
        """Start a fresh session, discarding every scrap of prior state (Property 7)."""
        self.session_generation += 1
        self.session_name = name
        self.session_names.append(name)
        # The three things a fresh ZAP session provably lacks:
        self.configured_alerts = []
        self.site_tree = []
        self.sent_requests = []
        # Canary checks are per-scan; reset so start/end sequencing restarts.
        self._canary_calls = 0

    # ------------------------------------------------------------------ #
    # Exclusions
    # ------------------------------------------------------------------ #
    def exclude_from_scan(self, pattern: str) -> None:
        """Register ``pattern`` so matching URLs are never contacted (Property 6)."""
        self.exclusions.append(pattern)

    # ------------------------------------------------------------------ #
    # Auth injection
    # ------------------------------------------------------------------ #
    def set_replacer_rule(
        self, header_value: str, *, header_name: str = "Authorization"
    ) -> None:
        """Inject ``header_name: header_value`` on every subsequent request (Property 5)."""
        self.replacer_headers[header_name] = header_value

    # ------------------------------------------------------------------ #
    # Scan-policy knobs — recorded so tests can assert they were applied
    # ------------------------------------------------------------------ #
    def set_rate_limit(self, requests_per_second: int) -> None:
        """Record the outgoing rate cap the adapter asked for (Property 12/req 12.2).

        The real client registers a global rate-limit rule; the fake sends no real
        traffic, so it just records the value the adapter requested for inspection.
        """
        self.rate_limit = requests_per_second

    def set_active_scan_options(
        self,
        *,
        thread_per_host: int | None = None,
        host_per_scan: int | None = None,
        delay_ms: int | None = None,
    ) -> None:
        """Record active-scan throttle options the adapter requested (no-op otherwise)."""
        self.active_scan_options = {
            "thread_per_host": thread_per_host,
            "host_per_scan": host_per_scan,
            "delay_ms": delay_ms,
        }

    # ------------------------------------------------------------------ #
    # Seeding the site tree
    # ------------------------------------------------------------------ #
    def import_openapi(self, spec_url: str, *, target_url: str | None = None) -> None:
        """Seed from an OpenAPI spec: the import fetch plus every declared endpoint.

        The spec fetch itself flows through ZAP and so carries the auth header, exactly
        like the real import-by-URL; then each configured endpoint is contacted/seeded.
        """
        self._record_request(spec_url, phase="seed")
        self._seed()

    def spider(self, target_url: str, *, timeout: int | None = None) -> None:
        """Seed by crawling: contact the root, then every configured endpoint."""
        self._record_request(target_url, phase="seed")
        self._seed()

    def urls(self, base_url: str | None = None) -> list[str]:
        """Return the site tree, optionally filtered to URLs under ``base_url``."""
        if base_url:
            return [u for u in self.site_tree if base_url in u]
        return list(self.site_tree)

    # ------------------------------------------------------------------ #
    # Passive scan — inspects existing traffic, sends nothing new
    # ------------------------------------------------------------------ #
    def passive_scan_wait(self, *, timeout: int | None = None) -> None:
        """No-op: passive scanning inspects mapped traffic and issues no new requests."""
        return None

    # ------------------------------------------------------------------ #
    # Active scan — attacks every mapped endpoint
    # ------------------------------------------------------------------ #
    def active_scan(self, target_url: str, *, timeout: int | None = None) -> None:
        """Attack every mapped endpoint, recording one request per site-tree entry.

        Active traffic must also carry the injected auth header (Property 5), so each
        contact is recorded through the same header-snapshot path as seeding.
        """
        for url in list(self.site_tree):
            self._record_request(url, phase="active")

    # ------------------------------------------------------------------ #
    # Alerts
    # ------------------------------------------------------------------ #
    def alerts(
        self, *, base_url: str | None = None, page_size: int = 500
    ) -> list[dict[str, Any]]:
        """Return the configured alerts, optionally filtered to ``base_url``."""
        if base_url:
            return [
                a for a in self.configured_alerts if base_url in str(a.get("url", ""))
            ]
        return list(self.configured_alerts)

    # ------------------------------------------------------------------ #
    # Request evidence — configurable counters (Properties 11, 13)
    # ------------------------------------------------------------------ #
    def requests_made(self, *, base_url: str | None = None) -> int:
        """Requests ZAP sent: the override when set, else the recorded request count."""
        if self.requests_made_override is not None:
            return self.requests_made_override
        return len(self.sent_requests)

    def request_errors(self) -> int:
        """Configured count of outgoing requests that failed outright."""
        return self.request_errors_count

    def timeouts(self) -> int:
        """Configured count of outgoing requests that timed out."""
        return self.timeouts_count

    # ------------------------------------------------------------------ #
    # Canary detection — start value first, end value thereafter
    # ------------------------------------------------------------------ #
    def canary_detected(self, canary_path: str) -> bool:
        """Return the start outcome on the first call, the end outcome after (Prop 10)."""
        if not canary_path:
            return False
        self._canary_calls += 1
        return self.canary_at_start if self._canary_calls == 1 else self.canary_at_end
