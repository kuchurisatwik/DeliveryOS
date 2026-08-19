# Feature: dast-schemathesis, Task 4.11: scan edge cases and run-stats parsing
"""Example-based unit tests for ``SchemathesisAdapter.scan`` edge cases.

These cover the corners of ``scan`` / ``_build_command`` / ``_run_statistics`` that the
property tests do not pin to concrete outcomes:

* **Anonymous run** — when ``DastScope.auth_header`` is unset, no ``--header`` flag is
  emitted and no ``Authorization`` value appears in the argv or the subprocess
  environment (Req 2.4).
* **Proxy off** — when the ZAP host/port are absent, no ``--request-proxy`` flag is
  emitted and neither ``HTTP_PROXY`` nor ``HTTPS_PROXY`` is exported (Req 3.2).
* **Bad seed on fast** — a missing or non-integer seed on the fast profile is a hard
  failure: a ``ScannerError`` is raised and nothing is ever sent (Req 4.4).
* **Deep is unseeded** — a deep-profile run omits ``--hypothesis-seed`` even when a
  seed is configured (Req 4.2).
* **Production refusal** — a target matching the production pattern sends zero requests
  and raises a ``ScannerError`` (Req 14.3).
* **Run-stats parsing** — ``requests_made`` / ``request_errors`` / ``timeouts`` are
  read from Schemathesis's own run statistics (the saved fixture), never from the
  generated-case count (Req 11.4).

Every test drives the command-builder + ``_run`` seam through the in-memory fake in
``tests/dast/_schemathesis_fakes.py`` — no subprocess, no network. The proxy is left
unconfigured (except where a test configures it) so the reachability probe never runs.

**Validates: Requirements 2.4, 3.2, 4.2, 4.4, 11.4, 14.3**
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.security.detection.adapters.base import ScannerError
from dast.models import DastScope
from tests.dast._schemathesis_fakes import (
    FakeSchemathesisRun,
    load_run_stats_fixture,
    make_adapter,
    make_report,
    make_stats,
)


# --------------------------------------------------------------------------- #
# Settings / scope helpers — only the knobs scan() reads on these paths.
# --------------------------------------------------------------------------- #
def _make_settings(
    *,
    prod_pattern: object = None,
    seed: object = 0,
    schema_file: object = "/tmp/openapi.json",
    zap_host: object = None,
    zap_port: object = None,
    rate_limit: object = 10,
) -> SimpleNamespace:
    """A minimal ``DastSettings`` stand-in for the ``scan()`` edge-case paths.

    A file schema keeps ``_schema_source`` local (no ``--wait-for-schema`` window and
    no network). The proxy is unconfigured by default so ``_check_proxy_reachable`` is
    never invoked.
    """
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=prod_pattern,
        DAST_SCHEMATHESIS_SEED=seed,
        DAST_SCHEMATHESIS_SCHEMA_FILE=schema_file,
        DAST_OPENAPI_PATH="/openapi.json",
        DAST_ZAP_HOST=zap_host,
        DAST_ZAP_PORT=zap_port,
        DAST_SCHEMATHESIS_RATE_LIMIT=rate_limit,
        DAST_SCHEMATHESIS_CONNECT_TIMEOUT=30,
        DAST_SCHEMATHESIS_SCHEMA_TIMEOUT=30,
        DAST_SCHEMATHESIS_TIMEOUT=900,
        DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT=5,
    )


def _scope(*, auth_header: object = None, profile: str = "fast") -> DastScope:
    return DastScope(
        target_url="http://target.internal",
        auth_header=auth_header,  # type: ignore[arg-type]
        profile=profile,
    )


# --------------------------------------------------------------------------- #
# Req 2.4 — anonymous run: no --header, no Authorization anywhere
# --------------------------------------------------------------------------- #
def test_anonymous_run_emits_no_auth_header_and_no_auth_env() -> None:
    """Validates: Requirements 2.4

    With ``auth_header`` unset the CLI carries no ``--header`` flag, no ``Authorization``
    token appears anywhere in the argv, and no ``Authorization`` value is exported into
    the subprocess environment.
    """
    fake = FakeSchemathesisRun()  # returncode 0, empty report → clean completion
    adapter = make_adapter(settings=_make_settings(), fake=fake)

    adapter.scan(_scope(auth_header=None))

    run = fake.last
    assert run.header is None
    assert run.headers == []
    assert not run.has_flag("--header")
    # No Authorization token smuggled into the argv or the environment.
    assert not any("Authorization" in token for token in run.argv)
    assert not any("Authorization" in key for key in run.env)


def test_authenticated_run_attaches_the_auth_header() -> None:
    """Validates: Requirements 2.4

    Contrast case: when ``auth_header`` is set, exactly one ``--header`` carries the
    verbatim ``Authorization`` value.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(), fake=fake)

    adapter.scan(_scope(auth_header="Bearer staging-token-xyz"))

    assert fake.last.headers == ["Authorization: Bearer staging-token-xyz"]


