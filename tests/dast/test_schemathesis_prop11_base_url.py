# Feature: dast-schemathesis, Property 11: requests target only the configured base URL
"""Property 11 — requests target only the configured base URL.

**Validates: Requirements 2.3**

Schemathesis generates thousands of requests from the target's OpenAPI schema, and the
one thing that must never drift is *where those requests go*. Requirement 2.3 is
categorical: every generated request is sent to the Base_URL carried on
``DastScope.target_url``, and none is sent to any other host. The adapter enforces this
with a single flag — it passes ``--base-url <scope.target_url>`` — so Schemathesis
confines every generated request to that exact origin.

This property asserts the invariant at that seam: *for any* valid target URL, the
recorded ``--base-url`` argument equals ``scope.target_url`` **exactly** — same scheme,
host, port, and path, with no rewriting, normalisation, or truncation. If the flag ever
differed from the configured target, requests could be aimed at a host the operator did
not authorise, which is precisely the failure this property forbids.

The invariant is checked over the command-builder + ``_run`` seam using the in-memory
fake in ``tests/dast/_schemathesis_fakes.py`` — no subprocess, no network. The proxy is
left unconfigured so no reachability probe runs, and a fixed integer seed keeps the
default fast profile off the hard-failure path. The recorded ``--base-url`` value is
read back via :attr:`RecordedRun.base_url`.
"""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from dast.models import DastScope
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, make_adapter


# --------------------------------------------------------------------------- #
# Stub settings — only the knobs scan() reads on this path. Proxy unconfigured
# so _check_proxy_reachable never runs; a fixed seed keeps the fast profile
# valid (off the hard-failure path); a file schema keeps _schema_source local.
# --------------------------------------------------------------------------- #
def _make_settings() -> SimpleNamespace:
    """A minimal DastSettings stand-in for the base-URL path."""
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=None,
        DAST_SCHEMATHESIS_SEED=0,
        # A file schema keeps _schema_source local (no --wait-for-schema window).
        DAST_SCHEMATHESIS_SCHEMA_FILE="/tmp/openapi.json",
        DAST_OPENAPI_PATH="/openapi.json",
        # Proxy unconfigured → no reachability check, no proxy flags/env.
        DAST_ZAP_HOST=None,
        DAST_ZAP_PORT=None,
        DAST_SCHEMATHESIS_RATE_LIMIT=10,
        DAST_SCHEMATHESIS_CONNECT_TIMEOUT=30,
        DAST_SCHEMATHESIS_SCHEMA_TIMEOUT=30,
        DAST_SCHEMATHESIS_TIMEOUT=900,
        DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT=5,
    )


def _recorded_base_url(target_url: str, *, profile: str = "fast") -> str | None:
    """Drive one scan through the faked seam and return the recorded --base-url."""
    fake = FakeSchemathesisRun()  # returncode 0, empty report → clean completion
    adapter = make_adapter(settings=_make_settings(), fake=fake)
    adapter.scan(DastScope(target_url=target_url, profile=profile))
    return fake.last.base_url


# --------------------------------------------------------------------------- #
# Strategy — arbitrary valid target URLs (scheme, host, optional port + path)
# --------------------------------------------------------------------------- #
# A DAST target is a live HTTP(S) origin. We vary every part that could tempt a
# rewrite: scheme, host label shape, an optional explicit port, and an optional
# base path. The production-refusal pattern is disabled in the stub settings, so
# any of these is a legal, non-refused target for this path.
_SCHEME = st.sampled_from(["http", "https"])

_HOST_LABEL = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
    min_size=1,
    max_size=12,
).filter(lambda s: not s.startswith("-") and not s.endswith("-"))

_HOST = st.lists(_HOST_LABEL, min_size=1, max_size=4).map(".".join)

_PORT = st.one_of(
    st.none(),
    st.integers(min_value=1, max_value=65535),
)

_PATH = st.one_of(
    st.just(""),
    st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=8),
        min_size=1,
        max_size=3,
    ).map(lambda parts: "/" + "/".join(parts)),
)


@st.composite
def _target_urls(draw) -> str:
    scheme = draw(_SCHEME)
    host = draw(_HOST)
    port = draw(_PORT)
    path = draw(_PATH)
    authority = host if port is None else f"{host}:{port}"
    return f"{scheme}://{authority}{path}"


# --------------------------------------------------------------------------- #
# The property: recorded --base-url equals scope.target_url exactly
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(target_url=_target_urls())
def test_base_url_equals_configured_target_exactly(target_url: str) -> None:
    """Validates: Requirements 2.3

    For any valid target URL, the recorded --base-url equals scope.target_url
    verbatim — no rewriting, normalisation, or host substitution — so every
    generated request is confined to exactly the configured origin.
    """
    recorded = _recorded_base_url(target_url)
    assert recorded == target_url


@hyp_settings(max_examples=200)
@given(target_url=_target_urls())
def test_base_url_present_on_deep_profile_too(target_url: str) -> None:
    """Validates: Requirements 2.3

    The confinement flag is independent of the generation profile: an unseeded
    deep run still targets only the configured base URL.
    """
    recorded = _recorded_base_url(target_url, profile="deep")
    assert recorded == target_url


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_plain_host() -> None:
    assert _recorded_base_url("http://target.internal") == "http://target.internal"


def test_example_host_with_port_and_path() -> None:
    url = "https://staging.example.com:8443/api/v2"
    assert _recorded_base_url(url) == url
