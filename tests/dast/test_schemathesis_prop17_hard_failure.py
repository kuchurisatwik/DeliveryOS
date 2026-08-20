# Feature: dast-schemathesis, Property 17: any hard failure yields an incomplete entry and never aborts the scan
"""Property 17 — any hard failure yields an incomplete entry and never aborts the scan.

**Validates: Requirements 1.4, 2.5, 3.4, 12.1, 12.2, 12.3, 12.4**

The whole point of the DAST trust model is that a broken scanner is never mistaken for
a clean application. Schemathesis has several *hard-failure* triggers — a bad argument,
an unloadable/invalid schema, an unreachable target, a configured-but-down proxy, a
non-zero exit before any request landed. For *every* one of them three things must hold
together:

* the adapter **raises** rather than returning a clean ``ScanOutcome`` — a
  ``ScannerError`` for the operational failures, or a plain error (``TypeError``) for a
  non-``DastScope`` argument (Req 1.4, 2.5, 3.4, 12.1, 12.2);
* the runner records that tool's coverage as ``incomplete`` with a **descriptive
  reason** carrying whatever failure-path evidence exists at the point of failure — for
  a non-zero exit that ran the CLI, the exit code and the honest ``requests_made`` /
  ``request_errors`` counts (Req 12.4); and
* **the scan is not aborted**: every *other* adapter still runs and its findings and
  coverage are preserved exactly (Req 12.3).

The invariant is exercised over the real :class:`~dast.runner.run_scan` with a real
:class:`~dast.adapters.schemathesis_adapter.SchemathesisAdapter`, driven at the
command-builder + ``_run`` seam through the in-memory fake in
``tests/dast/_schemathesis_fakes.py`` — no subprocess, and the only network is a
localhost TCP probe to a deliberately-closed port for the proxy-unreachable trigger.
Sibling tools are simple in-memory fakes, so the "other tools keep running" half of the
property is checked without touching a real scanner.

Hard-failure triggers exercised (each maps to a requirement):

* ``production``        — target matches the production pattern → refused (Req 14.x; the
                          canonical "raise before any request" hard failure).
* ``bad_seed``          — fast profile, missing/invalid seed → refused (Req 4.4).
* ``nonzero_exit``      — CLI exits non-zero having landed zero requests → schema
                          unavailable/invalid or target unreachable (Req 2.5, 12.1, 12.2).
* ``proxy_unreachable`` — proxy configured but its host/port cannot be connected to
                          (Req 3.4).
"""

from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, Location, Severity
from dast.models import DastScope, ScanOutcome, ToolActivity
from dast.runner import run_scan
from tests.dast._schemathesis_fakes import FakeSchemathesisRun, make_adapter

SCANNER_NAME = "schemathesis"
TARGET_URL = "http://target.internal"


# --------------------------------------------------------------------------- #
# Settings stub — only the knobs scan() reads. A file schema keeps _schema_source
# local (no --wait-for-schema, no network); the proxy is unconfigured by default so
# the reachability probe never runs unless a trigger configures it.
# --------------------------------------------------------------------------- #
def _settings(
    *,
    prod_pattern: object = None,
    seed: object = 0,
    zap_host: object = None,
    zap_port: object = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        DAST_SCHEMATHESIS_PROD_URL_PATTERN=prod_pattern,
        DAST_SCHEMATHESIS_SEED=seed,
        DAST_SCHEMATHESIS_SCHEMA_FILE="/tmp/openapi.json",
        DAST_OPENAPI_PATH="/openapi.json",
        DAST_ZAP_HOST=zap_host,
        DAST_ZAP_PORT=zap_port,
        DAST_SCHEMATHESIS_RATE_LIMIT=10,
        DAST_SCHEMATHESIS_CONNECT_TIMEOUT=30,
        DAST_SCHEMATHESIS_SCHEMA_TIMEOUT=30,
        DAST_SCHEMATHESIS_TIMEOUT=900,
        DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT=5,
    )


