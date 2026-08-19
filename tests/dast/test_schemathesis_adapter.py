# Feature: dast-schemathesis, Task 2.10: parse against a saved machine-readable report fixture
"""Unit test: ``SchemathesisAdapter.parse`` against a saved Schemathesis report.

**Validates: Requirements 5.1, 6.1, 7.1, 8.1**

Where the property tests generate reports from the shared builders in
``_schemathesis_fakes``, this test pins the mapping against a *captured* report —
``tests/dast/fixtures/schemathesis_report.json`` — so the real Schemathesis field
names (``results`` / ``method`` / ``path`` / ``cases`` / ``request`` / ``response`` /
``checks``) are exercised exactly as the CLI emits them. It proves that:

* a failed ``not_a_server_error`` check maps to one high-severity server-error
  finding (Req 5.1);
* a failed ``ignored_auth`` check maps to one unauthenticated-access finding carrying
  the observed status (Req 6.1);
* one or more failed schema-conformance checks map to a single contract-violation
  finding enumerating every violated element (Req 7.1); and
* every finding carries its reproducing request — method, path (with query string),
  headers, and body (Req 8.1).

``parse`` is a pure classmethod, so this runs with no binary, no network, and no
target.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.security.models import Finding, Location, Severity
from dast.adapters.schemathesis_adapter import (
    _KIND_IGNORED_AUTH,
    _KIND_SCHEMA_VIOLATION,
    _KIND_SERVER_ERROR,
    SchemathesisAdapter,
)

# The saved machine-readable report captured from a real fast-profile scan.
_FIXTURE = Path(__file__).parent / "fixtures" / "schemathesis_report.json"

# OpenAPI templates from the target's spec, so concrete ids in the captured URLs are
# templatised through the same spec-driven path the runner uses (Req 9.2). The report
# reaches /api/users/42, /api/orders/1008, and /api/orders.
_SPEC_PATHS = ("/api/users/{id}", "/api/orders/{order_id}", "/api/orders")

# The exact Authorization header value recorded in the fixture's authenticated cases.
_AUTH = "Bearer staging-token-abc123"


@pytest.fixture(scope="module")
def report() -> dict:
    """The decoded saved Schemathesis report."""
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def findings(report) -> list[Finding]:
    """Findings parsed from the saved report with the target's spec paths."""
    return SchemathesisAdapter.parse(report, spec_paths=_SPEC_PATHS)


def _by_kind(findings: list[Finding], kind: str) -> list[Finding]:
    """Every finding whose stable ``rule_id`` prefix identifies ``kind``."""
    return [f for f in findings if f.rule_id.startswith(f"{kind}:")]


# --------------------------------------------------------------------------- #
# The report yields exactly the three expected finding kinds
# --------------------------------------------------------------------------- #
def test_report_yields_one_finding_per_kind(findings):
    """The captured report carries one failing case for each of the three kinds."""
    assert len(findings) == 3

    kinds = {
        _KIND_SERVER_ERROR: _by_kind(findings, _KIND_SERVER_ERROR),
        _KIND_IGNORED_AUTH: _by_kind(findings, _KIND_IGNORED_AUTH),
        _KIND_SCHEMA_VIOLATION: _by_kind(findings, _KIND_SCHEMA_VIOLATION),
    }
    assert all(len(group) == 1 for group in kinds.values()), kinds

    # Every finding is a shared Finding on a web Location from the schemathesis scanner.
    for finding in findings:
        assert finding.scanner == "schemathesis"
        assert isinstance(finding.location, Location)
        assert finding.location.start_line == 0
        assert finding.location.end_line == 0
        assert finding.message.strip() != ""


