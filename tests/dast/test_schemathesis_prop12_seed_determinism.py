# Feature: dast-schemathesis, Property 12: generation is reproducible on fast and exploratory on deep
"""Property 12 — generation is reproducible on fast and exploratory on deep.

**Validates: Requirements 4.1, 4.2, 4.4**

A fixed generation seed is what makes the ``fast`` profile *reproducible*: the same
schema and configuration yield the same generated cases, so a finding can be re-run and
re-confirmed. The ``deep`` profile deliberately runs *unseeded* (exploratory) so a
nightly run keeps exploring new inputs. And a ``fast`` run whose seed is missing or
non-integer is refused outright — silently running a non-reproducible fast scan whose
findings can never be re-confirmed is the exact failure mode this rule exists to avoid.

Expressed over the command-builder + ``_run`` seam (the in-memory fake in
``tests/dast/_schemathesis_fakes.py`` — no subprocess, no network):

* *for any* ``fast`` profile with a valid integer seed, the recorded argument vector
  carries ``--hypothesis-seed <seed>`` with that exact value, and two runs with the same
  seed record the same value → reproducible (Req 4.1);
* *for any* ``deep`` profile, no ``--hypothesis-seed`` flag is emitted → exploratory
  (Req 4.2); and
* *for any* ``fast`` profile with a missing or non-integer seed, ``scan()`` raises
  :class:`ScannerError` and sends nothing rather than running non-reproducibly
  (Req 4.4).

The proxy is left unconfigured so no reachability probe runs, and a file schema keeps
``_schema_source`` local (no ``--wait-for-schema`` window). The recorded
``--hypothesis-seed`` value is read back via :attr:`RecordedRun.seed`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.security.detection.adapters.base import ScannerError
from dast.models import DastScope
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, make_adapter

_SEED_FLAG = "--hypothesis-seed"


# --------------------------------------------------------------------------- #
# Stub settings — only the knobs scan() reads on this path. Proxy unconfigured
# so _check_proxy_reachable never runs; a file schema stays local.
# --------------------------------------------------------------------------- #
def _make_settings(*, seed: object) -> SimpleNamespace:
    """A minimal DastSettings stand-in with a configurable Schemathesis seed."""
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=None,
        DAST_SCHEMATHESIS_SEED=seed,
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


def _scope(profile: str) -> DastScope:
    return DastScope(target_url="http://target.internal", profile=profile)


def _run_scan(*, seed: object, profile: str) -> FakeSchemathesisRun:
    """Drive one scan through the faked seam and return the fake for inspection."""
    fake = FakeSchemathesisRun()  # returncode 0, empty report → clean completion
    adapter = make_adapter(settings=_make_settings(seed=seed), fake=fake)
    adapter.scan(_scope(profile))
    return fake


# --------------------------------------------------------------------------- #
# Strategies — the seed input space
# --------------------------------------------------------------------------- #
# Valid integer seeds: the setting's declared type. Any integer is accepted and
# emitted verbatim.
_VALID_SEED = st.integers()

# Missing or non-integer seeds → refused. The untrusted-input cases that matter are
# "absent" (None), a bool (explicitly rejected — a bool is not a seed), and values
# that cannot be read as an integer at all (non-numeric / fractional text).
_INVALID_SEED = st.one_of(
    st.none(),
    st.booleans(),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz-_ ", min_size=1, max_size=12),
    st.just(""),
    st.just("1.5"),
    st.just("abc123"),
)


# --------------------------------------------------------------------------- #
# fast + valid seed → --hypothesis-seed <seed>, reproducible
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(seed=_VALID_SEED)
def test_fast_with_valid_seed_emits_that_seed(seed: int) -> None:
    """Validates: Requirements 4.1

    A fast run with a valid integer seed carries --hypothesis-seed with that exact
    value, so generation is pinned and reproducible.
    """
    fake = _run_scan(seed=seed, profile="fast")
    assert fake.last.has_flag(_SEED_FLAG)
    assert fake.last.seed == str(seed)


@hyp_settings(max_examples=200)
@given(seed=_VALID_SEED)
def test_fast_is_reproducible_across_runs(seed: int) -> None:
    """Validates: Requirements 4.1

    Two fast runs with the same fixed seed record the same --hypothesis-seed value, so
    the same schema + configuration yields the same generated cases (reproducible).
    """
    first = _run_scan(seed=seed, profile="fast")
    second = _run_scan(seed=seed, profile="fast")
    assert first.last.seed == second.last.seed == str(seed)


# --------------------------------------------------------------------------- #
# deep → no --hypothesis-seed (exploratory)
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=100)
@given(seed=st.one_of(_VALID_SEED, _INVALID_SEED))
def test_deep_runs_unseeded(seed: object) -> None:
    """Validates: Requirements 4.2

    The deep profile runs unseeded whatever the configured seed value — no
    --hypothesis-seed flag is emitted, so each nightly run keeps exploring new inputs.
    """
    fake = _run_scan(seed=seed, profile="deep")
    assert not fake.last.has_flag(_SEED_FLAG)
    assert fake.last.seed is None


# --------------------------------------------------------------------------- #
# fast + missing/invalid seed → ScannerError, nothing sent
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(seed=_INVALID_SEED)
def test_fast_with_invalid_seed_raises(seed: object) -> None:
    """Validates: Requirements 4.4

    A fast run whose seed is missing or non-integer is refused: scan() raises
    ScannerError and never reaches the command-builder seam, so no request is sent.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(seed=seed), fake=fake)
    with pytest.raises(ScannerError):
        adapter.scan(_scope("fast"))
    # Refused before building the command → the seam was never driven.
    assert not fake.called


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_default_seed_zero_is_emitted() -> None:
    fake = _run_scan(seed=0, profile="fast")
    assert fake.last.seed == "0"


def test_example_deep_ignores_seed() -> None:
    assert _run_scan(seed=12345, profile="deep").last.seed is None


def test_example_missing_seed_on_fast_raises() -> None:
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(seed=None), fake=fake)
    with pytest.raises(ScannerError):
        adapter.scan(_scope("fast"))
    assert not fake.called
