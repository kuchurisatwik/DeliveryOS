"""Property 6: Scanner-failure containment (security-pipeline).

Exercises :class:`app.security.detection.runner.DetectionStage` with N in-memory
fake scanner adapters. Hypothesis chooses, per adapter, whether it succeeds or
fails (via a ``ScannerError`` or an unexpected non-``ScannerError`` exception),
covering the empty failing subset (no scanner fails) and the all-fail subset.

The property asserts that:
- findings from every non-failing scanner are retained (aggregated as the
  multiset union of their per-scanner lists), and failing scanners contribute
  none, and
- a scanner's coverage is marked ``incomplete`` if and only if that scanner is
  in the failing subset (``complete`` otherwise).

Validates: Requirements 3.4
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.detection.adapters import ScannerError
from app.security.detection.runner import DetectionStage
from app.security.models import Finding
from app.workflows.context import WorkflowContext
from tests.security.strategies import findings


# --------------------------------------------------------------------------- #
# Fakes + helpers
# --------------------------------------------------------------------------- #

# Failure modes an adapter can exhibit. "ok" succeeds; the other two are the two
# distinct failure paths the runner must isolate (a well-defined ScannerError and
# an unexpected exception).
_FAIL_MODES = ("ok", "scanner_error", "unexpected")


class _FakeAdapter:
    """An in-memory ScannerAdapter that either returns findings or fails."""

    def __init__(self, name: str, fail_mode: str, scanner_findings: list[Finding]) -> None:
        self.name = name
        self._fail_mode = fail_mode
        self._findings = scanner_findings

    def scan(self, scope: Any) -> list[Finding]:
        if self._fail_mode == "scanner_error":
            raise ScannerError(self.name, "injected scanner failure")
        if self._fail_mode == "unexpected":
            raise ValueError("injected unexpected failure")
        return list(self._findings)


def _make_context() -> WorkflowContext:
    """A minimal WorkflowContext; the scope is irrelevant to failure isolation."""

    return WorkflowContext(
        repository="owner/repo",
        repo_name="repo",
        clone_url="https://example.invalid/owner/repo.git",
        branch="main",
        commit_sha="deadbeef",
    )


def _finding_key(f: Finding) -> str:
    """A stable, sortable, order-independent key for a Finding (multiset compare)."""

    return repr(
        (
            f.scanner,
            f.rule_id,
            f.location.path,
            f.location.start_line,
            f.location.end_line,
            f.location.symbol,
            f.severity.name,
            f.message,
            tuple(sorted(f.raw.items(), key=lambda kv: kv[0])),
        )
    )


def _multiset(items: Any) -> list[str]:
    return sorted(_finding_key(f) for f in items)


@st.composite
def scanner_specs(draw: st.DrawFn) -> list[dict[str, Any]]:
    """A list of per-scanner specs: failure mode + findings to emit on success."""

    n = draw(st.integers(min_value=1, max_value=6))
    specs: list[dict[str, Any]] = []
    for i in range(n):
        specs.append(
            {
                "name": f"scanner_{i}",
                "fail_mode": draw(st.sampled_from(_FAIL_MODES)),
                "findings": draw(st.lists(findings(), max_size=4)),
            }
        )
    return specs


# --------------------------------------------------------------------------- #
# Property
# --------------------------------------------------------------------------- #


# Feature: security-pipeline, Property 6: For any subset of scanners chosen to fail, findings from every non-failing scanner are retained, and a scanner's coverage is marked incomplete if and only if that scanner is in the failing subset.
@settings(max_examples=100)
@given(specs=scanner_specs())
def test_property_06_scanner_failure_containment(specs: list[dict[str, Any]]) -> None:
    adapters = [
        _FakeAdapter(s["name"], s["fail_mode"], s["findings"]) for s in specs
    ]
    failing = {s["name"] for s in specs if s["fail_mode"] != "ok"}

    context = _make_context()
    DetectionStage(adapters=adapters).execute(context)
    result = context.detection_result

    # Coverage covers exactly the adapters, once each.
    coverage_by_name = {c.scanner: c for c in result.coverage}
    assert set(coverage_by_name) == {s["name"] for s in specs}
    assert len(result.coverage) == len(specs)

    # A scanner is incomplete iff it is in the failing subset; complete otherwise.
    for spec in specs:
        cov = coverage_by_name[spec["name"]]
        if spec["name"] in failing:
            assert cov.status == "incomplete"
            assert cov.reason  # a reason is recorded for the failure
        else:
            assert cov.status == "complete"
            assert cov.reason is None

    # Findings equal the multiset union of the non-failing scanners' lists;
    # failing scanners contribute nothing.
    expected: list[Finding] = []
    for spec in specs:
        if spec["name"] not in failing:
            expected.extend(spec["findings"])
    assert _multiset(result.findings) == _multiset(expected)


# --------------------------------------------------------------------------- #
# Explicit edge-case examples (empty subset, all-fail, unexpected exception)
# --------------------------------------------------------------------------- #


def _run_with(adapters: list[_FakeAdapter]):
    context = _make_context()
    DetectionStage(adapters=adapters).execute(context)
    return context.detection_result


def test_empty_failing_subset_retains_all_findings() -> None:
    a = _FakeAdapter("bandit", "ok", [])
    b = _FakeAdapter("semgrep", "ok", [])
    result = _run_with([a, b])

    assert {c.scanner: c.status for c in result.coverage} == {
        "bandit": "complete",
        "semgrep": "complete",
    }


def test_all_scanners_failing_yields_no_findings_all_incomplete() -> None:
    a = _FakeAdapter("bandit", "scanner_error", [])
    b = _FakeAdapter("semgrep", "unexpected", [])
    result = _run_with([a, b])

    assert result.findings == ()
    assert {c.scanner: c.status for c in result.coverage} == {
        "bandit": "incomplete",
        "semgrep": "incomplete",
    }
    assert all(c.reason for c in result.coverage)


def test_unexpected_exception_is_contained_as_incomplete() -> None:
    # A non-ScannerError exception from one adapter must not lose the other's findings.
    failing = _FakeAdapter("codeql", "unexpected", [])
    healthy_findings: list[Finding] = []
    healthy = _FakeAdapter("bandit", "ok", healthy_findings)

    result = _run_with([failing, healthy])

    coverage_by_name = {c.scanner: c for c in result.coverage}
    assert coverage_by_name["codeql"].status == "incomplete"
    assert coverage_by_name["codeql"].reason
    assert coverage_by_name["bandit"].status == "complete"
