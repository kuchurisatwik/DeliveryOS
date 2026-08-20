# Feature: dast-schemathesis, Property 7: a non-conforming response becomes one schema-violation finding enumerating all breaks
"""Property 7 — a non-conforming response becomes one schema-violation finding enumerating all breaks.

*For any* response for an invoked operation, a schema-violation ``Finding`` is produced
exactly when the status code, headers, or body do not conform to the declared contract;
a fully conforming response produces none; and a single response violating multiple
contract elements produces exactly ONE finding whose description enumerates every
violated element.

The chain under test is :meth:`SchemathesisAdapter.parse`, a pure classmethod over a
decoded Schemathesis report (no binary, no network, no target). The load-bearing fact
that makes this property checkable at the ``parse`` layer:

    The four schema-conformance checks Schemathesis runs — ``status_code_conformance``,
    ``content_type_conformance``, ``response_headers_conformance``,
    ``response_schema_conformance`` — each guard one declared contract element. A
    *failed* check means that element did not conform. ``parse`` collapses however many
    of the four failed into a SINGLE ``MEDIUM`` schema-violation finding whose message
    enumerates every violated element in the fixed ``_SCHEMA_CHECK_ORDER``. A response
    where none of the four failed (a fully conforming response) yields no such finding.

The schema-violation finding is selected by its stable ``rule_id`` prefix
(``schema_violation:``, the ``_KIND_SCHEMA_VIOLATION`` kind) so the test does not assert
against ``parse``'s full output shape.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4**
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.models import Severity
from dast.adapters.schemathesis_adapter import (
    _ELEMENT_LABELS,
    _SCHEMA_CHECK_ORDER,
    SchemathesisAdapter,
)

from tests.dast._schemathesis_fakes import make_case, make_report

# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
_http_methods = st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"])

# Route-name segments only (lowercase letters): a literal segment can never be
# templatised by the endpoint heuristic, so the path is stable and free of noise.
_route_segment = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
_paths = st.lists(_route_segment, min_size=1, max_size=4).map(
    lambda segs: "/" + "/".join(segs)
)

_status = st.integers(min_value=200, max_value=599)

# A subset (0–4) of the four schema-conformance checks to mark as FAILED. Drawn as a
# unique-preserving sub-list of the canonical order.
_failed_schema_subset = st.lists(
    st.sampled_from(_SCHEMA_CHECK_ORDER), unique=True, min_size=0, max_size=4
)


def _schema_violation_findings(findings):
    """The subset of findings that are schema-violation findings.

    parse() tags every schema-violation finding with a ``rule_id`` of
    ``schema_violation:{METHOD path}:{status}`` (the ``_KIND_SCHEMA_VIOLATION`` prefix),
    so the prefix is the stable, kind-specific selector.
    """
    return [f for f in findings if f.rule_id.startswith("schema_violation:")]


def _expected_elements(failed_checks) -> list[str]:
    """The element labels parse() must enumerate, in the fixed canonical order."""
    return [
        _ELEMENT_LABELS[name] for name in _SCHEMA_CHECK_ORDER if name in failed_checks
    ]


# --------------------------------------------------------------------------- #
# Property 7 — the "exactly when" direction over an arbitrary failed subset
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(method=_http_methods, path=_paths, status=_status, failed=_failed_schema_subset)
def test_schema_violation_finding_produced_exactly_when_a_check_fails(
    method, path, status, failed
):
    """Validates: Requirements 7.1, 7.2, 7.3, 7.4

    A response yields exactly one MEDIUM schema-violation finding when one or more of
    the four conformance checks failed, and none when they all passed. When produced,
    the single finding's description enumerates every violated element in the fixed
    canonical order.
    """
    passed = [name for name in _SCHEMA_CHECK_ORDER if name not in failed]
    case = make_case(
        method=method,
        path=path,
        status_code=status,
        failed_checks=failed,
        passed_checks=passed,
    )
    findings = SchemathesisAdapter.parse(make_report(cases=[case]))
    violations = _schema_violation_findings(findings)

    if not failed:
        # A fully conforming response produces no schema-violation finding (Req 7.2).
        assert violations == []
        return

    # One or more elements broke -> exactly ONE finding (Req 7.1, 7.4).
    assert len(violations) == 1
    finding = violations[0]

    # A contract violation is MEDIUM (Req 7.3).
    assert finding.severity is Severity.MEDIUM

    # The description enumerates every violated element, in the fixed order (Req 7.3, 7.4).
    expected = _expected_elements(failed)
    positions = []
    for label in expected:
        assert label in finding.message, (
            f"missing element {label!r} in description {finding.message!r}"
        )
        positions.append(finding.message.index(label))
    assert positions == sorted(positions), (
        f"elements not enumerated in canonical order: {finding.message!r}"
    )


# --------------------------------------------------------------------------- #
# Property 7 — multiple broken elements collapse into exactly ONE finding
# --------------------------------------------------------------------------- #
_multi_failed_subset = st.lists(
    st.sampled_from(_SCHEMA_CHECK_ORDER), unique=True, min_size=2, max_size=4
)


@settings(max_examples=200)
@given(method=_http_methods, path=_paths, status=_status, failed=_multi_failed_subset)
def test_multiple_violated_elements_yield_one_enumerating_finding(
    method, path, status, failed
):
    """Validates: Requirements 7.4

    A single response that breaks more than one declared contract element is recorded as
    ONE schema-violation finding whose description enumerates every violated element —
    never one finding per broken element.
    """
    passed = [name for name in _SCHEMA_CHECK_ORDER if name not in failed]
    case = make_case(
        method=method,
        path=path,
        status_code=status,
        failed_checks=failed,
        passed_checks=passed,
    )
    findings = SchemathesisAdapter.parse(make_report(cases=[case]))
    violations = _schema_violation_findings(findings)

    # Exactly one finding for the whole response, regardless of how many elements broke.
    assert len(violations) == 1
    message = violations[0].message
    # Every violated element is named in that single description.
    for label in _expected_elements(failed):
        assert label in message


# --------------------------------------------------------------------------- #
# Property 7 — "exactly when" across a mixed report of conforming/non-conforming cases
# --------------------------------------------------------------------------- #
@st.composite
def _conformance_case(draw):
    """One case with an arbitrary failed subset of the schema checks.

    Returns ``(case, is_violation)`` so the test can count expected findings without
    re-deriving parse()'s collapse logic.
    """
    method = draw(_http_methods)
    path = draw(_paths)
    status = draw(_status)
    failed = draw(_failed_schema_subset)
    passed = [name for name in _SCHEMA_CHECK_ORDER if name not in failed]
    case = make_case(
        method=method,
        path=path,
        status_code=status,
        failed_checks=failed,
        passed_checks=passed,
    )
    return case, bool(failed)


@settings(max_examples=200)
@given(specs=st.lists(_conformance_case(), min_size=0, max_size=8))
def test_schema_violation_count_equals_non_conforming_case_count(specs):
    """Validates: Requirements 7.1, 7.2, 7.4

    Over an arbitrary mix of conforming and non-conforming responses, the number of
    schema-violation findings equals the number of cases with at least one failed
    conformance check (one finding per non-conforming response), and every one is
    MEDIUM severity.
    """
    cases = [case for case, _ in specs]
    expected = sum(1 for _, is_violation in specs if is_violation)

    findings = SchemathesisAdapter.parse(make_report(cases=cases))
    violations = _schema_violation_findings(findings)

    assert len(violations) == expected
    assert all(f.severity is Severity.MEDIUM for f in violations)


# --------------------------------------------------------------------------- #
# Example-based companion (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_status_and_body_break_one_finding_conforming_silent():
    report = make_report(
        cases=[
            # Two elements broke on one response -> ONE finding naming both.
            make_case(
                method="post",
                path="/api/orders",
                status_code=418,
                failed_checks=[
                    "status_code_conformance",
                    "response_schema_conformance",
                ],
                passed_checks=[
                    "content_type_conformance",
                    "response_headers_conformance",
                ],
            ),
            # Fully conforming -> no schema-violation finding.
            make_case(
                method="get",
                path="/api/health",
                status_code=200,
                passed_checks=list(_SCHEMA_CHECK_ORDER),
            ),
        ]
    )

    violations = _schema_violation_findings(SchemathesisAdapter.parse(report))

    assert len(violations) == 1
    finding = violations[0]
    assert finding.severity is Severity.MEDIUM
    assert finding.location.path == "POST /api/orders"
    # Both broken elements are enumerated, status code before response body.
    assert "status code" in finding.message
    assert "response body" in finding.message
    assert finding.message.index("status code") < finding.message.index("response body")
