# Feature: dast-schemathesis, Property 8: every finding carries a complete, reissuable reproducing request
"""Property 8 — every finding carries a complete, reissuable reproducing request.

*For any* produced ``Finding``, its ``raw`` carries a reproducing request recording the
HTTP method, the path including any query string, every header sent, and the body — with
the body recorded as an explicit empty value when the request carried none and the auth
header present among the headers when the outgoing request carried it. If the request
cannot be captured, an explicit ``{"unavailable": True}`` marker is attached instead of
emitting a ``Finding`` with no request detail.

The chain under test is :meth:`SchemathesisAdapter.parse`, a pure classmethod over a
decoded Schemathesis report (no binary, no network, no target). Every produced finding —
whichever of the three kinds it is — must carry the reproducing request under
``raw["reproducing_request"]`` (Req 8.1), and that block must be complete and reissuable
(Req 8.2–8.4) or an explicit unavailable marker (Req 8.5).

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from dast.adapters.schemathesis_adapter import (
    _IGNORED_AUTH_CHECK,
    _SCHEMA_CHECK_ORDER,
    _SERVER_ERROR_CHECK,
    SchemathesisAdapter,
)

from tests.dast._schemathesis_fakes import make_case, make_check, make_report

# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
_http_methods = st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"])

# Every check whose failure yields at least one Finding. Drawing a non-empty subset
# guarantees the generated case is a Failing_Case, so parse() always produces a finding
# whose reproducing request we can inspect.
_ALL_FAILING_CHECKS: tuple[str, ...] = (
    _SERVER_ERROR_CHECK,
    _IGNORED_AUTH_CHECK,
    *_SCHEMA_CHECK_ORDER,
)
_failed_checks = st.lists(
    st.sampled_from(_ALL_FAILING_CHECKS), min_size=1, max_size=len(_ALL_FAILING_CHECKS)
).map(lambda names: sorted(set(names)))

# A route path: leading-slash-joined lowercase segments (min_size 0 -> "/").
_route_segment = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
_paths = st.lists(_route_segment, min_size=0, max_size=4).map(
    lambda segs: "/" + "/".join(segs)
)

# A query string built from alphanumeric key=value pairs — round-trips through urlsplit
# unchanged, so the expected path+query is exactly what we construct here.
_kv_token = st.text(
    alphabet=string.ascii_letters + string.digits, min_size=1, max_size=5
)
_query = st.lists(st.tuples(_kv_token, _kv_token), min_size=1, max_size=3).map(
    lambda pairs: "&".join(f"{k}={v}" for k, v in pairs)
)

# Arbitrary non-auth request headers.
_header_name = st.sampled_from(
    ["Content-Type", "Accept", "X-Trace", "User-Agent", "X-Custom"]
)
_header_bag = st.dictionaries(_header_name, st.text(min_size=0, max_size=12), max_size=5)

# An Authorization value the outgoing request may or may not have carried.
_auth_value = st.text(
    alphabet=string.ascii_letters + string.digits + " ._-", min_size=1, max_size=24
)

# A request body: absent (None) or an arbitrary JSON-ish payload.
_body = st.one_of(
    st.none(),
    st.text(max_size=16),
    st.integers(),
    st.lists(st.integers(), max_size=4),
    st.dictionaries(_kv_token, st.integers(), max_size=4),
)

_status_codes = st.integers(min_value=100, max_value=599)


@st.composite
def _capturable_case(draw):
    """One failing case with a fully captured request, plus the expected repro block.

    Returns ``(case, expected)`` where ``expected`` is the reproducing-request mapping
    ``parse`` must record for the case's findings — computed here independently of
    ``parse``'s own construction.
    """
    method = draw(_http_methods)
    path = draw(_paths)
    query = draw(st.one_of(st.none(), _query))
    headers = dict(draw(_header_bag))
    auth = draw(st.one_of(st.none(), _auth_value))
    if auth is not None:
        headers["Authorization"] = auth
    body = draw(_body)

    uri = f"http://target{path}"
    expected_path = path
    if query is not None:
        uri = f"{uri}?{query}"
        expected_path = f"{path}?{query}"

    case = make_case(
        method=method,
        path=path,
        uri=uri,
        status_code=draw(_status_codes),
        failed_checks=draw(_failed_checks),
        headers=headers,
        body=body,
    )
    expected = {
        "method": method.upper(),
        "path": expected_path,
        "headers": dict(headers),
        # Explicit empty value when the request carried no body (Req 8.3).
        "body": "" if body is None else body,
        "auth": auth,
    }
    return case, expected


@st.composite
def _uncapturable_case(draw):
    """One failing case whose request could NOT be captured (no ``request`` block).

    Schemathesis occasionally emits a case with no reproducible request; the parser must
    still surface a finding, marking the reproducing request unavailable (Req 8.5).
    """
    method = draw(_http_methods)
    path = draw(_paths)
    checks = [make_check(name, failed=True) for name in draw(_failed_checks)]
    return {
        "method": method,
        "path": path,
        "response": {"status_code": draw(_status_codes)},
        "checks": checks,
    }


# --------------------------------------------------------------------------- #
# Property 8 — captured requests are complete and reissuable
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(specs=st.lists(_capturable_case(), min_size=1, max_size=6))
def test_every_finding_carries_a_complete_reproducing_request(specs):
    """Validates: Requirements 8.1, 8.2, 8.3, 8.4

    Every produced finding's ``raw`` carries a reproducing request recording the method,
    the path including any query string, every header sent (the auth header among them
    when the outgoing request carried it), and the body (explicit empty value when
    absent) — so the recorded request can be reissued unchanged.
    """
    cases = [case for case, _ in specs]
    findings = SchemathesisAdapter.parse(make_report(cases=cases))

    # A report of failing cases must yield findings to inspect.
    assert findings

    for finding in findings:
        # The reproducing request rides in raw under a dedicated key (Req 8.1).
        assert "reproducing_request" in finding.raw
        repro = finding.raw["reproducing_request"]

        # A captured request is never the unavailable marker.
        assert repro.get("unavailable") is not True

        # Method, path+query, headers, and body are all present (Req 8.2, 8.3).
        assert set(repro) == {"method", "path", "headers", "body"}
        assert isinstance(repro["method"], str) and repro["method"] != ""
        assert isinstance(repro["path"], str) and repro["path"] != ""
        assert isinstance(repro["headers"], dict)
        assert "body" in repro  # explicit, never omitted


@settings(max_examples=200)
@given(spec=_capturable_case())
def test_reproducing_request_matches_the_outgoing_request_exactly(spec):
    """Validates: Requirements 8.2, 8.3, 8.4

    The recorded reproducing request equals the outgoing request field-for-field: the
    upper-cased method, the path including query string, every header (with the auth
    header preserved when it was carried), and the body (empty value when absent).
    """
    case, expected = spec
    findings = SchemathesisAdapter.parse(make_report(cases=[case]))
    assert findings

    for finding in findings:
        repro = finding.raw["reproducing_request"]
        assert repro["method"] == expected["method"]
        assert repro["path"] == expected["path"]
        # Every header sent is recorded, unchanged (Req 8.2).
        assert repro["headers"] == expected["headers"]
        # Body: the exact payload, or an explicit empty value when absent (Req 8.3).
        assert repro["body"] == expected["body"]
        # The auth header is present exactly when the outgoing request carried it (Req 8.4).
        if expected["auth"] is not None:
            assert repro["headers"].get("Authorization") == expected["auth"]
        else:
            assert "Authorization" not in repro["headers"]


# --------------------------------------------------------------------------- #
# Property 8 — the unavailable marker (Req 8.5)
# --------------------------------------------------------------------------- #
@settings(max_examples=200)
@given(cases=st.lists(_uncapturable_case(), min_size=1, max_size=6))
def test_uncapturable_request_yields_explicit_unavailable_marker(cases):
    """Validates: Requirements 8.1, 8.5

    When a failing case's request cannot be captured, the parser still emits a finding,
    attaching an explicit ``{"unavailable": True}`` marker rather than a finding with no
    request detail.
    """
    findings = SchemathesisAdapter.parse(make_report(cases=cases))
    assert findings

    for finding in findings:
        assert "reproducing_request" in finding.raw
        assert finding.raw["reproducing_request"] == {"unavailable": True}


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_repro_records_query_headers_auth_and_empty_body():
    case = make_case(
        method="post",
        path="/api/orders",
        uri="http://target/api/orders?expand=items",
        status_code=500,
        failed_checks=[_SERVER_ERROR_CHECK],
        headers={"Authorization": "Bearer abc", "Content-Type": "application/json"},
        body=None,
    )

    [finding] = SchemathesisAdapter.parse(make_report(cases=[case]))
    repro = finding.raw["reproducing_request"]

    assert repro["method"] == "POST"
    assert repro["path"] == "/api/orders?expand=items"
    assert repro["headers"] == {
        "Authorization": "Bearer abc",
        "Content-Type": "application/json",
    }
    assert repro["body"] == ""


def test_example_repro_preserves_a_non_empty_body():
    case = make_case(
        method="put",
        path="/api/users/1",
        status_code=422,
        failed_checks=[*_SCHEMA_CHECK_ORDER[:1]],
        body={"name": "x"},
    )

    [finding] = SchemathesisAdapter.parse(make_report(cases=[case]))
    repro = finding.raw["reproducing_request"]

    assert repro["method"] == "PUT"
    assert repro["body"] == {"name": "x"}


def test_example_unavailable_marker_when_no_request_captured():
    case = {
        "method": "GET",
        "path": "/api/health",
        "response": {"status_code": 500},
        "checks": [make_check(_SERVER_ERROR_CHECK, failed=True)],
    }

    [finding] = SchemathesisAdapter.parse(make_report(cases=[case]))

    assert finding.raw["reproducing_request"] == {"unavailable": True}
