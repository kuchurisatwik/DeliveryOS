# Feature: dast-schemathesis, Property 5: undeclared 5xx becomes a high-severity finding; declared 5xx does not
"""Property 5 — undeclared 5xx becomes a high-severity finding; declared 5xx does not.

*For any* generated case, an unhandled server-error ``Finding`` with severity ``HIGH``
is produced exactly when the response status is in 500–599 **and** that status is not a
declared response for the invoked operation; a 5xx that the schema declares for the
operation produces no such finding.

The chain under test is :meth:`SchemathesisAdapter.parse`, a pure classmethod over a
decoded Schemathesis report (no binary, no network, no target). The load-bearing fact
that makes this property checkable at the ``parse`` layer:

    A *failed* ``not_a_server_error`` check is, by Schemathesis's own definition, an
    **undeclared** 5xx — a 5xx the schema *declares* for the operation never fails that
    check. So "undeclared 5xx" is represented in the report as a case whose
    ``not_a_server_error`` check FAILED, and "declared 5xx" as a 5xx case whose
    ``not_a_server_error`` check is present and PASSED (never fails). ``parse`` emits a
    HIGH-severity server-error finding exactly for the former.

The server-error finding is located by method + templatised path (Req 5.3), which we
recompute independently via ``endpoint_identity`` to avoid asserting against ``parse``'s
own output shape.

**Validates: Requirements 5.1, 5.2, 5.3**
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.models import Severity
from dast.adapters.schemathesis_adapter import _SERVER_ERROR_CHECK, SchemathesisAdapter
from dast.urls import endpoint_identity

from tests.dast._schemathesis_fakes import make_case, make_report

# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
_http_methods = st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"])

# Route-name segments only (lowercase letters): a literal segment can never look like a
# dynamic identifier and be templatised by the heuristic, so the endpoint identity we
# recompute matches parse()'s exactly.
_route_segment = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
_paths = st.lists(_route_segment, min_size=1, max_size=4).map(
    lambda segs: "/" + "/".join(segs)
)

# A server-error status: the 500–599 range Req 5.1/5.2 speak about.
_server_error_status = st.integers(min_value=500, max_value=599)

# A non-5xx status a declared/undeclared case might also carry (used only in the mixed
# report to add non-server-error noise the property must ignore).
_non_server_status = st.integers(min_value=100, max_value=499)


def _server_error_findings(findings):
    """The subset of findings that are unhandled-server-error findings.

    parse() tags every server-error finding with a ``rule_id`` of
    ``server_error:{METHOD path}:{status}`` (the ``_KIND_SERVER_ERROR`` prefix), so the
    prefix is the stable, kind-specific selector.
    """
    return [f for f in findings if f.rule_id.startswith("server_error:")]


# --------------------------------------------------------------------------- #
# Property 5 — the "exactly when" direction (undeclared 5xx -> HIGH finding)
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(method=_http_methods, path=_paths, status=_server_error_status)
def test_undeclared_5xx_becomes_one_high_severity_server_error_finding(method, path, status):
    """Validates: Requirements 5.1, 5.3

    A 5xx whose ``not_a_server_error`` check FAILED (an undeclared server error) yields
    exactly one server-error ``Finding`` with severity ``HIGH`` located at the method +
    templatised path of the responsible operation.
    """
    case = make_case(
        method=method,
        path=path,
        status_code=status,
        failed_checks=[_SERVER_ERROR_CHECK],
    )
    findings = SchemathesisAdapter.parse(make_report(cases=[case]))

    server_errors = _server_error_findings(findings)
    assert len(server_errors) == 1

    finding = server_errors[0]
    # Undeclared 5xx is HIGH (Req 5.3).
    assert finding.severity is Severity.HIGH
    # Located at method + templatised path (Req 5.3). Recomputed independently.
    expected_path = f"{method.upper()} {endpoint_identity(case['request']['uri'])}"
    assert finding.location.path == expected_path
    # The observed status rides in the stable rule id.
    assert finding.rule_id == f"server_error:{expected_path}:{status}"


# --------------------------------------------------------------------------- #
# Property 5 — the other direction (declared 5xx -> no finding)
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(method=_http_methods, path=_paths, status=_server_error_status)
def test_declared_5xx_produces_no_server_error_finding(method, path, status):
    """Validates: Requirements 5.2

    A 5xx the schema declares for the operation never fails ``not_a_server_error``, so
    it is represented as a case whose ``not_a_server_error`` check PASSED — and parse()
    must produce no server-error finding for it.
    """
    case = make_case(
        method=method,
        path=path,
        status_code=status,
        passed_checks=[_SERVER_ERROR_CHECK],
    )
    findings = SchemathesisAdapter.parse(make_report(cases=[case]))

    assert _server_error_findings(findings) == []


# --------------------------------------------------------------------------- #
# Property 5 — combined "exactly when" over a mixed report
# --------------------------------------------------------------------------- #
@st.composite
def _mixed_5xx_case(draw):
    """One 5xx case tagged either undeclared (check failed) or declared (check passed).

    Returns ``(case, is_undeclared)`` so the test can count the expected number of
    server-error findings without re-deriving parse()'s logic.
    """
    method = draw(_http_methods)
    path = draw(_paths)
    status = draw(_server_error_status)
    is_undeclared = draw(st.booleans())
    if is_undeclared:
        case = make_case(
            method=method,
            path=path,
            status_code=status,
            failed_checks=[_SERVER_ERROR_CHECK],
        )
    else:
        case = make_case(
            method=method,
            path=path,
            status_code=status,
            passed_checks=[_SERVER_ERROR_CHECK],
        )
    return case, is_undeclared


@settings(max_examples=200)
@given(specs=st.lists(_mixed_5xx_case(), min_size=0, max_size=8))
def test_server_error_findings_produced_exactly_for_undeclared_cases(specs):
    """Validates: Requirements 5.1, 5.2, 5.3

    Over an arbitrary mix of declared and undeclared 5xx cases, the count of
    server-error findings equals the number of undeclared cases (a failed
    ``not_a_server_error`` check), and every one is HIGH severity — nothing more,
    nothing less.
    """
    cases = [case for case, _ in specs]
    expected_undeclared = sum(1 for _, undeclared in specs if undeclared)

    findings = SchemathesisAdapter.parse(make_report(cases=cases))
    server_errors = _server_error_findings(findings)

    assert len(server_errors) == expected_undeclared
    assert all(f.severity is Severity.HIGH for f in server_errors)


# --------------------------------------------------------------------------- #
# Example-based companion (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_undeclared_500_high_declared_503_silent():
    report = make_report(
        cases=[
            # Undeclared: the schema did not declare a 500 here -> check failed -> HIGH.
            make_case(
                method="post",
                path="/api/orders",
                status_code=500,
                failed_checks=[_SERVER_ERROR_CHECK],
            ),
            # Declared: the schema declares this 503 -> check passed -> no finding.
            make_case(
                method="get",
                path="/api/health",
                status_code=503,
                passed_checks=[_SERVER_ERROR_CHECK],
            ),
        ]
    )

    server_errors = _server_error_findings(SchemathesisAdapter.parse(report))

    assert len(server_errors) == 1
    finding = server_errors[0]
    assert finding.severity is Severity.HIGH
    assert finding.location.path == "POST /api/orders"
    assert finding.rule_id == "server_error:POST /api/orders:500"
