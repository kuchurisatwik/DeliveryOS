"""Tests for Phase-1 cross-tool correlation, baseline/delta mode, and njsscan."""

from __future__ import annotations

import json

from app.security.detection.adapters.njsscan_adapter import NjsscanAdapter
from app.security.intelligence import baseline as bl
from app.security.intelligence.correlate import classify, correlate
from app.security.models import Location, Normalized_Finding, Severity


def _nf(rule_identity, path, line, severity=Severity.MEDIUM, scanner="semgrep", message=""):
    return Normalized_Finding(
        finding_id=f"id-{rule_identity}-{path}-{line}-{scanner}",
        rule_identity=rule_identity,
        location=Location(path=path, start_line=line, end_line=line),
        severity=severity,
        scanners=frozenset({scanner}),
        category="code",
        message=message,
        defaults_applied=(),
    )


# --------------------------------------------------------------------------- #
# Correlation
# --------------------------------------------------------------------------- #
def test_classify_recognizes_common_classes():
    assert classify(_nf("py/command-line-injection", "a.py", 1)) == "command-injection"
    assert classify(_nf("b602", "a.py", 1)) == "command-injection"
    assert classify(_nf("py/sql-injection", "a.py", 1)) == "sql-injection"
    assert classify(_nf("b324", "a.py", 1)) == "weak-crypto"
    assert classify(_nf("generic-api-key", "a.env", 1)) == "hardcoded-secret"
    assert classify(_nf("some-unknown-rule", "a.py", 1)) == ""


def test_correlate_merges_same_class_same_location_across_tools():
    # One shell-injection line reported by 4 different tools/rules.
    findings = [
        _nf("py/command-line-injection", "app.py", 23, Severity.CRITICAL, "codeql"),
        _nf("subprocess-shell-true", "app.py", 23, Severity.HIGH, "semgrep"),
        _nf("dangerous-subprocess-use", "app.py", 23, Severity.HIGH, "semgrep"),
        _nf("b602", "app.py", 23, Severity.HIGH, "bandit"),
    ]
    merged = correlate(findings)
    assert len(merged) == 1
    m = merged[0]
    # Highest severity wins as the base.
    assert m.severity == Severity.CRITICAL
    # All contributing scanners are unioned (corroboration visible).
    assert m.scanners == frozenset({"codeql", "semgrep", "bandit"})


def test_correlate_keeps_distinct_classes_separate():
    findings = [
        _nf("py/sql-injection", "app.py", 30, Severity.HIGH, "codeql"),
        _nf("b324", "app.py", 30, Severity.MEDIUM, "bandit"),  # weak-crypto, same line
    ]
    merged = correlate(findings)
    # Different vuln classes at the same line must NOT be merged.
    assert len(merged) == 2


def test_correlate_passes_through_unclassified():
    findings = [
        _nf("weird-rule-a", "x.py", 5, Severity.LOW, "semgrep"),
        _nf("weird-rule-b", "x.py", 5, Severity.LOW, "semgrep"),
    ]
    merged = correlate(findings)
    assert len(merged) == 2  # unclassified are never over-merged


# --------------------------------------------------------------------------- #
# Baseline / delta
# --------------------------------------------------------------------------- #
def test_fingerprint_is_line_independent():
    a = _nf("py/sql-injection", "app.py", 30)
    b = _nf("py/sql-injection", "app.py", 99)  # same rule+file, different line
    assert bl.fingerprint(a) == bl.fingerprint(b)


def test_filter_new_hides_known_and_keeps_new():
    known_finding = _nf("py/sql-injection", "app.py", 30)
    new_finding = _nf("py/command-line-injection", "app.py", 23)
    baseline = {bl.fingerprint(known_finding)}
    result = bl.filter_new([known_finding, new_finding], baseline)
    assert result == [new_finding]


def test_empty_baseline_returns_all():
    fs = [_nf("r1", "a.py", 1), _nf("r2", "b.py", 2)]
    assert bl.filter_new(fs, set()) == fs


def test_write_then_load_baseline_roundtrip(tmp_path):
    findings = [_nf("py/sql-injection", "app.py", 30), _nf("b602", "app.py", 23)]
    path = str(tmp_path / "baseline.json")
    bl.write_baseline(path, findings)
    loaded = bl.load_baseline(path)
    assert loaded == set(bl.compute_fingerprints(findings))


def test_load_missing_baseline_is_empty():
    assert bl.load_baseline("/no/such/baseline.json") == set()


def test_resolve_baseline_path_disabled():
    assert bl.resolve_baseline_path("/ws", "") is None
    assert bl.resolve_baseline_path("/ws", "off") is None


# --------------------------------------------------------------------------- #
# njsscan parsing
# --------------------------------------------------------------------------- #
NJSSCAN_REPORT = {
    "errors": [],
    "nodejs": {
        "node_username": {
            "files": [
                {"file_path": "server.js", "match_lines": [14, 14], "match_string": "..."}
            ],
            "metadata": {
                "severity": "ERROR",
                "cwe": "CWE-89",
                "description": "SQL Injection via string concatenation",
            },
        }
    },
    "templates": {},
    "secrets": {},
}


def test_njsscan_parses_findings():
    findings = NjsscanAdapter.parse(NJSSCAN_REPORT)
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner == "njsscan"
    assert f.rule_id == "node_username"
    assert f.severity == Severity.HIGH  # ERROR -> HIGH
    assert f.location.path == "server.js"
    assert f.location.start_line == 14
    assert "SQL Injection" in f.message


def test_njsscan_no_findings():
    assert NjsscanAdapter.parse({"nodejs": {}, "templates": {}, "secrets": {}}) == []