def _closed_localhost_port() -> int:
    """A localhost port that is bound then released, so connecting is refused fast."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


# --------------------------------------------------------------------------- #
# Sibling in-memory tool — proves the scan is not aborted (Req 12.3).
# --------------------------------------------------------------------------- #
class _SiblingTool:
    """A trivial adapter that always completes with the findings it was given."""

    def __init__(self, name: str, *, mutating: bool, rule_ids: tuple[str, ...]) -> None:
        self.name = name
        self.mutating = mutating
        self._rule_ids = rule_ids

    def scan(self, scope: DastScope) -> ScanOutcome:
        findings = tuple(_finding(self.name, rid) for rid in self._rule_ids)
        # Honest evidence so _assess_activity classes this "complete".
        return ScanOutcome(
            findings=findings,
            activity=ToolActivity(units_executed=100, requests_made=50, request_errors=0),
        )


def _finding(scanner: str, rule_id: str) -> Finding:
    return Finding(
        scanner=scanner,
        rule_id=rule_id,
        location=Location(path="/x", start_line=0, end_line=0),
        severity=Severity.HIGH,
        message="m",
        raw={},
    )


# --------------------------------------------------------------------------- #
# Build a hard-failing SchemathesisAdapter for a given trigger.
# --------------------------------------------------------------------------- #
#: For each trigger, the substrings the incomplete coverage reason must carry.
_EXPECTED_REASON: dict[str, tuple[str, ...]] = {
    "production": ("refused",),
    "bad_seed": ("seed",),
    "nonzero_exit": ("before any request", "requests_made="),
    "proxy_unreachable": ("proxy unreachable",),
}

#: Triggers that raise a plain error (not a ScannerError) — only the argument guard.
_TRIGGERS = ("production", "bad_seed", "nonzero_exit", "proxy_unreachable")


def _failing_adapter(trigger: str):
    """Return ``(adapter, fake)`` wired so ``scan`` hits ``trigger``'s hard failure."""
    if trigger == "production":
        settings = _settings(prod_pattern=r"target\.internal")
        fake = FakeSchemathesisRun()
    elif trigger == "bad_seed":
        settings = _settings(seed=None)
        fake = FakeSchemathesisRun()
    elif trigger == "nonzero_exit":
        settings = _settings()
        # Non-zero exit and NO report written → zero requests landed → hard failure.
        fake = FakeSchemathesisRun(returncode=1, stderr="could not load schema")
    elif trigger == "proxy_unreachable":
        settings = _settings(zap_host="127.0.0.1", zap_port=_closed_localhost_port())
        fake = FakeSchemathesisRun()
    else:  # pragma: no cover - defensive
        raise AssertionError(f"unknown trigger {trigger!r}")
    return make_adapter(settings=settings, fake=fake), fake


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
_TRIGGER = st.sampled_from(_TRIGGERS)

# A distinct rule id per sibling finding.
_RULE_IDS = st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8),
    min_size=1,
    max_size=4,
    unique=True,
).map(tuple)

# Arbitrary non-DastScope arguments for the Req 1.4 guard.
_NOT_A_SCOPE = st.one_of(
    st.none(),
    st.integers(),
    st.text(),
    st.lists(st.integers()),
    st.dictionaries(st.text(), st.text()),
    st.tuples(st.text()),
    st.builds(object),
)


# --------------------------------------------------------------------------- #
# The property: any hard failure → incomplete entry, scan not aborted
# --------------------------------------------------------------------------- #
# deadline disabled: the ``proxy_unreachable`` trigger performs a real localhost TCP
# connect to a deliberately-closed port, whose refusal latency is OS-dependent (up to a
# couple of seconds on Windows) and unrelated to the invariant under test.
@hyp_settings(max_examples=150, deadline=None)
@given(trigger=_TRIGGER, sibling_rules=_RULE_IDS)
def test_hard_failure_yields_incomplete_and_never_aborts(
    trigger: str, sibling_rules: tuple[str, ...]
) -> None:
    """Validates: Requirements 2.5, 3.4, 12.1, 12.2, 12.3, 12.4

    For any hard-failure trigger, the Schemathesis coverage is ``incomplete`` with a
    descriptive reason (never a clean result), and every sibling tool still runs and
    reports unchanged.
    """
    schema_tool, _ = _failing_adapter(trigger)
    sibling = _SiblingTool("nuclei", mutating=False, rule_ids=sibling_rules)

    result = run_scan(DastScope(target_url=TARGET_URL, profile="fast"),
                      [sibling, schema_tool])

    by_name = {c.scanner: c for c in result.coverage}

    # 1. Schemathesis never renders as a clean result — it is incomplete...
    schema_cov = by_name[SCANNER_NAME]
    assert schema_cov.status == "incomplete"
    # ...with a descriptive, non-empty reason carrying the trigger's evidence.
    assert schema_cov.reason
    lowered = schema_cov.reason.lower()
    for fragment in _EXPECTED_REASON[trigger]:
        assert fragment.lower() in lowered
    # No Schemathesis finding leaked from an aborted run.
    assert not [f for f in result.findings if f.scanner == SCANNER_NAME]

    # 2. The scan was NOT aborted: the sibling ran to completion, unchanged.
    sibling_cov = by_name["nuclei"]
    assert sibling_cov.status == "complete"
    assert sibling_cov.reason is None
    assert {f.rule_id for f in result.findings if f.scanner == "nuclei"} == set(
        sibling_rules
    )
    # Every tool produced a coverage entry.
    assert set(by_name) == {SCANNER_NAME, "nuclei"}


