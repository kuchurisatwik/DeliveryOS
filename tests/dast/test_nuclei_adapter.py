"""Nuclei adapter tests.

``parse`` is a pure classmethod, so these run against canned JSONL with no binary,
no network, and no target — the same convention the SAST adapter tests use.
"""

import pytest

from app.security.models import Severity
from dast.adapters.base import load_jsonl
from dast.adapters.nuclei_adapter import NucleiAdapter
from dast.models import ScanOutcome, ToolActivity
from dast.runner import _assess_activity

# A realistic slice of nuclei JSONL output: one CVE hit, one exposure, one TLS check.
FIXTURE = """
{"template-id":"CVE-2021-44228","info":{"name":"Apache Log4j2 RCE","severity":"critical","classification":{"cve-id":["cve-2021-44228"],"cwe-id":["cwe-502"]}},"type":"http","host":"https://staging.test","matched-at":"https://staging.test/api/search?q=x","matcher-name":"jndi"}
{"template-id":"git-config","info":{"name":"Git Config Exposure","severity":"medium"},"type":"http","host":"https://staging.test","matched-at":"https://staging.test/.git/config"}
{"template-id":"deprecated-tls","info":{"name":"TLS 1.0 Enabled","severity":"low"},"type":"ssl","host":"staging.test:443","matched-at":"staging.test:443"}
"""


@pytest.fixture()
def findings():
    return NucleiAdapter.parse(load_jsonl(FIXTURE, scanner_name="nuclei"))


def test_every_event_becomes_a_finding(findings):
    assert len(findings) == 3


def test_severity_maps_one_to_one(findings):
    assert [f.severity for f in findings] == [
        Severity.CRITICAL,
        Severity.MEDIUM,
        Severity.LOW,
    ]


def test_rule_id_is_the_stable_template_id_not_the_display_name(findings):
    # Template names get reworded between releases; ids do not. Since the rule id
    # feeds the finding hash, using the name would re-ID everything on a bump.
    assert findings[0].rule_id == "CVE-2021-44228"


def test_location_is_the_endpoint_identity_not_the_raw_url(findings):
    assert findings[0].location.path == "/api/search"
    assert findings[0].location.symbol == "jndi"


def test_category_varies_per_finding(findings):
    # One tool, several kinds of finding — TLS results must not be filed as web bugs.
    assert [f.category for f in findings] == ["dast", "dast", "tls"]


def test_message_carries_the_cve(findings):
    assert "CVE-2021-44228" in findings[0].message


def test_raw_payload_is_retained(findings):
    # The request/response evidence is the first thing a triager wants.
    assert findings[0].raw["matched-at"] == "https://staging.test/api/search?q=x"


def test_spec_paths_templatise_dynamic_segments():
    event = '{"template-id":"x","info":{"severity":"high"},"type":"http","matched-at":"https://s.test/api/users/12345"}'
    parsed = NucleiAdapter.parse(
        load_jsonl(event, scanner_name="nuclei"), spec_paths=("/api/users/{user_id}",)
    )
    assert parsed[0].location.path == "/api/users/{user_id}"


def test_empty_output_is_not_an_error():
    # A dynamic scanner that matched nothing legitimately writes an empty report.
    assert load_jsonl("", scanner_name="nuclei") == []
    assert load_jsonl("\n  \n", scanner_name="nuclei") == []


def test_malformed_line_fails_loudly():
    # Silently dropping findings is the one outcome worse than crashing.
    from app.security.detection.adapters.base import ScannerError

    with pytest.raises(ScannerError):
        load_jsonl('{"ok":1}\nnot json\n', scanner_name="nuclei")


# --------------------------------------------------------------------------- #
# The liveness rule: "found nothing" must be distinguishable from "did nothing"
# --------------------------------------------------------------------------- #


def test_zero_checks_executed_is_incomplete_not_clean():
    outcome = ScanOutcome(findings=(), activity=ToolActivity(units_executed=0))
    status, reason = _assess_activity("nuclei", outcome)
    assert status == "incomplete"
    assert "zero checks" in reason