# --------------------------------------------------------------------------- #
# Req 5.1 — not_a_server_error -> high-severity undeclared 5xx
# --------------------------------------------------------------------------- #
def test_not_a_server_error_maps_to_high_severity_server_error(findings):
    """Validates: Requirements 5.1, 8.1"""
    [finding] = _by_kind(findings, _KIND_SERVER_ERROR)

    # HIGH severity, endpoint = METHOD + templatised path, status carried in rule_id.
    assert finding.severity is Severity.HIGH
    assert finding.location.path == "GET /api/users/{id}"
    assert finding.rule_id == "server_error:GET /api/users/{id}:500"
    assert "500" in finding.message
    assert finding.raw["checks"] == ["not_a_server_error"]

    # Req 8.1 — the reproducing request is attached, with the query string preserved,
    # the auth header among the recorded headers, and an explicit (empty) body.
    repro = finding.raw["reproducing_request"]
    assert repro["method"] == "GET"
    assert repro["path"] == "/api/users/42?include=profile"
    assert repro["headers"]["Authorization"] == _AUTH
    assert repro["body"] == ""


# --------------------------------------------------------------------------- #
# Req 6.1 — ignored_auth -> unauthenticated-access finding carrying the status
# --------------------------------------------------------------------------- #
def test_ignored_auth_maps_to_unauthenticated_access_finding(findings):
    """Validates: Requirements 6.1, 8.1"""
    [finding] = _by_kind(findings, _KIND_IGNORED_AUTH)

    # The observed 2xx status is carried through into the finding (Req 6.1/6.2).
    assert finding.rule_id == "ignored_auth:GET /api/orders/{order_id}:200"
    assert finding.location.path == "GET /api/orders/{order_id}"
    assert "200" in finding.message
    assert finding.raw["checks"] == ["ignored_auth"]

    # Req 8.1 — reproducing request attached. This case was sent with auth omitted, so
    # no Authorization header is recorded, and the empty body is explicit.
    repro = finding.raw["reproducing_request"]
    assert repro["method"] == "GET"
    assert repro["path"] == "/api/orders/1008"
    assert "Authorization" not in repro["headers"]
    assert repro["body"] == ""


# --------------------------------------------------------------------------- #
# Req 7.1 — schema conformance -> one contract finding enumerating every element
# --------------------------------------------------------------------------- #
def test_schema_conformance_maps_to_single_contract_violation(findings):
    """Validates: Requirements 7.1, 8.1"""
    [finding] = _by_kind(findings, _KIND_SCHEMA_VIOLATION)

    # MEDIUM severity, and the two failed conformance checks collapse into ONE finding
    # whose message enumerates both violated elements in the fixed enumeration order.
    assert finding.severity is Severity.MEDIUM
    assert finding.location.path == "POST /api/orders"
    assert finding.rule_id == "schema_violation:POST /api/orders:418"
    assert finding.raw["checks"] == [
        "status_code_conformance",
        "response_schema_conformance",
    ]
    assert "status code" in finding.message
    assert "response body" in finding.message

    # Req 8.1 — reproducing request attached, with the JSON body and the auth header
    # preserved so the request can be reissued unchanged.
    repro = finding.raw["reproducing_request"]
    assert repro["method"] == "POST"
    assert repro["path"] == "/api/orders"
    assert repro["headers"]["Authorization"] == _AUTH
    assert repro["headers"]["Content-Type"] == "application/json"
    assert repro["body"] == '{"sku": "WIDGET-1", "quantity": -2147483648}'


# --------------------------------------------------------------------------- #
# parse is pure: repeated calls over the saved report agree exactly
# --------------------------------------------------------------------------- #
def test_parse_is_deterministic_over_the_saved_report(report):
    """Validates: Requirements 5.1, 6.1, 7.1"""
    first = SchemathesisAdapter.parse(report, spec_paths=_SPEC_PATHS)
    second = SchemathesisAdapter.parse(report, spec_paths=_SPEC_PATHS)

    assert [f.rule_id for f in first] == [f.rule_id for f in second]
    assert [f.raw for f in first] == [f.raw for f in second]
