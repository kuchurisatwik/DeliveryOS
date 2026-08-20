# Feature: dast-schemathesis, Property 6: an unauthenticated 2xx on a secured operation becomes a finding
"""Property 6 — an unauthenticated 2xx on a secured operation becomes a finding.

*For any* generated case whose ``ignored_auth`` check FAILED, exactly one
unauthenticated-access ``Finding`` is produced, carrying the endpoint location and the
observed response status; that finding reflects broken access control.

The chain under test is :meth:`SchemathesisAdapter.parse`, a pure classmethod over a
decoded Schemathesis report (no binary, no network, no target). The load-bearing fact
that makes this property checkable at the ``parse`` layer:

    Schemathesis's ``ignored_auth`` check FAILS exactly when an operation that declares
    a security requirement answered ``2xx`` with the auth omitted — i.e. broken access
    control (Req 6.1). So an "unauthenticated 2xx on a secured operation" is represented
    in the report as a case whose ``ignored_auth`` check FAILED. ``parse`` emits exactly
    one access-control finding for such a case, carrying the endpoint location and the
    observed status (Req 6.2).

The access-control finding is located by method + templatised path, which we recompute
independently via ``endpoint_identity`` to avoid asserting against ``parse``'s own
output shape.

**Validates: Requirements 6.1, 6.2**
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.models import Severity
from dast.adapters.schemathesis_adapter import _IGNORED_AUTH_CHECK, SchemathesisAdapter
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

# A 2xx status: the 200–299 range Req 6.1 speaks about — an operation that answered
# successfully without authentication.
_success_status = st.integers(min_value=200, max_value=299)


def _unauth_findings(findings):
    """The subset of findings that are unauthenticated-access findings.

    parse() tags every access-control finding with a ``rule_id`` of
    ``ignored_auth:{METHOD path}:{status}`` (the ``_KIND_IGNORED_AUTH`` prefix), so the
    prefix is the stable, kind-specific selector.
    """
    return [f for f in findings if f.rule_id.startswith("ignored_auth:")]


# --------------------------------------------------------------------------- #
# Property 6 — an unauthenticated 2xx on a secured operation -> one finding
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(method=_http_methods, path=_paths, status=_success_status)
def test_unauthenticated_2xx_becomes_one_access_control_finding(method, path, status):
    """Validates: Requirements 6.1, 6.2

    A 2xx whose ``ignored_auth`` check FAILED (a secured operation answered without
    authentication) yields exactly one access-control ``Finding`` located at the method
    + templatised path of the responsible operation, carrying the observed status.
    """
    case = make_case(
        method=method,
        path=path,
        status_code=status,
        failed_checks=[_IGNORED_AUTH_CHECK],
    )
    findings = SchemathesisAdapter.parse(make_report(cases=[case]))

    unauth = _unauth_findings(findings)
    assert len(unauth) == 1

    finding = unauth[0]
    # Broken access control is treated as HIGH severity (Req 6.2).
    assert finding.severity is Severity.HIGH
    # Located at method + templatised path (Req 6.2). Recomputed independently.
    expected_path = f"{method.upper()} {endpoint_identity(case['request']['uri'])}"
    assert finding.location.path == expected_path
    # The observed response status rides in the stable rule id (Req 6.2).
    assert finding.rule_id == f"ignored_auth:{expected_path}:{status}"
    # The observed status is carried in the human-readable message too.
    assert str(status) in finding.message


# --------------------------------------------------------------------------- #
# Property 6 — combined over a mixed report
# --------------------------------------------------------------------------- #
@st.composite
def _mixed_auth_case(draw):
    """One 2xx case tagged either failed (ignored_auth) or clean (auth honoured).

    Returns ``(case, is_unauth)`` so the test can count the expected number of
    access-control findings without re-deriving parse()'s logic.
    """
    method = draw(_http_methods)
    path = draw(_paths)
    status = draw(_success_status)
    is_unauth = draw(st.booleans())
    if is_unauth:
        case = make_case(
            method=method,
            path=path,
            status_code=status,
            failed_checks=[_IGNORED_AUTH_CHECK],
        )
    else:
        case = make_case(
            method=method,
            path=path,
            status_code=status,
            passed_checks=[_IGNORED_AUTH_CHECK],
        )
    return case, is_unauth


@settings(max_examples=200)
@given(specs=st.lists(_mixed_auth_case(), min_size=0, max_size=8))
def test_access_control_findings_produced_exactly_for_failed_ignored_auth(specs):
    """Validates: Requirements 6.1, 6.2

    Over an arbitrary mix of cases whose ``ignored_auth`` check failed or passed, the
    count of access-control findings equals the number of failed-check cases, and every
    one is HIGH severity — nothing more, nothing less.
    """
    cases = [case for case, _ in specs]
    expected_unauth = sum(1 for _, unauth in specs if unauth)

    findings = SchemathesisAdapter.parse(make_report(cases=cases))
    unauth = _unauth_findings(findings)

    assert len(unauth) == expected_unauth
    assert all(f.severity is Severity.HIGH for f in unauth)


# --------------------------------------------------------------------------- #
# Example-based companion (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_unauthenticated_200_on_secured_operation():
    report = make_report(
        cases=[
            # Secured operation answered 200 without auth -> ignored_auth failed -> finding.
            make_case(
                method="get",
                path="/api/account",
                status_code=200,
                failed_checks=[_IGNORED_AUTH_CHECK],
            ),
            # Auth honoured on this operation -> ignored_auth passed -> no finding.
            make_case(
                method="get",
                path="/api/public",
                status_code=200,
                passed_checks=[_IGNORED_AUTH_CHECK],
            ),
        ]
    )

    unauth = _unauth_findings(SchemathesisAdapter.parse(report))

    assert len(unauth) == 1
    finding = unauth[0]
    assert finding.severity is Severity.HIGH
    assert finding.location.path == "GET /api/account"
    assert finding.rule_id == "ignored_auth:GET /api/account:200"
    assert "200" in finding.message
