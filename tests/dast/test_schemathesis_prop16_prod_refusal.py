# Feature: dast-schemathesis, Property 16: a scan against a production target sends nothing and reports incomplete
"""Property 16 — a scan against a production target sends nothing and reports incomplete.

**Validates: Requirements 14.2, 14.3**

Schemathesis sends deliberately malformed and state-changing traffic, so it must never
touch production. Before any generated request leaves the scanner, ``scan()`` decides
whether the target is a Production_Target by matching ``target_url`` against the
configured ``DAST_SCHEMATHESIS_PROD_URL_PATTERN`` regex. When it matches, the adapter
refuses outright: it sends **zero** requests and raises :class:`ScannerError`, so the
Runner records an ``incomplete`` ToolCoverage entry whose reason states the scan was
refused because the target is a Production_Target (Req 14.2, 14.3).

Expressed over the command-builder + ``_run`` seam (the in-memory fake in
``tests/dast/_schemathesis_fakes.py`` — no subprocess, no network):

* *for any* ``target_url`` matching the configured production pattern, ``scan()`` raises
  :class:`ScannerError` and the command-builder/``_run`` seam is *never* driven — so
  nothing is sent (Req 14.2, 14.3); and
* *for any* ``target_url`` that does **not** match — including when no pattern is
  configured — the scan proceeds normally and *does* drive the seam.

The refusal is checked strictly before seed resolution and schema loading, so a valid
seed and a local file schema are configured only to prove the *non-matching* branch
runs to completion; on the matching branch they are never reached. The proxy is left
unconfigured so no reachability probe runs.
"""

from __future__ import annotations

import re
import string
from types import SimpleNamespace

import pytest
from hypothesis import assume, given, settings as hyp_settings
from hypothesis import strategies as st

from app.security.detection.adapters.base import ScannerError
from dast.models import DastScope
from dast.runner import run_scan
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, make_adapter

SCANNER_NAME = "schemathesis"

#: A representative production pattern. Its alternation is what every "matching" URL is
#: built to contain and every "non-matching" URL is filtered against.
_PROD_PATTERN = r"prod|production|prd"

#: Literals guaranteed to satisfy ``_PROD_PATTERN`` — a matching URL embeds one.
_PROD_TOKENS = ("prod", "production", "prd")


# --------------------------------------------------------------------------- #
# Stub settings — only the knobs scan() reads on this path. Proxy unconfigured
# so _check_proxy_reachable never runs; a valid seed + file schema keep the
# non-matching branch off every hard-failure path so it runs to completion.
# --------------------------------------------------------------------------- #
def _make_settings(*, pattern: object) -> SimpleNamespace:
    """A minimal DastSettings stand-in with a configurable production URL pattern."""
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=pattern,
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


def _scope(target_url: str) -> DastScope:
    return DastScope(target_url=target_url, profile="fast")


# --------------------------------------------------------------------------- #
# Strategies — the target-URL input space
# --------------------------------------------------------------------------- #
# Host/path fragments from a restricted alphabet, kept short so the assume() below
# rarely rejects a candidate.
_FRAGMENT = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-", min_size=1, max_size=8
)
_SCHEME = st.sampled_from(["http://", "https://"])


@st.composite
def _matching_url(draw: st.DrawFn) -> str:
    """A target URL guaranteed to match ``_PROD_PATTERN`` (embeds a prod token)."""
    scheme = draw(_SCHEME)
    token = draw(st.sampled_from(_PROD_TOKENS))
    left = draw(_FRAGMENT)
    right = draw(_FRAGMENT)
    url = f"{scheme}{left}-{token}-{right}.example.com/api"
    # Sanity: the constructed URL really does match the configured pattern.
    assert re.search(_PROD_PATTERN, url)
    return url


