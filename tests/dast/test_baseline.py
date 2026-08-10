"""Baseline tests.

The diff itself is the easy part. The two rules that keep the baseline honest are
DAST-specific, and both are about *not guessing*:

* a finding that disappeared may have been fixed — or may simply not have been
  looked at this run;
* a scan that reached nothing must never be allowed to overwrite what we know.
"""

import pytest

from app.security.models import Location, Normalized_Finding, Severity
from dast import baseline


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline.dast_settings, "DAST_STATE_DIR", str(tmp_path))


def _finding(finding_id: str, path: str = "/api/x") -> Normalized_Finding:
    return Normalized_Finding(
        finding_id=finding_id,
        rule_identity="some-rule",
        location=Location(path=path, start_line=0, end_line=0),
        severity=Severity.HIGH,
        scanners=frozenset({"nuclei"}),
        category="dast",
        message="m",
    )


# --------------------------------------------------------------------------- #
# Target identity
# --------------------------------------------------------------------------- #


def test_trailing_slash_is_the_same_target():
    assert baseline.target_key("https://s.test") == baseline.target_key("https://s.test/")


def test_host_case_does_not_split_the_baseline():
    assert baseline.target_key("https://S.Test") == baseline.target_key("https://s.test")


def test_different_ports_are_different_targets():
    assert baseline.target_key("http://s.test:3000") != baseline.target_key("http://s.test:4000")


# --------------------------------------------------------------------------- #
# The diff
# --------------------------------------------------------------------------- #


def test_first_scan_reports_nothing_as_new():
    # Everything is "new" on a first scan, which makes the word meaningless.
    result = baseline.diff({}, [_finding("a"), _finding("b")], coverage_complete=True)
    assert result.is_first_scan is True
    assert result.new == ()
    assert set(result.known) == {"a", "b"}


def test_only_genuinely_new_findings_are_flagged():
    result = baseline.diff(
        {"a": {}}, [_finding("a"), _finding("b")], coverage_complete=True
    )
    assert result.new == ("b",)
    assert result.known == ("a",)


def test_disappeared_finding_is_resolved_when_coverage_is_complete():
    result = baseline.diff({"a": {}, "b": {}}, [_finding("a")], coverage_complete=True)
    assert result.resolved == ("b",)
    assert result.unverified == ()


def test_disappeared_finding_is_only_unverified_when_coverage_is_incomplete():
    """The rule that separates a trustworthy baseline from a lying one.

    In SAST a finding vanishing means the code changed. In DAST it may mean the
    scanner never reached that endpoint — expired auth, a rate limiter, a slow
    boot. Calling that "resolved" would quietly close real vulnerabilities.
    """
    result = baseline.diff({"a": {}, "b": {}}, [_finding("a")], coverage_complete=False)
    assert result.resolved == ()
    assert result.unverified == ("b",)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def test_round_trip():
    baseline.update("https://s.test", [_finding("a"), _finding("b")])
    assert set(baseline.load("https://s.test")) == {"a", "b"}


def test_baseline_is_per_target():
    baseline.update("https://a.test", [_finding("a")])
    baseline.update("https://b.test", [_finding("b")])
    assert set(baseline.load("https://a.test")) == {"a"}
    assert set(baseline.load("https://b.test")) == {"b"}


def test_first_seen_is_preserved_across_scans():
    # How long an issue has been outstanding is the useful number; resetting it
    # every scan would make everything look like it appeared today.
    baseline.update("https://s.test", [_finding("a")])
    first = baseline.load("https://s.test")["a"]["first_seen"]

    previous = baseline.load("https://s.test")
    baseline.update("https://s.test", [_finding("a")], previous=previous)
    second = baseline.load("https://s.test")["a"]

    assert second["first_seen"] == first
    assert second["last_seen"] >= first


def test_resolved_findings_are_dropped():
    baseline.update("https://s.test", [_finding("a"), _finding("b")])
    previous = baseline.load("https://s.test")
    baseline.update("https://s.test", [_finding("a")], previous=previous, drop=("b",))
    assert set(baseline.load("https://s.test")) == {"a"}


def test_unverified_findings_are_retained():
    """Forgetting an unverified finding would make it reappear as new next run."""
    baseline.update("https://s.test", [_finding("a"), _finding("b")])
    previous = baseline.load("https://s.test")

    # 'b' was not seen this run, but coverage was incomplete -> nothing dropped.
    result = baseline.diff(previous, [_finding("a")], coverage_complete=False)
    baseline.update(
        "https://s.test", [_finding("a")], previous=previous, drop=result.resolved
    )

    assert set(baseline.load("https://s.test")) == {"a", "b"}


def test_missing_baseline_reads_as_empty():
    assert baseline.load("https://never-scanned.test") == {}
