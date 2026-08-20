# Feature: dast-schemathesis, Property 13: request evidence, not generated-case count, drives complete/incomplete
"""Property 13 — request evidence, not the generated-case count, drives
complete/incomplete.

**Validates: Requirements 11.2, 11.3, 11.4, 13.5**

Schemathesis is part of the *fast* profile that runs on every deploy, so its coverage
verdict feeds the same liveness/trust model that keeps "zero findings" honest. The
single most important trust rule is that the verdict is decided by **request evidence
Schemathesis actually gathered** — the count of requests that reached the target and
came back — never by how many test cases it *generated*. A run that generated 50,000
cases but resolved no DNS sent zero requests, and reporting that as "clean" is exactly
the failure mode the whole service exists to avoid.

The evidence lives in ``ToolActivity`` (``requests_made``, ``request_errors``,
``timeouts``), which the adapter fills from Schemathesis's OWN run statistics (Req
11.4). The runner's :func:`dast.runner._assess_activity` then classifies it:

* ``requests_made == 0`` → ``incomplete`` — the target was never contacted (Req 11.2);
* ``requests_made > 0`` and ``request_errors >= requests_made`` → ``incomplete`` —
  every request failed at the transport level (Req 11.3);
* a flood of timeouts (``timeouts > max(10, units_executed * 0.05)``) → ``incomplete``
  — the target was overwhelmed and the checks that timed out silently tested nothing
  (Req 13.5); and
* honest evidence of delivered, answered requests → ``complete``.

The first three requirements are checked end-to-end through ``run_scan(scope,
[adapter])`` against the *real* :class:`SchemathesisAdapter`, using the in-memory fake
in ``tests/dast/_schemathesis_fakes.py`` to inject a report + run-statistics with no
subprocess and no network — the same seam the sibling property tests use. The report's
``generated_cases`` count is deliberately driven to huge, arbitrary values to prove it
never moves the verdict (Req 11.4). Requirement 13.5's timeout-flood rule is checked
directly against the runner's classifier ``_assess_activity`` (the runner is shared and
owns that rule), since the timeout branch is keyed on ``units_executed``.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from dast.models import DastScope, ScanOutcome, ToolActivity
from dast.runner import _assess_activity, run_scan
from tests.dast._schemathesis_fakes import (
    FakeSchemathesisRun,
    make_adapter,
    make_report,
    make_stats,
)


# --------------------------------------------------------------------------- #
# Stub settings — only the knobs scan() reads on this path. The proxy is left
# unconfigured so no reachability probe runs, a file schema keeps _schema_source
# local, and a fixed integer seed keeps the default fast profile off the
# hard-failure path so the run reaches _assess_activity.
# --------------------------------------------------------------------------- #
def _make_settings() -> SimpleNamespace:
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


def _scope() -> DastScope:
    return DastScope(target_url="http://target.internal", profile="fast")


def _classify_via_runner(
    *,
    requests_made: int,
    request_errors: int = 0,
    timeouts: int = 0,
    generated_cases: int | None = None,
    returncode: int = 0,
) -> tuple[str, str | None]:
    """Drive one scan through the real adapter + faked seam and return its coverage.

    The fake writes a report whose ``statistics`` block carries exactly these request
    counts (and, optionally, a ``generated_cases`` count), so ``scan()`` reads real
    request evidence back and the runner classifies it. Returns ``(status, reason)``
    from ``result.coverage[0]``.
    """
    stats = make_stats(
        requests_made=requests_made,
        request_errors=request_errors,
        timeouts=timeouts,
        generated_cases=generated_cases,
    )
    fake = FakeSchemathesisRun(report=make_report(stats=stats), returncode=returncode)
    adapter = make_adapter(settings=_make_settings(), fake=fake)
    result = run_scan(_scope(), [adapter])
    assert len(result.coverage) == 1
    entry = result.coverage[0]
    assert entry.scanner == "schemathesis"
    # The evidence the runner classified is the evidence the adapter reported —
    # read from Schemathesis's stats, never the generated-case count (Req 11.4).
    assert entry.activity.requests_made == requests_made
    return entry.status, entry.reason


#: A generous but bounded space for the honest request-evidence counts.
_COUNT = st.integers(min_value=1, max_value=100_000)
#: Generated-case counts, including values far larger than any request count, to prove
#: the verdict never reads them (Req 11.4).
_GENERATED = st.integers(min_value=0, max_value=50_000_000)


# --------------------------------------------------------------------------- #
# Req 11.2 — zero requests reached the target → incomplete, whatever was generated
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(generated_cases=_GENERATED)
def test_zero_requests_is_incomplete_regardless_of_generated_cases(
    generated_cases: int,
) -> None:
    """Validates: Requirements 11.2, 11.4

    However many cases Schemathesis generated, if none of them reached the target the
    coverage is incomplete — a huge generated-case count cannot rescue a run that sent
    nothing.
    """
    status, reason = _classify_via_runner(
        requests_made=0, request_errors=0, generated_cases=generated_cases
    )
    assert status == "incomplete"
    assert reason is not None and "zero requests" in reason


# --------------------------------------------------------------------------- #
# Req 11.3 — every delivered request failed at the transport level → incomplete
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(
    requests_made=_COUNT,
    extra_errors=st.integers(min_value=0, max_value=1000),
    generated_cases=_GENERATED,
)
def test_all_requests_failed_is_incomplete(
    requests_made: int, extra_errors: int, generated_cases: int
) -> None:
    """Validates: Requirements 11.3, 11.4

    When ``request_errors >= requests_made`` — every request that left the scanner
    failed at the transport level — the run reached the target's door but never got in,
    so the coverage is incomplete no matter how many cases were generated.
    """
    request_errors = requests_made + extra_errors  # >= requests_made
    status, reason = _classify_via_runner(
        requests_made=requests_made,
        request_errors=request_errors,
        generated_cases=generated_cases,
    )
    assert status == "incomplete"
    assert reason is not None and "failed" in reason


# --------------------------------------------------------------------------- #
# Honest evidence of delivered, answered requests → complete
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(
    requests_made=st.integers(min_value=2, max_value=100_000),
    generated_cases=_GENERATED,
)
def test_healthy_request_evidence_is_complete(
    requests_made: int, generated_cases: int
) -> None:
    """Validates: Requirements 11.3, 11.4

    Requests that were delivered and answered, with no error/timeout flood, are real
    evidence the app was tested — so the coverage is complete. The generated-case
    count (here driven far larger than the request count) never changes that.
    """
    status, reason = _classify_via_runner(
        requests_made=requests_made,
        request_errors=0,
        timeouts=0,
        generated_cases=generated_cases,
    )
    assert status == "complete"
    assert reason is None


# --------------------------------------------------------------------------- #
# Req 11.4 — the generated-case count NEVER changes the verdict
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(
    requests_made=st.integers(min_value=2, max_value=100_000),
    generated_a=_GENERATED,
    generated_b=_GENERATED,
)
def test_generated_case_count_does_not_move_the_verdict(
    requests_made: int, generated_a: int, generated_b: int
) -> None:
    """Validates: Requirements 11.4

    Holding the request evidence fixed while varying the generated-case count across
    two arbitrary values yields the identical verdict — proving the classification is
    a function of requests reached, not cases generated.
    """
    verdict_a = _classify_via_runner(
        requests_made=requests_made, request_errors=0, generated_cases=generated_a
    )
    verdict_b = _classify_via_runner(
        requests_made=requests_made, request_errors=0, generated_cases=generated_b
    )
    assert verdict_a == verdict_b


# --------------------------------------------------------------------------- #
# Req 13.5 — a flood of timeouts marks the coverage incomplete
# --------------------------------------------------------------------------- #
# The runner's timeout rule is keyed on units_executed
# (``timeouts > max(10, units_executed * 0.05)``), so it is exercised directly against
# the shared classifier that owns it. requests_made > 0 and low request_errors keep the
# earlier branches from firing, isolating the timeout rule.
def _timeout_threshold(units_executed: int) -> float:
    return max(10.0, units_executed * 0.05)


@hyp_settings(max_examples=200)
@given(
    units_executed=st.integers(min_value=1, max_value=200_000),
    requests_made=st.integers(min_value=1, max_value=100_000),
    over=st.integers(min_value=1, max_value=5000),
)
def test_timeout_flood_is_incomplete(
    units_executed: int, requests_made: int, over: int
) -> None:
    """Validates: Requirements 13.5

    A timeout count above ``max(10, units_executed * 0.05)`` means the target was
    overwhelmed and the checks that timed out tested nothing, so the coverage is
    incomplete even though requests were made and few failed at the transport level.
    """
    timeouts = int(math.ceil(_timeout_threshold(units_executed))) + over
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(
            units_executed=units_executed,
            requests_made=requests_made,
            request_errors=0,
            timeouts=timeouts,
        ),
    )
    status, reason = _assess_activity("schemathesis", outcome)
    assert status == "incomplete"
    assert reason is not None and "timeout" in reason


@hyp_settings(max_examples=200)
@given(
    units_executed=st.integers(min_value=1, max_value=200_000),
    requests_made=st.integers(min_value=2, max_value=100_000),
    data=st.data(),
)
def test_timeouts_within_tolerance_stay_complete(
    units_executed: int, requests_made: int, data: st.DataObject
) -> None:
    """Validates: Requirements 13.5

    The complement of the flood rule: a handful of timeouts at or below the tolerance
    does not, on its own, condemn an otherwise-healthy run — it stays complete.
    """
    ceiling = int(math.floor(_timeout_threshold(units_executed)))
    timeouts = data.draw(st.integers(min_value=0, max_value=ceiling))
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(
            units_executed=units_executed,
            requests_made=requests_made,
            request_errors=0,
            timeouts=timeouts,
        ),
    )
    status, reason = _assess_activity("schemathesis", outcome)
    assert status == "complete"
    assert reason is None


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_fifty_thousand_generated_zero_reached_is_incomplete() -> None:
    """Req 11.2, 11.4 — the headline case: many cases generated, none delivered."""
    status, reason = _classify_via_runner(
        requests_made=0, request_errors=0, generated_cases=50_000
    )
    assert status == "incomplete"
    assert reason is not None and "zero requests" in reason


def test_example_healthy_run_is_complete() -> None:
    """A normal fast-profile run with delivered traffic is complete."""
    status, reason = _classify_via_runner(
        requests_made=4791, request_errors=3, timeouts=0, generated_cases=6000
    )
    assert status == "complete"
    assert reason is None


def test_example_all_transport_errors_is_incomplete() -> None:
    """Req 11.3 — a run where every delivered request failed is incomplete."""
    status, reason = _classify_via_runner(
        requests_made=120, request_errors=120, generated_cases=9000
    )
    assert status == "incomplete"
    assert reason is not None and "failed" in reason


def test_example_timeout_flood_is_incomplete() -> None:
    """Req 13.5 — a flood of timeouts over the tolerance marks coverage incomplete."""
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(
            units_executed=100, requests_made=100, request_errors=0, timeouts=80
        ),
    )
    status, reason = _assess_activity("schemathesis", outcome)
    assert status == "incomplete"
    assert reason is not None and "timeout" in reason