@st.composite
def _non_matching_url(draw: st.DrawFn) -> str:
    """A non-production target URL that does NOT match ``_PROD_PATTERN``."""
    scheme = draw(_SCHEME)
    host = draw(st.sampled_from(["staging", "dev", "qa", "test", "localhost", "internal"]))
    suffix = draw(_FRAGMENT)
    url = f"{scheme}{host}-{suffix}.example.com/api"
    # A random fragment could still spell a prod token; drop those so this stays the
    # genuinely non-matching branch.
    assume(not re.search(_PROD_PATTERN, url))
    return url


# --------------------------------------------------------------------------- #
# Matching target → refuse, send nothing (Req 14.2, 14.3)
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(target_url=_matching_url())
def test_production_target_is_refused_and_sends_nothing(target_url: str) -> None:
    """Validates: Requirements 14.2, 14.3

    Any target URL matching the production pattern is refused: scan() raises
    ScannerError before the command-builder/_run seam is ever driven, so zero requests
    are sent.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(pattern=_PROD_PATTERN), fake=fake)

    with pytest.raises(ScannerError) as excinfo:
        adapter.scan(_scope(target_url))

    # Nothing sent: the seam was never reached.
    assert fake.called is False
    # The reason names the refusal so the runner's incomplete entry is diagnostic.
    assert excinfo.value.scanner == "schemathesis"
    assert "production" in excinfo.value.reason.lower()


# --------------------------------------------------------------------------- #
# Non-matching target → scan proceeds and drives the seam
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(target_url=_non_matching_url())
def test_non_production_target_proceeds(target_url: str) -> None:
    """Validates: Requirements 14.2, 14.3

    A target URL that does not match the production pattern is not a Production_Target,
    so the scan proceeds normally and drives the command-builder/_run seam.
    """
    fake = FakeSchemathesisRun()  # returncode 0, empty report → clean completion
    adapter = make_adapter(settings=_make_settings(pattern=_PROD_PATTERN), fake=fake)

    adapter.scan(_scope(target_url))

    # The seam WAS driven → the scan actually ran against the (non-prod) target.
    assert fake.called is True
    assert fake.last.base_url == target_url


# --------------------------------------------------------------------------- #
# Routing through the runner's _run_one → incomplete ToolCoverage (Req 14.2, 14.3)
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=100)
@given(target_url=_matching_url())
def test_production_refusal_routes_to_incomplete_coverage(target_url: str) -> None:
    """Validates: Requirements 14.2, 14.3

    The ScannerError raised for a production target is turned by the runner's _run_one
    into an ``incomplete`` ToolCoverage whose reason states the production refusal, and
    the seam is still never driven (nothing sent).
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(pattern=_PROD_PATTERN), fake=fake)

    result = run_scan(_scope(target_url), [adapter])

    # The refusal flows through _run_one as one incomplete coverage entry.
    assert len(result.coverage) == 1
    cov = result.coverage[0]
    assert cov.scanner == SCANNER_NAME
    assert cov.status == "incomplete"
    assert cov.reason is not None and "production" in cov.reason.lower()
    # No findings and nothing sent.
    assert result.findings == ()
    assert fake.called is False


# --------------------------------------------------------------------------- #
# No pattern configured → never refused, always proceeds
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=100)
@given(target_url=st.one_of(_matching_url(), _non_matching_url()))
def test_absent_pattern_never_refuses(target_url: str) -> None:
    """Validates: Requirements 14.2, 14.3

    With no production pattern configured, no target is classified as production, so the
    scan proceeds and drives the seam whatever the URL looks like.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(pattern=None), fake=fake)

    adapter.scan(_scope(target_url))

    assert fake.called is True


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_prod_host_is_refused() -> None:
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(pattern=_PROD_PATTERN), fake=fake)
    with pytest.raises(ScannerError):
        adapter.scan(_scope("https://api.prod.example.com/api"))
    assert fake.called is False


def test_example_staging_host_proceeds() -> None:
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(pattern=_PROD_PATTERN), fake=fake)
    adapter.scan(_scope("https://staging.example.com/api"))
    assert fake.called is True


def test_example_empty_pattern_proceeds() -> None:
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(pattern=""), fake=fake)
    adapter.scan(_scope("https://api.prod.example.com/api"))
    assert fake.called is True
