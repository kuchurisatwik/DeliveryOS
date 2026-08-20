# Feature: dast-schemathesis, Property 10: every generated request routes through the proxy when one is configured
"""Property 10 — every generated request routes through the proxy when one is configured.

*For any* set of generated requests, when the ZAP proxy is configured (host **and**
port both present and non-empty) every outgoing request reaches the target only by way
of that proxy; when the proxy host or port is absent or empty the proxy is treated as
not configured and Schemathesis talks to the target directly.

**Validates: Requirements 3.1, 3.2**

Schemathesis has no per-request proxy channel: routing is decided once, when the
adapter builds the command. It pins the proxy on two redundant channels so *no*
generated request can slip past it — the explicit ``--request-proxy`` CLI flag and the
``HTTP_PROXY`` / ``HTTPS_PROXY`` subprocess environment variables — or on neither when
the proxy is unconfigured. This test drives the real
:meth:`SchemathesisAdapter.scan` through the in-memory ``_run`` seam
(:class:`FakeSchemathesisRun`), which records the exact ``(argv, env)`` the adapter
would have executed with no subprocess and no network, and asserts:

* **configured** (host + port both non-empty, port a positive integer) — the recorded
  command carries ``--request-proxy http://<host>:<port>`` and both ``HTTP_PROXY`` and
  ``HTTPS_PROXY`` set to that same URL; and
* **not configured** (host or port absent/empty, or port zero/negative) — no
  ``--request-proxy`` flag and neither proxy environment variable is set.

The proxy reachability probe (the one piece of I/O ``scan()`` performs on the
configured path) is stubbed so the property never touches the network.
"""

from __future__ import annotations

from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from dast.config import DastSettings
from dast.models import DastScope
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, make_adapter


# --------------------------------------------------------------------------- #
# Generators — the full host/port present/absent/empty space
# --------------------------------------------------------------------------- #
# Valid, non-empty proxy hosts (IPs and DNS names). Some carry surrounding
# whitespace so the "non-empty after strip" rule is exercised.
_REAL_HOSTS = st.sampled_from(
    ["127.0.0.1", "localhost", "zap", "zap.internal", "10.0.0.5", "proxy.test"]
)
# Empty / whitespace-only hosts count as "absent" (proxy not configured).
_BLANK_HOSTS = st.sampled_from(["", "   ", "\t"])
_HOSTS = st.one_of(_REAL_HOSTS, _BLANK_HOSTS)

# DAST_ZAP_PORT is an int field. A positive value configures the proxy; 0 or a
# negative value means "not configured".
_PORTS = st.one_of(
    st.integers(min_value=1, max_value=65535),
    st.just(0),
    st.integers(min_value=-5, max_value=0),
)

# Non-production staging targets (default PROD_URL_PATTERN is None -> never refused).
_TARGET_URLS = st.sampled_from(
    [
        "https://staging.test",
        "http://localhost:8000",
        "https://qa.internal.example",
        "https://staging.example.com/app",
    ]
)
_PROFILES = st.sampled_from(["fast", "deep"])


def _expected_proxy_url(host: str, port: int) -> str | None:
    """Mirror ``SchemathesisAdapter._proxy_target`` -> the expected proxy URL, or None.

    Configured only when the host is non-empty after stripping AND the port is a
    positive integer; otherwise the proxy is not configured.
    """
    if host is None or not str(host).strip():
        return None
    if port is None or int(port) <= 0:
        return None
    return f"http://{str(host).strip()}:{int(port)}"


def _build_settings(*, host, port) -> DastSettings:
    """DastSettings from declared defaults with the ZAP host/port overridden.

    ``_env_file=None`` ignores any local ``.env`` so behaviour reflects the given
    host/port only. A fixed integer seed keeps the default fast profile off the
    hard-failure path; the schema file and prod pattern are cleared so ``scan()``
    reaches the command builder for every example.
    """
    return DastSettings(
        _env_file=None,
        DAST_ZAP_HOST=host,
        DAST_ZAP_PORT=port,
        DAST_SCHEMATHESIS_SEED=0,
        DAST_SCHEMATHESIS_SCHEMA_FILE=None,
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=None,
        DAST_OPENAPI_PATH="/openapi.json",
    )


# --------------------------------------------------------------------------- #
# The property
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(
    host=_HOSTS,
    port=_PORTS,
    target_url=_TARGET_URLS,
    profile=_PROFILES,
)
def test_every_request_routes_through_the_proxy_when_configured(
    host, port, target_url, profile
):
    """Validates: Requirements 3.1, 3.2

    When the ZAP proxy is configured (host + port both non-empty/valid) the recorded
    command carries ``--request-proxy`` and both proxy env vars pointing at that
    proxy; when either is absent/empty no proxy flag or env var is set.
    """
    expected = _expected_proxy_url(host, port)

    scope = DastScope(
        target_url=target_url,
        commit_sha="deadbeef",
        profile=profile,
    )
    adapter_settings = _build_settings(host=host, port=port)
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=adapter_settings, fake=fake)

    # The reachability probe is the only I/O scan() performs; stub it so the
    # configured path never touches the network (it succeeds by default).
    with patch("dast.adapters.schemathesis_adapter.socket.create_connection"):
        adapter.scan(scope)

    assert fake.called, "scan() must reach the _run seam and build the command"
    run = fake.last

    if expected is not None:
        # Configured: the flag and BOTH env vars pin the proxy, all to the same URL.
        assert run.request_proxy == expected
        assert run.http_proxy == expected
        assert run.https_proxy == expected
    else:
        # Not configured: no proxy flag, no proxy env vars.
        assert run.request_proxy is None
        assert not run.has_flag("--request-proxy")
        assert run.http_proxy is None
        assert run.https_proxy is None


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_configured_proxy_pins_flag_and_both_env_vars():
    settings_ = _build_settings(host="zap", port=8090)
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=settings_, fake=fake)

    with patch("dast.adapters.schemathesis_adapter.socket.create_connection"):
        adapter.scan(DastScope(target_url="https://staging.test"))

    run = fake.last
    assert run.request_proxy == "http://zap:8090"
    assert run.http_proxy == "http://zap:8090"
    assert run.https_proxy == "http://zap:8090"


def test_example_blank_host_means_no_proxy():
    settings_ = _build_settings(host="", port=8090)
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=settings_, fake=fake)

    # No probe should run when the proxy is unconfigured; leave the network alone.
    adapter.scan(DastScope(target_url="https://staging.test"))

    run = fake.last
    assert run.request_proxy is None
    assert run.http_proxy is None
    assert run.https_proxy is None


def test_example_zero_port_means_no_proxy():
    settings_ = _build_settings(host="127.0.0.1", port=0)
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=settings_, fake=fake)

    adapter.scan(DastScope(target_url="https://staging.test"))

    run = fake.last
    assert run.request_proxy is None
    assert run.http_proxy is None
    assert run.https_proxy is None
