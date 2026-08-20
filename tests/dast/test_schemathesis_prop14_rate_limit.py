# Feature: dast-schemathesis, Property 14: the rate limit is clamped into range with a safe default
"""Property 14 — the rate limit is clamped into range with a safe default.

**Validates: Requirements 13.1, 13.2**

The Schemathesis adapter caps outgoing traffic so a single-worker target is not jammed
into timing out — a scan that "looks clean" only because its requests never landed is
the exact failure mode the whole service exists to avoid. So the configured request
rate is read from ``DAST_SCHEMATHESIS_RATE_LIMIT`` and clamped into ``1..1000`` req/s:

* *for any* integer setting inside ``1..1000`` the recorded ``--rate-limit`` uses that
  exact value (Req 13.1);
* *for any* value outside ``1..1000`` — or an absent/non-integer one — the adapter
  falls back to the safe default of ``10`` req/s rather than firing unbounded
  (Req 13.2); and
* the emitted rate is therefore *always* a value inside ``1..1000``.

The invariant is checked over the command-builder + ``_run`` seam using the in-memory
fake in ``tests/dast/_schemathesis_fakes.py`` — no subprocess, no network. The proxy is
left unconfigured so no reachability probe runs, and a fixed integer seed keeps the
default fast profile off the hard-failure path. The recorded ``--rate-limit`` value
(e.g. ``"10/s"``) is read back via :attr:`RecordedRun.rate_limit`.
"""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from dast.models import DastScope
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, make_adapter

#: The safe default applied when the setting is absent or out of range (Req 13.2).
_DEFAULT_RATE = 10
#: The inclusive clamp range (Req 13.1).
_MIN_RATE, _MAX_RATE = 1, 1000


# --------------------------------------------------------------------------- #
# Stub settings — only the knobs scan() reads on this path, proxy unconfigured
# so _check_proxy_reachable is never invoked and a fixed seed keeps fast valid.
# --------------------------------------------------------------------------- #
def _make_settings(*, rate_limit: object) -> SimpleNamespace:
    """A minimal DastSettings stand-in with a configurable Schemathesis rate limit."""
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=None,
        DAST_SCHEMATHESIS_SEED=0,
        # A file schema keeps _schema_source local (no --wait-for-schema window).
        DAST_SCHEMATHESIS_SCHEMA_FILE="/tmp/openapi.json",
        DAST_OPENAPI_PATH="/openapi.json",
        # Proxy unconfigured → no reachability check, no proxy flags/env.
        DAST_ZAP_HOST=None,
        DAST_ZAP_PORT=None,
        DAST_SCHEMATHESIS_RATE_LIMIT=rate_limit,
        DAST_SCHEMATHESIS_CONNECT_TIMEOUT=30,
        DAST_SCHEMATHESIS_SCHEMA_TIMEOUT=30,
        DAST_SCHEMATHESIS_TIMEOUT=900,
        DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT=5,
    )


def _scope() -> DastScope:
    return DastScope(target_url="http://target.internal", profile="fast")


def _recorded_rate(rate_limit: object) -> int:
    """Drive one scan through the faked seam and return the emitted integer req/s."""
    fake = FakeSchemathesisRun()  # returncode 0, empty report → clean completion
    adapter = make_adapter(settings=_make_settings(rate_limit=rate_limit), fake=fake)
    adapter.scan(_scope())

    recorded = fake.last.rate_limit
    # The adapter always passes the rate as "<value>/s".
    assert recorded is not None and recorded.endswith("/s"), recorded
    return int(recorded[: -len("/s")])


# --------------------------------------------------------------------------- #
# Strategies — the whole rate-limit input space
# --------------------------------------------------------------------------- #
# Integer settings that sit inside the clamp range → used verbatim.
_IN_RANGE = st.integers(min_value=_MIN_RATE, max_value=_MAX_RATE)

# Integer settings outside the range (below 1 or above 1000) → default applied.
_OUT_OF_RANGE = st.one_of(
    st.integers(max_value=_MIN_RATE - 1),
    st.integers(min_value=_MAX_RATE + 1),
)

# Absent or non-integer settings → default applied. The setting's declared type is an
# integer, so the untrusted-input cases that matter are "absent" (None) and values that
# cannot be read as an integer bound at all (non-numeric text).
_ABSENT_OR_INVALID = st.one_of(
    st.none(),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz-_ ", min_size=1, max_size=12),
    st.just(""),
)


# --------------------------------------------------------------------------- #
# In range → used as-is
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(rate=_IN_RANGE)
def test_in_range_rate_is_used_verbatim(rate: int) -> None:
    """Validates: Requirements 13.1

    Any integer setting inside 1..1000 is emitted exactly as configured, and is (by
    construction) itself within the allowed range.
    """
    emitted = _recorded_rate(rate)
    assert emitted == rate
    assert _MIN_RATE <= emitted <= _MAX_RATE


# --------------------------------------------------------------------------- #
# Out of range → safe default
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(rate=_OUT_OF_RANGE)
def test_out_of_range_rate_falls_back_to_default(rate: int) -> None:
    """Validates: Requirements 13.2

    Any integer setting outside 1..1000 falls back to the safe default of 10 req/s,
    which is itself inside the allowed range.
    """
    emitted = _recorded_rate(rate)
    assert emitted == _DEFAULT_RATE
    assert _MIN_RATE <= emitted <= _MAX_RATE


# --------------------------------------------------------------------------- #
# Absent / non-integer → safe default
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(rate=_ABSENT_OR_INVALID)
def test_absent_or_invalid_rate_falls_back_to_default(rate: object) -> None:
    """Validates: Requirements 13.2

    An absent or non-integer setting cannot be trusted as a bound, so the adapter
    applies the safe default of 10 req/s rather than firing at an unbounded rate.
    """
    emitted = _recorded_rate(rate)
    assert emitted == _DEFAULT_RATE
    assert _MIN_RATE <= emitted <= _MAX_RATE


# --------------------------------------------------------------------------- #
# The umbrella invariant: the emitted rate is ALWAYS within 1..1000
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(rate=st.one_of(_IN_RANGE, _OUT_OF_RANGE, _ABSENT_OR_INVALID))
def test_emitted_rate_is_always_within_range(rate: object) -> None:
    """Validates: Requirements 13.1, 13.2

    Whatever the setting — in range, out of range, absent, or garbage — the rate the
    adapter actually hands Schemathesis is always a value inside 1..1000.
    """
    emitted = _recorded_rate(rate)
    assert _MIN_RATE <= emitted <= _MAX_RATE


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_default_rate_is_ten() -> None:
    assert _recorded_rate(10) == 10


def test_example_boundaries_are_kept() -> None:
    assert _recorded_rate(1) == 1
    assert _recorded_rate(1000) == 1000


def test_example_just_below_and_above_range_default() -> None:
    assert _recorded_rate(0) == _DEFAULT_RATE
    assert _recorded_rate(1001) == _DEFAULT_RATE
    assert _recorded_rate(-5) == _DEFAULT_RATE
