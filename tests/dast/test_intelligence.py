"""Normalisation + deduplication for DAST findings.

The property everything downstream needs is that the same issue at the same
endpoint produces the same ``finding_id`` on every run. Without it there is no
baseline, and "show me only what's new" is impossible.
"""

from app.security.models import Finding, Location, Severity
from dast.adapters.base import make_web_location
from dast.adapters.nuclei_adapter import NucleiAdapter
from dast.adapters.base import load_jsonl
from dast.intelligence import consolidate
from dast.storage import MAX_EVIDENCE_PER_FINDING, normalized_finding_to_dict

SPEC = ("/api/users/{user_id}",)


def _nuclei_finding(url, *, template="git-config", matcher=None, severity=Severity.MEDIUM,
                    category="dast", spec=SPEC):
    return Finding(
        scanner="nuclei",
        rule_id=template,
        location=make_web_location(url, param=matcher, spec_paths=spec),
        severity=severity,
        message=template,
        raw={"matched-at": url, "template-id": template},
        category=category,
    )


# --------------------------------------------------------------------------- #
# Stable identity
# --------------------------------------------------------------------------- #


def test_findings_gain_a_stable_id():
    result = consolidate([_nuclei_finding("https://s.test/.git/config")])
    assert result.findings[0].finding_id.startswith("finding-")


def test_the_same_issue_gets_the_same_id_across_runs():
    a = consolidate([_nuclei_finding("https://s.test/.git/config")])
    b = consolidate([_nuclei_finding("https://s.test/.git/config")])
    assert a.findings[0].finding_id == b.findings[0].finding_id


def test_moving_the_host_does_not_change_the_id():
    # Staging being renamed must not present the whole backlog as new findings.
    a = consolidate([_nuclei_finding("https://staging.test/.git/config")])
    b = consolidate([_nuclei_finding("https://staging-blue.test/.git/config")])
    assert a.findings[0].finding_id == b.findings[0].finding_id


# --------------------------------------------------------------------------- #
# Deduplication — the case that actually fires for a dynamic scanner
# --------------------------------------------------------------------------- #


def test_one_rule_across_many_ids_collapses_to_one_finding():
    """The real win: a rule firing on every user row is one problem, not N.

    URL templatising turns ``/api/users/1..400`` into one endpoint identity, and
    dedup then merges them. Without this a single bug reports as hundreds of
    findings and the baseline is unusable within a week.
    """
    findings = [
        _nuclei_finding(f"https://s.test/api/users/{i}", template="idor-check")
        for i in range(400)
    ]
    result = consolidate(findings)
    assert result.raw_count == 400
    assert len(result.findings) == 1
    assert result.collapsed == 399


def test_different_matchers_on_one_endpoint_stay_separate():
    # Missing CSP and missing HSTS are different problems on the same page.
    result = consolidate([
        _nuclei_finding("https://s.test/", template="missing-headers", matcher="csp"),
        _nuclei_finding("https://s.test/", template="missing-headers", matcher="hsts"),
    ])
    assert len(result.findings) == 2


def test_different_templates_stay_separate():
    result = consolidate([
        _nuclei_finding("https://s.test/", template="a"),
        _nuclei_finding("https://s.test/", template="b"),
    ])
    assert len(result.findings) == 2


def test_scanners_are_unioned_when_findings_merge():
    shared = dict(rule_id="same-rule", severity=Severity.HIGH, message="m",
                  raw={}, category="dast")
    location = Location(path="/api/x", start_line=0, end_line=0)
    result = consolidate([
        Finding(scanner="nuclei", location=location, **shared),
        Finding(scanner="zap", location=location, **shared),
    ])
    assert len(result.findings) == 1
    assert result.findings[0].scanners == frozenset({"nuclei", "zap"})


# --------------------------------------------------------------------------- #
# Evidence survives normalisation
# --------------------------------------------------------------------------- #


def test_evidence_is_kept_and_keyed_by_finding_id():
    # Normalized_Finding has no ``raw`` field, but for a dynamic finding the raw
    # payload IS the proof, so it must not be dropped on the way through.
    findings = [_nuclei_finding(f"https://s.test/api/users/{i}") for i in range(3)]
    result = consolidate(findings)
    finding_id = result.findings[0].finding_id
    assert len(result.evidence[finding_id]) == 3
    assert result.evidence[finding_id][0].raw["matched-at"].endswith("/0")


def test_stored_finding_carries_occurrences_and_capped_evidence():
    findings = [_nuclei_finding(f"https://s.test/api/users/{i}") for i in range(50)]
    result = consolidate(findings)
    finding = result.findings[0]
    payload = normalized_finding_to_dict(finding, result.evidence[finding.finding_id])

    assert payload["finding_id"] == finding.finding_id
    assert payload["occurrences"] == 50          # true scale is recorded...
    assert len(payload["evidence"]) == MAX_EVIDENCE_PER_FINDING  # ...without 50 copies
    assert payload["scanners"] == ["nuclei"]
    assert payload["severity"] == "MEDIUM"


# --------------------------------------------------------------------------- #
# Category must survive — the shared normaliser defaults unknown scanners to
# "code", which would file every web finding as a source-code issue.
# --------------------------------------------------------------------------- #


def test_web_findings_keep_the_dast_category():
    result = consolidate([_nuclei_finding("https://s.test/x", category="dast")])
    assert result.findings[0].category == "dast"


def test_tls_findings_keep_the_tls_category():
    result = consolidate([_nuclei_finding("s.test:443", template="tls", category="tls", spec=())])
    assert result.findings[0].category == "tls"


def test_real_nuclei_output_normalises_end_to_end():
    """A slice of genuine nuclei JSONL, straight through parse -> consolidate."""
    jsonl = "\n".join(
        f'{{"template-id":"http-missing-security-headers","info":{{"name":"Missing header","severity":"info"}},'
        f'"type":"http","matched-at":"https://s.test/","matcher-name":"{m}"}}'
        for m in ("csp", "hsts", "x-frame-options")
    )
    findings = NucleiAdapter.parse(load_jsonl(jsonl, scanner_name="nuclei"))
    result = consolidate(findings)

    assert len(result.findings) == 3            # three distinct missing headers
    assert all(f.category == "dast" for f in result.findings)
    assert len({f.finding_id for f in result.findings}) == 3