# --------------------------------------------------------------------------- #
# Failure-path evidence on the non-zero-exit path (Req 12.4)
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=100)
@given(
    exit_code=st.integers(min_value=1, max_value=255),
    sibling_rules=_RULE_IDS,
)
def test_nonzero_exit_reason_carries_failure_path_evidence(
    exit_code: int, sibling_rules: tuple[str, ...]
) -> None:
    """Validates: Requirements 12.2, 12.4

    A CLI that exits non-zero having landed zero requests is a hard failure whose
    reason carries the available evidence: the exit code and the honest request counts
    (both zero, since nothing reached the target).
    """
    fake = FakeSchemathesisRun(returncode=exit_code, stderr="schema load failed")
    adapter = make_adapter(settings=_settings(), fake=fake)
    sibling = _SiblingTool("zap", mutating=False, rule_ids=sibling_rules)

    result = run_scan(DastScope(target_url=TARGET_URL, profile="fast"),
                      [adapter, sibling])

    by_name = {c.scanner: c for c in result.coverage}
    schema_cov = by_name[SCANNER_NAME]
    assert schema_cov.status == "incomplete"
    # Evidence available at the point of failure: exit code + zero-request counts.
    assert str(exit_code) in schema_cov.reason
    assert "requests_made=0" in schema_cov.reason
    assert "request_errors=0" in schema_cov.reason
    # Sibling preserved.
    assert by_name["zap"].status == "complete"


# --------------------------------------------------------------------------- #
# A non-DastScope argument raises (an error), never a clean ScanOutcome (Req 1.4)
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=150)
@given(not_a_scope=_NOT_A_SCOPE)
def test_non_dastscope_argument_raises_and_returns_nothing(not_a_scope: object) -> None:
    """Validates: Requirements 1.4

    Invoked with anything other than a ``DastScope``, ``scan`` raises before doing any
    work and never returns a ``ScanOutcome`` — no command is built and nothing is sent.
    """
    fake = FakeSchemathesisRun()
    adapter = make_adapter(settings=_settings(), fake=fake)

    with pytest.raises(TypeError):
        adapter.scan(not_a_scope)  # type: ignore[arg-type]

    # Refused before the command-builder seam → nothing was ever driven.
    assert not fake.called


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_production_refusal_is_incomplete_others_survive() -> None:
    """Validates: Requirements 12.3

    A production refusal marks Schemathesis incomplete while a sibling tool's finding
    and its complete coverage are preserved untouched.
    """
    schema_tool, fake = _failing_adapter("production")
    sibling = _SiblingTool("nuclei", mutating=False, rule_ids=("r1",))

    result = run_scan(DastScope(target_url=TARGET_URL, profile="fast"),
                      [schema_tool, sibling])

    by_name = {c.scanner: c for c in result.coverage}
    assert by_name[SCANNER_NAME].status == "incomplete"
    assert "refused" in by_name[SCANNER_NAME].reason.lower()
    assert not fake.called  # refused before sending anything
    assert [f.rule_id for f in result.findings if f.scanner == "nuclei"] == ["r1"]
    assert by_name["nuclei"].status == "complete"


def test_example_proxy_unreachable_is_incomplete() -> None:
    """Validates: Requirements 3.4

    A configured-but-down proxy is a hard failure: incomplete coverage, no fallback to
    unproxied traffic (the seam is never reached).
    """
    schema_tool, fake = _failing_adapter("proxy_unreachable")
    result = run_scan(DastScope(target_url=TARGET_URL, profile="fast"), [schema_tool])

    cov = result.coverage[0]
    assert cov.scanner == SCANNER_NAME
    assert cov.status == "incomplete"
    assert "proxy unreachable" in cov.reason.lower()
    assert not fake.called


def test_example_adapter_raises_scannererror_directly() -> None:
    """Validates: Requirements 2.5, 12.2

    At the adapter level a non-zero exit with no requests raises ``ScannerError`` and
    returns no ``ScanOutcome``.
    """
    fake = FakeSchemathesisRun(returncode=1, stderr="boom")
    adapter = make_adapter(settings=_settings(), fake=fake)

    with pytest.raises(ScannerError) as excinfo:
        adapter.scan(DastScope(target_url=TARGET_URL, profile="fast"))

    assert excinfo.value.scanner == SCANNER_NAME
    assert "before any request" in excinfo.value.reason