def test_loading_templates_without_sending_requests_is_incomplete():
    """The exact failure our first live scan hit.

    nuclei resolved no DNS, sent nothing, and exited 0 having "loaded" 6,915
    templates. Counting loaded templates certified that as a clean scan.
    """
    outcome = ScanOutcome(
        findings=(), activity=ToolActivity(units_executed=6915, requests_made=0)
    )
    status, reason = _assess_activity("nuclei", outcome)
    assert status == "incomplete"
    assert "never actually contacted" in reason


def test_all_requests_failing_is_incomplete():
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(units_executed=6915, requests_made=6915, request_errors=6915),
    )
    status, reason = _assess_activity("nuclei", outcome)
    assert status == "incomplete"
    assert "could not reach the target" in reason


def test_majority_of_requests_failing_is_incomplete():
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(units_executed=1000, requests_made=1000, request_errors=700),
    )
    status, reason = _assess_activity("nuclei", outcome)
    assert status == "incomplete"
    assert "did not reach the target" in reason


def test_unknown_activity_with_no_findings_is_incomplete():
    outcome = ScanOutcome(findings=(), activity=ToolActivity(units_executed=None))
    assert _assess_activity("nuclei", outcome)[0] == "incomplete"


def test_templates_loaded_alone_is_not_evidence():
    # No request count at all and nothing found -> unverified, never "clean".
    outcome = ScanOutcome(findings=(), activity=ToolActivity(units_executed=5000))
    assert _assess_activity("nuclei", outcome)[0] == "incomplete"


def test_delivered_requests_with_no_findings_is_complete():
    # Traffic reached the target and nothing matched: a trustworthy clean result.
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(units_executed=5000, requests_made=5000, request_errors=0),
    )
    assert _assess_activity("nuclei", outcome) == ("complete", None)


def test_flood_of_timeouts_invalidates_the_run():
    # Timed-out checks tested nothing, so a clean result would be a lie.
    outcome = ScanOutcome(
        findings=(),
        activity=ToolActivity(units_executed=1000, requests_made=1000, timeouts=400),
    )
    status, reason = _assess_activity("nuclei", outcome)
    assert status == "incomplete"
    assert "rate limit" in reason


def test_stats_parsing_human_format():
    """The ``-stats`` output is the liveness signal; parse the LAST update."""
    from dast.adapters.nuclei_adapter import (
        _STATS_ERRORS,
        _STATS_REQUESTS,
        _extract_last_int,
    )

    stderr = (
        "[0:00:05] | Templates: 6915 | Hosts: 1 | RPS: 90 | Matched: 0 | Errors: 2 | Requests: 450/6915 (6%)\n"
        "[0:00:31] | Templates: 6915 | Hosts: 1 | RPS: 210 | Matched: 3 | Errors: 7 | Requests: 6915/6915 (100%)\n"
    )
    assert _extract_last_int(_STATS_REQUESTS, stderr) == 6915
    assert _extract_last_int(_STATS_ERRORS, stderr) == 7
    assert _extract_last_int(_STATS_REQUESTS, "") is None


def test_stats_parsing_json_format():
    """With ``-jsonl`` nuclei silently switches its stats output to JSON.

    Missing this is what let a scan that sent zero requests report as clean.
    """
    from dast.adapters.nuclei_adapter import (
        _STATS_ERRORS,
        _STATS_REQUESTS,
        _extract_last_int,
    )

    out = (
        '{"duration":"0:01:00","errors":"51","hosts":"1","matched":"3","requests":"2715","rps":"45"}\n'
        '{"duration":"0:01:24","errors":"54","hosts":"1","matched":"3","requests":"3881","rps":"46"}\n'
    )
    assert _extract_last_int(_STATS_REQUESTS, out) == 3881
    assert _extract_last_int(_STATS_ERRORS, out) == 54
