# Feature: dast-schemathesis, Property 4: duplicate failing cases collapse to one finding
"""Property 4 — duplicate failing cases collapse to one finding.

**Validates: Requirements 9.3, 9.4, 9.5**

A dynamic scanner generates *thousands* of requests, and the same underlying defect
fires again and again: the same operation 500s on twenty different malformed bodies,
or answers unauthenticated on every id it tries. If each of those failing cases became
its own finding, one bug would render as a wall of near-identical noise and the
baseline would be useless within a week.

So the guarantee this property pins down is: for any failing case repeated any number
of times — sharing both its **rule identity** (same finding kind, method, templatised
path, status) and its **endpoint identity** (same templatised path, even when the
concrete dynamic segments differ) — the shared normalize → dedupe chain
(:func:`dast.intelligence.consolidate`) collapses the parsed findings to **exactly one**
finding for that identity, retaining one representative. And because a first scan has no
baseline to compare against, every such finding is classified as new — nothing is
pre-existing, resolved, or unverified (Req 9.4, 9.5).

The parse layer under test is :meth:`SchemathesisAdapter.parse`; the collapse is done by
the same ``consolidate`` and baseline diff that nuclei and ZAP use, so this is a
property of the whole normalize → dedupe → baseline chain as Schemathesis feeds it.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from dast import baseline
from dast.adapters.schemathesis_adapter import SchemathesisAdapter
from dast.intelligence import consolidate

from tests.dast._schemathesis_fakes import make_case, make_report

# --------------------------------------------------------------------------- #
# Strategies — a single failing-case shape, repeated with varying dynamic ids
# --------------------------------------------------------------------------- #
# Each generated example describes ONE failing-case identity: one finding kind, one
# method, one templatised endpoint, one response status. It is then materialised as
# ``N`` concrete cases that differ only in the dynamic path segment, so every case
# shares the same rule identity AND the same (templatised) endpoint identity — the
# exact precondition of the property.

_METHODS = st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"])
_RESOURCES = st.sampled_from(["users", "orders", "items", "accounts", "invoices"])

# The three finding kinds parse() classifies, each isolated to a single kind so every
# case yields exactly one finding sharing one rule identity: (failed check names,
# response status).
_KINDS = st.sampled_from(
    [
        (("not_a_server_error",), 500),
        (("not_a_server_error",), 503),
        (("ignored_auth",), 200),
        (("ignored_auth",), 204),
        (("response_schema_conformance",), 200),
        (("status_code_conformance", "response_schema_conformance"), 418),
    ]
)


@st.composite
def repeated_failing_cases(draw):
    """Build ``(report, spec_paths, count)`` for one repeated failing-case identity.

    Returns a Schemathesis report holding ``count`` cases that all hit the same
    templatised endpoint with the same failing checks and status, differing only in
    the concrete id in the path (e.g. ``/api/users/12345`` vs ``/api/users/67890``).
    """
    resource = draw(_RESOURCES)
    method = draw(_METHODS)
    failed_checks, status = draw(_KINDS)
    template = f"/api/{resource}/{{id}}"

    # The dynamic segments the repeated cases differ by. Duplicates are allowed — a
    # bug that fires twice on the same concrete id is still one finding.
    ids = draw(st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=25))

    cases = [
        make_case(
            method=method,
            path=f"/api/{resource}/{id_}",
            uri=f"http://target/api/{resource}/{id_}",
            status_code=status,
            failed_checks=failed_checks,
        )
        for id_ in ids
    ]
    report = make_report(cases=cases)
    return report, (template,), len(ids)


# --------------------------------------------------------------------------- #
# Property
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(data=repeated_failing_cases())
def test_duplicate_failing_cases_collapse_to_one_finding(data):
    report, spec_paths, count = data

    parsed = SchemathesisAdapter.parse(report, spec_paths=spec_paths)

    # Precondition sanity: each repeated case yields exactly one finding, and every
    # parsed finding shares one rule identity (same kind, method, templatised path,
    # status) — the "same failing case repeated" the property is about.
    assert len(parsed) == count
    assert len({f.rule_id for f in parsed}) == 1
    assert len({f.location.path for f in parsed}) == 1

    # 1. consolidate collapses the repeats to exactly one finding for that identity,
    #    retaining one representative (Req 9.3)...
    result = consolidate(parsed)
    assert result.raw_count == count
    assert len(result.findings) == 1

    representative = result.findings[0]
    # ...while every occurrence is preserved as evidence behind that one finding.
    assert len(result.evidence[representative.finding_id]) == count

    # 2. With no stored baseline, every finding is classified new: the scan is a
    #    first scan, nothing is pre-existing/resolved/unverified, and the one
    #    consolidated finding is tracked (Req 9.4, 9.5).
    diff = baseline.diff({}, result.findings, coverage_complete=True)
    assert diff.is_first_scan is True
    assert diff.resolved == ()
    assert diff.unverified == ()
    tracked = set(diff.new) | set(diff.known)
    assert tracked == {f.finding_id for f in result.findings}
