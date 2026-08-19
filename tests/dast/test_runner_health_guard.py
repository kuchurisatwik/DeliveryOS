"""Runner health guard — a target that dies mid-scan degrades to unverified.

Some targets fall over under the read-only tier's load. Once the target is down,
every mutating tool that reaches it through the proxy sees 5xx and would report a
wall of false "server error" findings. The runner's optional ``health_check`` probe
stops that: when the target is reported down, the remaining mutating tools are
skipped with an honest ``incomplete`` reason instead of running against a corpse.

These use fake adapters and a fake probe — no tool, target, or network involved.
"""

from __future__ import annotations

import time

from app.security.models import Finding, Location, Severity
from dast.models import DastScope, ScanOutcome, ToolActivity
from dast.runner import run_scan

SCOPE = DastScope(target_url="https://staging.test")


def _finding(rule_id: str) -> Finding:
    return Finding(
        scanner="fake",
        rule_id=rule_id,
        location=Location(path="/x", start_line=0, end_line=0),
        severity=Severity.HIGH,
        message="m",
        raw={},
    )


class FakeTool:
    def __init__(self, name, *, mutating=False, findings=()):
        self.name = name
        self.mutating = mutating
        self._findings = tuple(findings)
        self.ran = False

    def scan(self, scope):
        self.ran = True
        return ScanOutcome(
            findings=self._findings, activity=ToolActivity(units_executed=1, requests_made=1)
        )


def test_mutating_tools_are_skipped_once_the_target_is_down():
    ro = FakeTool("nuclei")  # read-only tier
    schemathesis = FakeTool("schemathesis", mutating=True, findings=[_finding("r1")])
    zap_active = FakeTool("zap-active", mutating=True, findings=[_finding("r2")])

    # Probe: target is up before the first mutating tool, then down.
    calls = {"n": 0}

    def health_check() -> bool:
        calls["n"] += 1
        return calls["n"] < 2  # healthy on first check, down thereafter

    result = run_scan(SCOPE, [ro, schemathesis, zap_active], health_check=health_check)
    by_name = {c.scanner: c for c in result.coverage}

    # First mutating tool ran (target still up); its findings are kept.
    assert schemathesis.ran is True
    assert by_name["schemathesis"].status == "complete"
    # Second mutating tool was skipped — target went down — with an honest reason.
    assert zap_active.ran is False
    assert by_name["zap-active"].status == "incomplete"
    assert "unreachable" in by_name["zap-active"].reason
    # Its would-be findings never entered the result.
    assert {f.rule_id for f in result.findings} == {"r1"}


def test_healthy_target_runs_every_tool_as_before():
    schemathesis = FakeTool("schemathesis", mutating=True, findings=[_finding("r1")])
    result = run_scan(SCOPE, [schemathesis], health_check=lambda: True)
    assert schemathesis.ran is True
    assert result.coverage[0].status == "complete"


def test_a_broken_probe_never_gates_the_scan():
    schemathesis = FakeTool("schemathesis", mutating=True, findings=[_finding("r1")])

    def boom() -> bool:
        raise RuntimeError("probe exploded")

    result = run_scan(SCOPE, [schemathesis], health_check=boom)
    # A probe that errors is ignored — the tool still runs.
    assert schemathesis.ran is True
    assert result.coverage[0].status == "complete"


def test_no_health_check_preserves_prior_behaviour():
    zap_active = FakeTool("zap-active", mutating=True, findings=[_finding("r2")])
    result = run_scan(SCOPE, [zap_active])  # no health_check
    assert zap_active.ran is True
    assert result.coverage[0].status == "complete"