# --------------------------------------------------------------------------- #
# Req 3.2 — proxy off when host/port absent: no --request-proxy, no HTTP_PROXY
# --------------------------------------------------------------------------- #
def test_proxy_unconfigured_emits_no_proxy_flag_or_env() -> None:
    """Validates: Requirements 3.2

    With neither ZAP host nor port configured the proxy is treated as absent: no
    ``--request-proxy`` flag and no ``HTTP_PROXY`` / ``HTTPS_PROXY`` in the environment.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(
        settings=_make_settings(zap_host=None, zap_port=None), fake=fake
    )

    adapter.scan(_scope())

    run = fake.last
    assert not run.has_flag("--request-proxy")
    assert run.request_proxy is None
    assert run.http_proxy is None
    assert run.https_proxy is None


def test_proxy_off_when_host_present_but_port_empty() -> None:
    """Validates: Requirements 3.2

    A host with an absent/empty port is still "not configured": no proxy flag or env.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(
        settings=_make_settings(zap_host="127.0.0.1", zap_port=""), fake=fake
    )

    adapter.scan(_scope())

    run = fake.last
    assert not run.has_flag("--request-proxy")
    assert run.http_proxy is None
    assert run.https_proxy is None


# --------------------------------------------------------------------------- #
# Req 4.4 — empty/invalid seed on fast is a hard failure that sends nothing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad_seed", [None, "", "not-an-int", True])
def test_invalid_seed_on_fast_raises_and_sends_nothing(bad_seed: object) -> None:
    """Validates: Requirements 4.4

    On the fast profile a missing or non-integer seed refuses the non-reproducible run:
    a ``ScannerError`` is raised and the ``_run`` seam is never reached, so no request
    is sent.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(seed=bad_seed), fake=fake)

    with pytest.raises(ScannerError) as excinfo:
        adapter.scan(_scope(profile="fast"))

    assert excinfo.value.scanner == "schemathesis"
    assert "seed" in excinfo.value.reason.lower()
    assert not fake.called  # nothing was ever sent


# --------------------------------------------------------------------------- #
# Req 4.2 — deep runs unseeded even when a seed is configured
# --------------------------------------------------------------------------- #
def test_deep_profile_runs_without_a_seed() -> None:
    """Validates: Requirements 4.2

    A deep-profile run omits ``--hypothesis-seed`` so each run explores fresh cases,
    even though a fixed seed is configured.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(seed=0), fake=fake)

    adapter.scan(_scope(profile="deep"))

    run = fake.last
    assert run.seed is None
    assert not run.has_flag("--hypothesis-seed")


def test_deep_profile_ignores_an_invalid_seed_and_still_runs() -> None:
    """Validates: Requirements 4.2

    Deep never reads the seed, so even a garbage seed value does not make it a hard
    failure — the run proceeds, unseeded.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_make_settings(seed="garbage"), fake=fake)

    adapter.scan(_scope(profile="deep"))

    assert fake.called
    assert fake.last.seed is None


# --------------------------------------------------------------------------- #
# Req 14.3 — production refusal sends nothing and raises
# --------------------------------------------------------------------------- #
def test_production_target_refused_sends_nothing_and_raises() -> None:
    """Validates: Requirements 14.3

    A target matching the configured production pattern is refused before any work:
    zero requests, and a ``ScannerError`` whose reason states the scan was refused.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(
        settings=_make_settings(prod_pattern=r"target\.internal"), fake=fake
    )

    with pytest.raises(ScannerError) as excinfo:
        adapter.scan(_scope())

    assert excinfo.value.scanner == "schemathesis"
    assert "refused" in excinfo.value.reason.lower()
    assert not fake.called  # nothing was ever sent


def test_non_production_target_is_not_refused() -> None:
    """Validates: Requirements 14.3

    A pattern that does not match the target does not refuse the run.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(
        settings=_make_settings(prod_pattern=r"prod\.example\.com"), fake=fake
    )

    adapter.scan(_scope())

    assert fake.called


# --------------------------------------------------------------------------- #
# Req 11.4 — run stats come from requests reached, never the generated-case count
# --------------------------------------------------------------------------- #
def test_run_statistics_read_from_fixture_not_case_count() -> None:
    """Validates: Requirements 11.4

    Driving ``scan()`` with the saved run-stats fixture as the report, the returned
    ToolActivity carries ``requests_made`` / ``request_errors`` / ``timeouts`` taken
    from the fixture's ``statistics`` block — NOT the ``generated_cases`` count, which
    the fixture deliberately sets far higher than ``requests_made``.
    """
    fixture = load_run_stats_fixture()
    stats = fixture["statistics"]
    generated_cases = fixture["generated_cases"]
    # The fixture is built so a case-counting parser would over-report reach.
    assert generated_cases > stats["requests_made"]

    fake = FakeSchemathesisRun(report=fixture)
    adapter = make_adapter(settings=_make_settings(), fake=fake)

    outcome = adapter.scan(_scope())

    activity = outcome.activity
    assert activity.requests_made == stats["requests_made"] == 4791
    assert activity.request_errors == stats["request_errors"] == 12
    assert activity.timeouts == stats["timeouts"] == 3
    # The evidence is not the generated-case count.
    assert activity.requests_made != generated_cases


def test_run_statistics_ignore_case_count_when_stats_present() -> None:
    """Validates: Requirements 11.4

    Even with many generated cases in the report body, ``requests_made`` is read from
    the statistics block, not the number of cases.
    """
    # 20 cases in the report, but the stats say only 7 requests actually reached.
    report = make_report(
        cases=[
            {"method": "GET", "path": f"/p{i}", "checks": []}
            for i in range(20)
        ],
        stats=make_stats(requests_made=7, request_errors=1, timeouts=0, generated_cases=20),
    )

    fake = FakeSchemathesisRun(report=report)
    adapter = make_adapter(settings=_make_settings(), fake=fake)

    outcome = adapter.scan(_scope())

    assert outcome.activity.requests_made == 7
    assert outcome.activity.request_errors == 1
