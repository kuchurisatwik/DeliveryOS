# Feature: dast-schemathesis, Task 8.1: live integration test
"""Live integration test: real Schemathesis CLI + real ZAP sidecar + a buggy API.

Where the property tests fake out the CLI/network at the ``_run`` seam and the
runner-trust tests classify synthetic activity, this test exercises the one thing
those cannot: the *real* boundary. It drives the pinned Schemathesis CLI as a
subprocess, routes every generated request through a real ZAP sidecar acting as an
HTTP proxy, and points both at a deliberately buggy API target, then asserts the
dual payoff Phase 4 exists to deliver:

* **ZAP site-tree seeding** — after one proxied Schemathesis run, ZAP's site tree is
  populated with the target's authenticated endpoints, so a *later* active ZAP scan
  has a real, authenticated map to attack instead of guessing ``id=1`` into 404s
  (Req 3.1, 3.3, 10.4);
* **undeclared 5xx → high-severity finding** — an endpoint that 500s on malformed
  input yields a ``HIGH`` finding carrying a reissuable reproducing request, which we
  actually reissue and confirm reproduces the failure (Req 5.1, and the reproducing
  request of Req 8);
* **schema violation → finding** — a response whose body does not conform to its
  declared OpenAPI contract yields a schema-violation finding (Req 7.1);
* **honest coverage** — a completed run produces a ``schemathesis`` coverage entry
  marked ``complete`` with a non-zero ``requests_made`` read from Schemathesis's OWN
  run statistics, never the generated-case count (Req 11.1).

Gating — this suite has heavy external dependencies (a pinned ``schemathesis``
binary, a running ZAP daemon, ``fastapi``/``uvicorn``/``httpx`` to host the buggy
target) and MUST NOT fail a normal CI/dev run where that stack is absent. It is
therefore gated on three levels, mirroring the repo's live-harness convention
(``scripts/live_zap_juiceshop.py`` + ``docker-compose.juiceshop.yml``):

1. **Opt-in** — the whole module is skipped unless ``DAST_IT_SCHEMATHESIS`` is set to
   a truthy value. Nothing here runs by accident.
2. **Tool presence** — skipped when the ``schemathesis`` binary is not on ``PATH`` or
   ``fastapi``/``uvicorn``/``httpx`` cannot be imported (checked in the fixture).
3. **Stack reachability** — skipped when the ZAP proxy or the buggy target cannot be
   reached at scan time.

Bringing the stack up locally (ZAP on ``127.0.0.1:8090``, as in the Juice Shop
harness), then::

    docker compose -f docker-compose.juiceshop.yml up -d zap   # a keyless ZAP daemon
    pip install "schemathesis==3.39.5"                          # the pinned CLI
    set DAST_IT_SCHEMATHESIS=1                                  # opt in (Windows: set)
    pytest tests/dast/test_schemathesis_integration.py -v

The buggy target is spun up in-process by default (a tiny FastAPI app with a route
that divides by a client-controlled denominator and a route that returns a body
violating its declared schema). Override it with an already-running target via
``DAST_IT_TARGET_URL`` when ZAP cannot reach a host-side process (the base URL must
be reachable *from the ZAP daemon*, e.g. ``http://host.docker.internal:8099`` under
Docker Desktop).

**Validates: Requirements 3.1, 3.3, 5.1, 7.1, 10.4, 11.1**
"""

from __future__ import annotations

import os
import shutil
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

import pytest

from app.security.models import Severity
from dast.config import DastSettings
from dast.models import DastScope, DastResult
from dast.runner import run_scan

# --------------------------------------------------------------------------- #
# Gating helpers
# --------------------------------------------------------------------------- #
#: Opt-in environment flag. Truthy → the live stack is expected to be present.
_OPT_IN_ENV = "DAST_IT_SCHEMATHESIS"
#: Optional override: an already-running buggy target reachable from the ZAP daemon.
_TARGET_URL_ENV = "DAST_IT_TARGET_URL"
#: Host/port the in-process buggy app binds to when no external target is given.
_TARGET_HOST_ENV = "DAST_IT_TARGET_HOST"   # the host in the base URL ZAP/schemathesis use
_TARGET_PORT_ENV = "DAST_IT_TARGET_PORT"
_TARGET_BIND_ENV = "DAST_IT_TARGET_BIND"   # the interface uvicorn binds on

_TRUTHY = {"1", "true", "yes", "on"}


def _opt_in() -> bool:
    """True when the operator has explicitly enabled the live integration stack."""
    return os.environ.get(_OPT_IN_ENV, "").strip().lower() in _TRUTHY


