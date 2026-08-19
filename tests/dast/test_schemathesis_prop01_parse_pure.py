# Feature: dast-schemathesis, Property 1: parse() is pure and deterministic
"""Property 1 — ``SchemathesisAdapter.parse`` is pure and deterministic.

*For any* Schemathesis report and any ``spec_paths``, calling
:meth:`SchemathesisAdapter.parse` twice with the same arguments produces equal
``Finding`` lists, and the call performs no network or filesystem I/O.

**Validates: Requirements 1.5**

The ``parse`` layer is a pure classmethod over Schemathesis's decoded
machine-readable report (grouped operations, flat cases, a ``cases`` block, or a
bare list — each carrying a request, a response, and the checks that ran). This
test builds arbitrary reports across all four accepted shapes plus a spread of
failing/passing/un-annotated checks, then asserts:

* **determinism** — two calls with the same arguments return equal ``Finding``
  lists (``Finding`` is a frozen dataclass, so equality is structural, covering
  ``rule_id``, ``severity``, ``message``, ``location`` and the ``raw`` evidence);
* **purity (no side effects on input)** — the report mapping is not mutated; and
* **purity (no I/O)** — ``socket``/``open`` are stubbed to raise for the duration
  of each call, so any network or filesystem access surfaces as a failure.
"""

from __future__ import annotations

import contextlib
import copy
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from dast.adapters.schemathesis_adapter import SchemathesisAdapter

# --------------------------------------------------------------------------- #
# Generators — arbitrary decoded Schemathesis reports
# --------------------------------------------------------------------------- #
# The four finding-bearing check names plus a couple of unrelated ones, so the
# generator exercises both the classified kinds and checks parse() must ignore.
_CHECK_NAMES = [
    "not_a_server_error",
    "ignored_auth",
    "status_code_conformance",
    "content_type_conformance",
    "response_headers_conformance",
    "response_schema_conformance",
    "some_other_check",
    "positive_data_acceptance",
]

_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
_PATHS = ["/", "/health", "/api/users", "/api/users/12345", "/orders/42/items"]
_STATUSES = [200, 201, 204, 401, 403, 404, 409, 500, 502, 503]
_HEADER_NAMES = ["Authorization", "Accept", "Content-Type", "X-Trace"]


@st.composite
def _check(draw: st.DrawFn) -> dict:
    """One check-result entry, sometimes un-annotated (report-of-failures shape)."""
    check: dict = {"name": draw(st.sampled_from(_CHECK_NAMES))}
    status = draw(
        st.sampled_from(
            ["failure", "failed", "error", "success", "passed", None]
        )
    )
    if status is not None:
        # Vary the field the status rides on, since parse() reads several.
        key = draw(st.sampled_from(["status", "value", "outcome", "result"]))
        check[key] = status
    return check


@st.composite
def _request(draw: st.DrawFn) -> dict:
    method = draw(st.sampled_from(_METHODS))
    path = draw(st.sampled_from(_PATHS))
    query = draw(st.sampled_from(["", "?q=1", "?a=b&c=d"]))
    headers = draw(
        st.dictionaries(
            st.sampled_from(_HEADER_NAMES),
            st.text(max_size=12),
            max_size=3,
        )
    )
    body = draw(
        st.one_of(
            st.none(),
            st.text(max_size=16),
            st.dictionaries(st.text(min_size=1, max_size=4), st.integers(), max_size=2),
        )
    )
    request: dict = {
        "method": method,
        "uri": f"http://target{path}{query}",
        "headers": headers,
    }
    if body is not None:
        request["body"] = body
    return request


@st.composite
def _case(draw: st.DrawFn) -> dict:
    method = draw(st.sampled_from(_METHODS))
    path = draw(st.sampled_from(_PATHS))
    case: dict = {
        "method": method,
        "path": path,
        "request": draw(_request()),
        "response": {"status_code": draw(st.sampled_from(_STATUSES))},
        "checks": draw(st.lists(_check(), max_size=5)),
    }
    # Sometimes surface failures as a flat name list too (parse() honours both).
    if draw(st.booleans()):
        case["failures"] = draw(
            st.lists(st.sampled_from(_CHECK_NAMES), max_size=3)
        )
    return case


@st.composite
def _report(draw: st.DrawFn) -> object:
    """A decoded report in any of the four shapes parse() accepts."""
    cases = draw(st.lists(_case(), max_size=6))
    shape = draw(
        st.sampled_from(["grouped", "results_cases", "cases_key", "bare_list"])
    )
    if shape == "grouped":
        return {
            "results": [
                {
                    "method": draw(st.sampled_from(_METHODS)),
                    "path": draw(st.sampled_from(_PATHS)),
                    "cases": cases,
                }
            ]
        }
    if shape == "results_cases":
        return {"results": cases}
    if shape == "cases_key":
        return {"cases": cases}
    return cases


_spec_paths = st.lists(
    st.sampled_from(
        ["/api/users/{id}", "/orders/{order_id}/items", "/api/users/{user_id}"]
    ),
    max_size=3,
).map(tuple)


# --------------------------------------------------------------------------- #
# I/O guard — parse() must touch neither the network nor the filesystem
# --------------------------------------------------------------------------- #
@contextlib.contextmanager
def _no_io():
    """Make any network/filesystem access raise for the duration of the block."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("parse() performed I/O — it must be pure")

    with patch("socket.socket", side_effect=_boom), patch(
        "socket.create_connection", side_effect=_boom
    ), patch("builtins.open", side_effect=_boom):
        yield


# --------------------------------------------------------------------------- #
# The property
# --------------------------------------------------------------------------- #
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(report=_report(), spec_paths=_spec_paths)
def test_parse_is_pure_and_deterministic(report, spec_paths):
    # A pristine copy to prove parse() does not mutate its input.
    report_snapshot = copy.deepcopy(report)

    with _no_io():
        first = SchemathesisAdapter.parse(report, spec_paths=spec_paths)
    with _no_io():
        second = SchemathesisAdapter.parse(report, spec_paths=spec_paths)

    # Determinism: equal arguments -> equal Finding lists (structural equality).
    assert first == second
    # Purity: the input report is left untouched.
    assert report == report_snapshot
