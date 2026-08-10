"""Runner tests — tool tiering and per-tool failure isolation.

These use fake adapters, so no tool, target, or network is involved.
"""

import threading
import time

import pytest

from app.security.detection.adapters.base import ScannerError
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
    def __init__(self, name, *, mutating=False, findings=(), error=None, hold=0.0, log=None):
        self.name = name
        self.mutating = mutating
        self._findings = tuple(findings)
        self._error = error
        self._hold = hold
        self._log = log if log is not None else []

    def scan(self, scope):
        self._log.append(("start", self.name, time.monotonic()))
        if self._hold:
            time.sleep(self._hold)
        self._log.append(("end", self.name, time.monotonic()))
        if self._error:
            raise self._error
        return ScanOutcome(
            findings=self._findings, activity=ToolActivity(units_executed=100)
        )


def test_findings_from_all_tools_are_aggregated():
    result = run_scan(SCOPE, [FakeTool("a", findings=[_finding("r1")]),
                              FakeTool("b", findings=[_finding("r2")])])
    assert {f.rule_id for f in result.findings} == {"r1", "r2"}
    assert all(c.status == "complete" for c in result.coverage)


def test_one_tool_failing_does_not_lose_the_others():
    result = run_scan(SCOPE, [
        FakeTool("broken", error=ScannerError("broken", "tool not installed")),
        FakeTool("working", findings=[_finding("r1")]),
    ])
    assert [f.rule_id for f in result.findings] == ["r1"]
    by_name = {c.scanner: c for c in result.coverage}
    assert by_name["broken"].status == "incomplete"
    assert "not installed" in by_name["broken"].reason
    assert by_name["working"].status == "complete"


def test_unexpected_exception_is_contained_too():
    result = run_scan(SCOPE, [FakeTool("rogue", error=RuntimeError("boom")),
                              FakeTool("ok", findings=[_finding("r1")])])
    by_name = {c.scanner: c for c in result.coverage}
    assert by_name["rogue"].status == "incomplete"
    assert "boom" in by_name["rogue"].reason
    assert by_name["ok"].status == "complete"


def test_read_only_tools_run_concurrently():
    log = []
    run_scan(SCOPE, [FakeTool("a", hold=0.2, log=log), FakeTool("b", hold=0.2, log=log)])
    # Both started before either finished.
    assert [e[0] for e in log] == ["start", "start", "end", "end"]


def test_mutating_tools_are_serialised():
    # Two tools attacking one live app at once make every result untrustworthy.
    log = []
    run_scan(SCOPE, [
        FakeTool("a", mutating=True, hold=0.1, log=log),
        FakeTool("b", mutating=True, hold=0.1, log=log),
    ])
    assert [e[0] for e in log] == ["start", "end", "start", "end"]


def test_mutating_tools_run_after_read_only_ones():
    log = []
    run_scan(SCOPE, [FakeTool("mut", mutating=True, log=log), FakeTool("ro", log=log)])
    names = [e[1] for e in log if e[0] == "start"]
    assert names == ["ro", "mut"]