# The whole module is skipped in a normal run: no opt-in, no live scan. Collection
# still succeeds — the module imports cleanly and every test is simply skipped.
pytestmark = pytest.mark.skipif(
    not _opt_in(),
    reason=(
        f"live Schemathesis+ZAP integration stack not enabled; set {_OPT_IN_ENV}=1 "
        "with a pinned 'schemathesis' on PATH and a reachable ZAP daemon to run it"
    ),
)


def _tcp_open(host: str, port: int, timeout: float = 3.0) -> bool:
    """Return True when a TCP connection to ``host:port`` can be established."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    """Return True when ``url`` answers any HTTP status (the target is up)."""
    try:
        import httpx
    except Exception:  # pragma: no cover - covered by importorskip in the fixture
        return False
    try:
        httpx.get(url, timeout=timeout)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# The buggy API target (in-process FastAPI app)
# --------------------------------------------------------------------------- #
def _build_buggy_app() -> Any:
    """A tiny, deliberately buggy API whose OpenAPI spec drives Schemathesis.

    Two planted defects give Schemathesis something real to catch:

    * ``POST /divide`` divides by a client-supplied denominator with no guard, so a
      generated ``denominator=0`` raises and the framework answers ``500`` — a 5xx
      the schema never declares (only 200/422 are), i.e. an *undeclared* server error
      (Req 5.1).
    * ``GET /widgets/{widget_id}`` declares a ``Widget`` response (``id`` and ``name``
      both required) but returns a body missing ``name``, so the response violates its
      own declared contract (Req 7.1).

    ``GET /health`` gives preflight/target-reachability something to poll, and FastAPI
    serves the schema at ``/openapi.json`` (the ``DAST_OPENAPI_PATH`` default).
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    app = FastAPI(title="dast-schemathesis buggy target", version="1.0.0")

    class Widget(BaseModel):
        id: int
        name: str

    class DivideRequest(BaseModel):
        numerator: int
        denominator: int

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"commit_sha": "integration-test"}

    @app.post("/divide")
    def divide(req: DivideRequest) -> dict[str, float]:
        # BUG: no zero-denominator guard. A generated denominator=0 raises
        # ZeroDivisionError → an undeclared 500 (the schema declares only 200/422).
        return {"result": req.numerator / req.denominator}

    @app.get("/widgets/{widget_id}", response_model=Widget)
    def get_widget(widget_id: int) -> Any:
        # BUG: the declared Widget requires `name`, but the actual body omits it.
        # Returning a raw JSONResponse bypasses FastAPI's response-model coercion so
        # the non-conforming body reaches the wire (a real schema violation).
        return JSONResponse({"id": widget_id})

    return app


class _BackgroundServer:
    """Run a uvicorn server for the buggy app on a daemon thread, start/stop cleanly."""

    def __init__(self, app: Any, *, bind_host: str, port: int) -> None:
        import uvicorn

        self._config = uvicorn.Config(
            app, host=bind_host, port=port, log_level="warning"
        )
        self._server = uvicorn.Server(self._config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self, *, timeout: float = 30.0) -> None:
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self._server.started and time.monotonic() < deadline:
            time.sleep(0.1)
        if not self._server.started:
            raise RuntimeError("buggy target server did not start in time")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10.0)


# --------------------------------------------------------------------------- #
# The one expensive live scan, shared across the assertions below
# --------------------------------------------------------------------------- #
@dataclass
class LiveScan:
    """Everything one live Schemathesis-through-ZAP run produced, for the tests."""

    result: DastResult
    zap_urls: list[str]
    target_url: str
    settings: DastSettings


