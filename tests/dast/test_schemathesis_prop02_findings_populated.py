# Feature: dast-schemathesis, Property 2: parsed findings are fully populated with stable identity
"""Property 2: parsed findings are fully populated with stable identity.

**Validates: Requirements 5.4, 9.1**

For any failing case in a well-formed Schemathesis report, the ``Finding`` that
``SchemathesisAdapter.parse`` produces must carry:

* the scanner name ``"schemathesis"`` (Req 9.1),
* a non-empty ``rule_id`` that is identical across runs for the same endpoint and
  failure kind (Req 5.4, 9.1),
* a web ``Location`` (Req 9.1),
* a ``Severity`` drawn from the shared severity scale (Req 9.1), and
* a non-empty message (Req 9.1).

``parse`` is a pure classmethod over a decoded report, so — like the nuclei adapter
tests — these run with no binary, no network, and no target. The report is built
from the shared case/report builders in ``_schemathesis_fakes`` so the shape matches
what the real CLI emits.
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.models import Location, Severity
from dast.adapters.schemathesis_adapter import (
    _IGNORED_AUTH_CHECK,
    _SCHEMA_CHECK_ORDER,
    _SERVER_ERROR_CHECK,
    SchemathesisAdapter,
)

from tests.dast._schemathesis_fakes import make_case, make_report

# Every check name whose failure yields at least one Finding. Drawing a non-empty
# subset guarantees the generated case is a Failing_Case (Req 9.1 talks about a
# Failing_Case), so parse() always produces at least one finding to inspect.
_ALL_FAILING_CHECKS: tuple[str, ...] = (
    _SERVER_ERROR_CHECK,
    _IGNORED_AUTH_CHECK,
    *_SCHEMA_CHECK_ORDER,
)

# The full, shared severity scale a finding's severity must be drawn from (Req 9.1).
_SHARED_SEVERITY_SCALE = frozenset(Severity)


# --------------------------------------------------------------------------- #
# Strategies — a well-formed report of one or more failing cases
# --------------------------------------------------------------------------- #
_http_methods = st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"])

# A path segment is either a route name (letters) or a numeric/hex id — the mix the
# endpoint-identity normaliser is built to templatise.
_route_segment = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
_id_segment = st.integers(min_value=0, max_value=99_999).map(str)
_segment = st.one_of(_route_segment, _id_segment)

_paths = st.lists(_segment, min_size=0, max_size=5).map(
    lambda segs: "/" + "/".join(segs)
)

# Any HTTP status; the finding kinds do not require a particular value here, and the
# rule_id must be populated regardless of the observed status.
_status_codes = st.integers(min_value=100, max_value=599)

# A non-empty, de-duplicated subset of the failing checks -> at least one finding.
_failed_checks = st.lists(
    st.sampled_from(_ALL_FAILING_CHECKS), min_size=1, max_size=len(_ALL_FAILING_CHECKS)
).map(lambda names: sorted(set(names)))


@st.composite
def _failing_case(draw):
    """One well-formed Schemathesis case carrying at least one failed check."""
    return make_case(
        method=draw(_http_methods),
        path=draw(_paths),
        status_code=draw(_status_codes),
        failed_checks=draw(_failed_checks),
    )


@st.composite
def _report(draw):
    """A well-formed report of one or more failing cases."""
    cases = draw(st.lists(_failing_case(), min_size=1, max_size=6))
    return make_report(cases=cases)


# --------------------------------------------------------------------------- #
# Property 2
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(report=_report())
def test_parsed_findings_are_fully_populated_with_stable_identity(report):
    """Validates: Requirements 5.4, 9.1"""
    findings = SchemathesisAdapter.parse(report)

    # A well-formed report of failing cases always yields findings to inspect.
    assert findings, "a report of failing cases must produce at least one finding"

    for finding in findings:
        # Scanner name identifies Schemathesis (Req 9.1).
        assert finding.scanner == "schemathesis"

        # rule_id is a non-empty string (Req 5.4, 9.1).
        assert isinstance(finding.rule_id, str)
        assert finding.rule_id.strip() != ""

        # A web Location: a Location with no file line span (Req 9.1).
        assert isinstance(finding.location, Location)
        assert finding.location.path.strip() != ""
        assert finding.location.start_line == 0
        assert finding.location.end_line == 0

        # Severity is drawn from the shared severity scale (Req 9.1).
        assert isinstance(finding.severity, Severity)
        assert finding.severity in _SHARED_SEVERITY_SCALE

        # A non-empty human-readable message (Req 9.1).
        assert isinstance(finding.message, str)
        assert finding.message.strip() != ""

    # rule_id is identical across runs for the same endpoint + failure kind: parsing
    # the same well-formed report again yields the same rule_ids in the same order
    # (Req 5.4, 9.1).
    again = SchemathesisAdapter.parse(report)
    assert [f.rule_id for f in again] == [f.rule_id for f in findings]


@settings(max_examples=200)
@given(report=_report(), scanner_name=st.text(min_size=1, max_size=20))
def test_rule_id_is_stable_across_repeated_parses_of_equal_reports(report, scanner_name):
    """Validates: Requirements 5.4, 9.1

    The stable identity is a property of the report content, not of the run: two
    independent parses of equal reports agree on every rule_id (and the scanner name
    is whatever the caller declares — ``"schemathesis"`` by default).
    """
    first = SchemathesisAdapter.parse(report, scanner_name=scanner_name)
    second = SchemathesisAdapter.parse(report, scanner_name=scanner_name)

    assert [f.rule_id for f in first] == [f.rule_id for f in second]
    assert all(f.scanner == scanner_name for f in first)


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_server_error_finding_is_fully_populated():
    report = make_report(
        cases=[
            make_case(
                method="get",
                path="/api/users/12345",
                status_code=500,
                failed_checks=[_SERVER_ERROR_CHECK],
            )
        ]
    )

    [finding] = SchemathesisAdapter.parse(report)

    assert finding.scanner == "schemathesis"
    assert finding.rule_id == "server_error:GET /api/users/{id}:500"
    assert isinstance(finding.location, Location)
    assert finding.location.path == "GET /api/users/{id}"
    assert finding.severity is Severity.HIGH
    assert finding.message.strip() != ""


def test_example_same_endpoint_and_kind_share_rule_id_across_differing_ids():
    # Two concrete requests on the same operation that differ only in their dynamic
    # segment must carry the same stable rule_id for the same failure kind.
    report_a = make_report(
        cases=[make_case(path="/api/users/1", status_code=500, failed_checks=[_SERVER_ERROR_CHECK])]
    )
    report_b = make_report(
        cases=[make_case(path="/api/users/9999", status_code=500, failed_checks=[_SERVER_ERROR_CHECK])]
    )

    [finding_a] = SchemathesisAdapter.parse(report_a)
    [finding_b] = SchemathesisAdapter.parse(report_b)

    assert finding_a.rule_id == finding_b.rule_id
