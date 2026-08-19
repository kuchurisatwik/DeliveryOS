# Feature: dast-schemathesis, Property 9: the auth header is attached to every outgoing request, or none
"""Property 9 — the auth header is attached to every outgoing request, or none.

**Validates: Requirements 2.4, 3.3**

An authenticated scan is worthless if the token leaks onto only *some* requests, and
a supposedly anonymous scan is a lie if a stale ``Authorization`` header rides along
on the side. The adapter therefore commits to an all-or-nothing rule at the
command-builder seam:

* *whenever* ``DastScope.auth_header`` is set, the recorded argument vector carries a
  single ``--header`` flag whose value is exactly ``Authorization: <auth_header>`` —
  the unmodified token — so Schemathesis stamps it on **every** generated request, and
  (Req 3.3) the same unmodified value reaches the proxied traffic that seeds ZAP; and
* *whenever* ``auth_header`` is unset (``None`` or empty), there is **no** ``--header``
  flag and the string ``Authorization`` appears nowhere in the argv or the subprocess
  environment — never a blank or partial header (Req 2.4).

Because Schemathesis applies a single ``--header`` uniformly to all cases it emits,
"attached to the CLI once" *is* "attached to every outgoing request" — there is no
per-request codepath that could attach it to only some. The invariant is checked over
the command-builder + ``_run`` seam using the in-memory fake in
``tests/dast/_schemathesis_fakes.py`` — no subprocess, no network. The proxy is left
unconfigured so no reachability probe runs, and a fixed integer seed keeps the default
fast profile off the hard-failure path.
"""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from dast.models import DastScope
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, RecordedRun, make_adapter


# --------------------------------------------------------------------------- #
# Stub settings — only the knobs scan() reads on this path. Proxy unconfigured
# so _check_proxy_reachable is never invoked, a fixed seed keeps fast valid, and
# a file schema keeps _schema_source local (no --wait-for-schema window).
# --------------------------------------------------------------------------- #
def _make_settings() -> SimpleNamespace:
    """A minimal DastSettings stand-in for the auth-header path."""
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=None,
        DAST_SCHEMATHESIS_SEED=0,
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


def _record(*, auth_header: object) -> RecordedRun:
    """Drive one scan through the faked seam and return what it would have executed."""
    fake = FakeSchemathesisRun()  # returncode 0, empty report → clean completion
    adapter = make_adapter(settings=_make_settings(), fake=fake)
    adapter.scan(
        DastScope(
            target_url="http://target.internal",
            profile="fast",
            auth_header=auth_header,  # type: ignore[arg-type]
        )
    )
    return fake.last


def _authorization_anywhere(recorded: RecordedRun) -> bool:
    """True if the string 'Authorization' appears anywhere in the argv or the env."""
    if any("Authorization" in token for token in recorded.argv):
        return True
    for key, value in recorded.env.items():
        if "Authorization" in key or "Authorization" in value:
            return True
    return False


# --------------------------------------------------------------------------- #
# Strategies — the auth-header input space
# --------------------------------------------------------------------------- #
# A "set" auth header is any non-empty token. Real values are bearer/basic tokens,
# but the invariant must hold for any non-empty string the operator supplies, so the
# generator ranges widely (incl. spaces and punctuation) while staying non-empty.
_SET_HEADER = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip() != "")

# "Unset" means the adapter treats it as no auth: None or an empty/blank string
# (the adapter's guard is a plain truthiness check on scope.auth_header).
_UNSET_HEADER = st.sampled_from([None, ""])


# --------------------------------------------------------------------------- #
# Set → the exact header rides on the single --header flag
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(auth_header=_SET_HEADER)
def test_set_auth_header_is_attached_exactly_once(auth_header: str) -> None:
    """Validates: Requirements 2.4, 3.3

    When the scope carries an auth header, exactly one --header flag is emitted and
    its value is the unmodified ``Authorization: <value>``, so every generated (and
    proxied) request carries the same token.
    """
    recorded = _record(auth_header=auth_header)
    headers = recorded.headers

    assert headers == [f"Authorization: {auth_header}"]
    # And there is exactly one --header flag — the token is attached uniformly, never
    # to only some requests.
    assert recorded.argv.count("--header") == 1


# --------------------------------------------------------------------------- #
# Unset → no header anywhere in argv or env
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(auth_header=_UNSET_HEADER)
def test_unset_auth_header_leaves_no_authorization_anywhere(auth_header: object) -> None:
    """Validates: Requirements 2.4

    When no auth header is set, the adapter runs anonymously: no --header flag, and
    the string 'Authorization' appears nowhere in the argv or the subprocess env — a
    stale or blank header never leaks onto the traffic.
    """
    recorded = _record(auth_header=auth_header)

    assert recorded.headers == []
    assert not recorded.has_flag("--header")
    assert not _authorization_anywhere(recorded)


# --------------------------------------------------------------------------- #
# The umbrella invariant: all-or-nothing across the whole input space
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(auth_header=st.one_of(_SET_HEADER, _UNSET_HEADER))
def test_auth_header_is_all_or_nothing(auth_header: object) -> None:
    """Validates: Requirements 2.4, 3.3

    Whatever the scope carries, the outcome is binary: either the exact auth header is
    the single --header value (set), or 'Authorization' is absent everywhere (unset).
    There is no in-between where a blank or partial header is emitted.
    """
    recorded = _record(auth_header=auth_header)

    if auth_header:
        assert recorded.headers == [f"Authorization: {auth_header}"]
        assert _authorization_anywhere(recorded)
    else:
        assert recorded.headers == []
        assert not _authorization_anywhere(recorded)


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_bearer_token_is_attached() -> None:
    recorded = _record(auth_header="Bearer eyJhbGciOi.abc.def")
    assert recorded.headers == ["Authorization: Bearer eyJhbGciOi.abc.def"]


def test_example_none_is_anonymous() -> None:
    recorded = _record(auth_header=None)
    assert not recorded.has_flag("--header")
    assert not _authorization_anywhere(recorded)


def test_example_empty_string_is_anonymous() -> None:
    recorded = _record(auth_header="")
    assert not recorded.has_flag("--header")
    assert not _authorization_anywhere(recorded)