@pytest.fixture(scope="module")
def live_scan() -> LiveScan:
    """Drive one real Schemathesis run through the real ZAP proxy at the buggy target.

    Applies the granular skips (tool presence, stack reachability) so an enabled-but-
    incomplete stack yields a precise skip rather than a spurious failure, then runs a
    single scan whose output every test in this module asserts over.
    """
    # 2. Tool presence — real CLI + the libs that host the in-process target.
    if shutil.which("schemathesis") is None:
        pytest.skip("the pinned 'schemathesis' CLI is not installed on PATH")
    pytest.importorskip("fastapi", reason="fastapi needed to host the buggy target")
    pytest.importorskip("uvicorn", reason="uvicorn needed to host the buggy target")
    pytest.importorskip("httpx", reason="httpx needed to probe/reissue requests")

    # Settings come from the environment (so DAST_ZAP_HOST/PORT/API_KEY are honoured),
    # exactly like production. The ZAP sidecar doubles as the Schemathesis proxy.
    settings = DastSettings()

    # 3a. Stack reachability — the ZAP proxy must be up (it is both the proxy the
    #     adapter routes through and the daemon whose site tree we inspect).
    zap_host = str(settings.DAST_ZAP_HOST)
    zap_port = int(settings.DAST_ZAP_PORT)
    if not _tcp_open(zap_host, zap_port):
        pytest.skip(
            f"ZAP sidecar not reachable at {zap_host}:{zap_port} — bring the daemon up"
        )

    # Resolve the buggy target: an external one if provided, else spin one up.
    external_url = os.environ.get(_TARGET_URL_ENV, "").strip()
    server: _BackgroundServer | None = None
    try:
        if external_url:
            target_url = external_url.rstrip("/")
        else:
            port = int(os.environ.get(_TARGET_PORT_ENV, "8099"))
            bind_host = os.environ.get(_TARGET_BIND_ENV, "0.0.0.0")
            # The base URL ZAP + schemathesis address. Defaults to the loopback the
            # host process can reach; override with DAST_IT_TARGET_HOST (e.g.
            # host.docker.internal) when ZAP runs in a container.
            url_host = os.environ.get(_TARGET_HOST_ENV, "127.0.0.1")
            server = _BackgroundServer(_build_buggy_app(), bind_host=bind_host, port=port)
            server.start()
            target_url = f"http://{url_host}:{port}"
            # 3b. Confirm the target is actually up from this process before scanning.
            if not _http_ok(f"http://127.0.0.1:{port}/health"):
                pytest.skip(f"buggy target did not become reachable on port {port}")

        # A fresh ZAP session so the site-tree assertion sees only THIS scan's traffic.
        from dast.adapters.zap_client import ZapClient

        with ZapClient(settings=settings) as client:
            try:
                client.reachable()
            except Exception as exc:  # noqa: BLE001 - not a ZAP daemon / keyed wrong
                pytest.skip(f"ZAP daemon did not answer a version ping: {exc}")
            client.new_session(f"schemathesis-it-{int(time.time())}")

            from dast.adapters.schemathesis_adapter import SchemathesisAdapter

            scope = DastScope(
                target_url=target_url,
                auth_header=settings.DAST_AUTH_HEADER,
                # Templatise the id segment so /widgets/1 and /widgets/2 collapse to
                # one endpoint identity (Req 9.2) — mirrors a real spec_paths seed.
                spec_paths=("/health", "/divide", "/widgets/{widget_id}"),
                profile="fast",
            )
            adapter = SchemathesisAdapter(settings=settings)

            # Run through the real runner so we get the coverage entry the trust model
            # produces — exactly what the service records (Req 11.1).
            result = run_scan(scope, adapters=[adapter])

            # After the proxied run, read ZAP's site tree: the dual payoff (Req 3.1,
            # 3.3, 10.4).
            zap_urls = client.urls(base_url=target_url)

        return LiveScan(
            result=result, zap_urls=zap_urls, target_url=target_url, settings=settings
        )
    finally:
        if server is not None:
            server.stop()


# --------------------------------------------------------------------------- #
# Small helpers over the scan result
# --------------------------------------------------------------------------- #
def _findings_by_kind(result: DastResult, prefix: str) -> list[Any]:
    """Findings whose stable rule_id starts with ``{kind}:`` (e.g. ``server_error:``)."""
    return [f for f in result.findings if f.rule_id.startswith(f"{prefix}:")]


def _schemathesis_coverage(result: DastResult) -> Any:
    """The single ``schemathesis`` coverage entry the runner recorded."""
    entries = [c for c in result.coverage if c.scanner == "schemathesis"]
    assert entries, "no schemathesis coverage entry was recorded"
    return entries[0]


# --------------------------------------------------------------------------- #
# Req 3.1, 3.3, 10.4 — the dual payoff: ZAP's site tree is seeded by the proxied run
# --------------------------------------------------------------------------- #
def test_proxied_run_seeds_zap_site_tree_before_active_scan(live_scan: LiveScan) -> None:
    """Validates: Requirements 3.1, 3.3, 10.4

    Every generated request routed through the ZAP proxy (Req 3.1) carrying the auth
    header (Req 3.3), so ZAP's site tree is now populated with the target's real
    endpoints — the map a later active ZAP scan attacks (Req 10.4). We assert the
    tree is non-empty and carries the buggy endpoints Schemathesis exercised.
    """
    urls = live_scan.zap_urls
    assert urls, (
        "ZAP's site tree is empty — Schemathesis traffic did not reach the target "
        "through the proxy, so the active scan would have nothing to attack"
    )
    joined = "\n".join(urls)
    # The endpoints Schemathesis generated cases for must appear on the map ZAP built.
    assert "/divide" in joined, "the /divide endpoint never landed on ZAP's site tree"
    assert "/widgets" in joined, "the /widgets endpoint never landed on ZAP's site tree"


# --------------------------------------------------------------------------- #
# Req 5.1 (+ Req 8 reproducing request) — undeclared 5xx → HIGH finding, reissuable
# --------------------------------------------------------------------------- #
def test_malformed_input_yields_high_severity_server_error_finding(
    live_scan: LiveScan,
) -> None:
    """Validates: Requirements 5.1

    The unguarded divide-by-zero makes ``POST /divide`` answer an undeclared 500 on a
    generated ``denominator=0``. Schemathesis's ``not_a_server_error`` check fails and
    the adapter converts it to a ``HIGH`` finding located on the responsible endpoint.
    """
    server_errors = _findings_by_kind(live_scan.result, "server_error")
    assert server_errors, "no undeclared-5xx finding was produced for /divide"

    finding = next(
        (f for f in server_errors if "/divide" in f.location.path), server_errors[0]
    )
    assert finding.severity is Severity.HIGH
    assert finding.scanner == "schemathesis"
    assert "/divide" in finding.location.path


def test_server_error_finding_carries_a_reissuable_reproducing_request(
    live_scan: LiveScan,
) -> None:
    """Validates: Requirements 5.1

    The finding's ``raw`` carries the reproducing request (method, path, headers,
    body). We reissue it against the live target and confirm it reproduces the 5xx —
    proving the recorded request is complete enough for a developer to act on without
    guesswork.
    """
    import httpx

    server_errors = _findings_by_kind(live_scan.result, "server_error")
    assert server_errors, "no undeclared-5xx finding to reissue"
    finding = next(
        (f for f in server_errors if "/divide" in f.location.path), server_errors[0]
    )

    repro = finding.raw.get("reproducing_request")
    assert isinstance(repro, dict) and not repro.get("unavailable"), (
        "the reproducing request must be captured, not marked unavailable"
    )
    method = str(repro.get("method", "")).upper()
    path = str(repro.get("path", ""))
    assert method and path, "the reproducing request must record a method and path"

    # Reissue directly against the target (not through the proxy) to confirm the bug.
    reissue_url = live_scan.target_url.rstrip("/") + path
    body = repro.get("body")
    headers = {
        k: v for k, v in dict(repro.get("headers") or {}).items()
        if k.lower() != "content-length"
    }
    try:
        content = None if body in (None, "") else body
        if isinstance(content, (dict, list)):
            resp = httpx.request(method, reissue_url, json=content, headers=headers, timeout=10)
        else:
            resp = httpx.request(method, reissue_url, content=content, headers=headers, timeout=10)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"could not reissue the recorded reproducing request: {exc}")

    assert 500 <= resp.status_code <= 599, (
        f"reissuing the recorded request returned {resp.status_code}, not a 5xx — "
        "the reproducing request did not reproduce the failure"
    )


# --------------------------------------------------------------------------- #
# Req 7.1 — a response violating its declared schema → a schema-violation finding
# --------------------------------------------------------------------------- #
def test_contract_violating_response_yields_schema_violation_finding(
    live_scan: LiveScan,
) -> None:
    """Validates: Requirements 7.1

    ``GET /widgets/{widget_id}`` returns a body missing the required ``name`` field,
    so the response violates its declared OpenAPI contract. Schemathesis's schema-
    conformance checks fail and the adapter emits a single schema-violation finding
    for the endpoint.
    """
    violations = _findings_by_kind(live_scan.result, "schema_violation")
    assert violations, "no schema-violation finding was produced for /widgets"

    finding = next(
        (f for f in violations if "/widgets" in f.location.path), violations[0]
    )
    assert finding.scanner == "schemathesis"
    assert "/widgets" in finding.location.path
    # The description names which contract element broke (Req 7.3/7.4 shape).
    assert finding.message


# --------------------------------------------------------------------------- #
# Req 11.1 — a completed run reports non-zero requests_made from the tool's own stats
# --------------------------------------------------------------------------- #
def test_completed_run_reports_nonzero_requests_made(live_scan: LiveScan) -> None:
    """Validates: Requirements 11.1

    The run reached the target, so its ``schemathesis`` coverage entry is ``complete``
    and its ToolActivity carries a non-zero ``requests_made`` — read from Schemathesis's
    own run statistics (requests that actually reached the target), the liveness signal
    that keeps "zero findings" honest.
    """
    coverage = _schemathesis_coverage(live_scan.result)
    activity = coverage.activity

    assert activity.requests_made is not None, (
        "requests_made is unknown — the run gave no honest evidence it contacted "
        "the target"
    )
    assert activity.requests_made > 0, (
        "requests_made is zero — the target was never actually contacted"
    )
    # A run that reached the target and produced findings must not read as incomplete.
    assert coverage.status == "complete", (
        f"expected a complete run, got '{coverage.status}': {coverage.reason}"
    )
