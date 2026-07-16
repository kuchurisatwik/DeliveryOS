"""Integration tests for the six Layer 2 scanner adapters (security-pipeline).

These are deterministic example/integration tests (NOT property-based). The real
scanner tools (bandit, semgrep, codeql, gitleaks, checkov, trivy) are not assumed
to be installed on the machine running the suite, so the adapters are exercised at
their **parse boundary** rather than by spawning subprocesses:

  * each adapter cleanly separates "run the tool subprocess" (``base.run_scanner``)
    from "parse the tool's native output" (each adapter's pure ``parse`` classmethod,
    which for SARIF-emitting tools delegates to ``base.parse_sarif``);
  * feeding fixed, representative canned payloads (native JSON or SARIF, matching the
    shape each adapter expects) to ``parse`` verifies the tool-wiring contract without
    requiring the tool binaries.

For each scanner we assert the parser surfaces representative :class:`Finding`
objects with correct provenance: the originating ``scanner`` name, ``rule_id``,
``location`` (path / lines / symbol), ``severity`` mapped into the shared
:class:`Severity` enum, and ``message``. A couple of scanners are additionally
exercised with their "no findings" payload (empty ``results`` / ``null``).

Finally, one test drives the *subprocess* boundary with a guaranteed-missing binary
to confirm a not-installed tool surfaces as :class:`ScannerError` from
``base.run_scanner`` (the fail-open signal the Layer 2 runner relies on).

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

from __future__ import annotations

import pytest

from app.security.detection.adapters import base
from app.security.detection.adapters.base import ScannerError, run_scanner
from app.security.detection.adapters.bandit_adapter import BanditAdapter
from app.security.detection.adapters.checkov_adapter import CheckovAdapter
from app.security.detection.adapters.codeql_adapter import CodeQLAdapter
from app.security.detection.adapters.gitleaks_adapter import GitleaksAdapter
from app.security.detection.adapters.semgrep_adapter import SemgrepAdapter
from app.security.detection.adapters.trivy_adapter import TrivyAdapter
from app.security.models import Finding, Severity


# --------------------------------------------------------------------------- #
# Bandit (Requirement 4.1) — native JSON `results` array.
# --------------------------------------------------------------------------- #

# Representative of Bandit flagging `subprocess` with shell=True (B602) and an
# eval() use (B307). Fixed canned payload trimmed to the fields the adapter reads.
BANDIT_REPORT = {
    "results": [
        {
            "filename": "app/handlers.py",
            "test_id": "B602",
            "test_name": "subprocess_popen_with_shell_equals_true",
            "issue_severity": "HIGH",
            "issue_text": "subprocess call with shell=True identified.",
            "line_number": 12,
            "line_range": [12, 13],
        },
        {
            "filename": "app/handlers.py",
            "test_id": "B307",
            "test_name": "blacklist",
            "issue_severity": "MEDIUM",
            "issue_text": "Use of possibly insecure function - consider using safer ast.literal_eval.",
            "line_number": 20,
            "line_range": [20],
        },
    ]
}


def test_bandit_adapter_parses_representative_findings():
    findings = BanditAdapter.parse(BANDIT_REPORT)

    assert len(findings) == 2
    assert all(isinstance(f, Finding) for f in findings)
    assert all(f.scanner == "bandit" for f in findings)

    high = findings[0]
    assert high.rule_id == "B602"
    assert high.severity == Severity.HIGH
    assert high.location.path == "app/handlers.py"
    assert high.location.start_line == 12
    assert high.location.end_line == 13
    assert high.location.symbol == "subprocess_popen_with_shell_equals_true"
    assert "shell=True" in high.message

    medium = findings[1]
    assert medium.rule_id == "B307"
    assert medium.severity == Severity.MEDIUM
    # Single-element line_range collapses start == end.
    assert medium.location.start_line == 20
    assert medium.location.end_line == 20


def test_bandit_adapter_no_findings():
    assert BanditAdapter.parse({"results": []}) == []


# --------------------------------------------------------------------------- #
# Semgrep (Requirement 4.2) — native JSON `results` array.
# --------------------------------------------------------------------------- #

SEMGREP_REPORT = {
    "results": [
        {
            "check_id": "python.lang.security.audit.formatted-sql-query",
            "path": "app/db.py",
            "start": {"line": 42},
            "end": {"line": 44},
            "extra": {
                "severity": "ERROR",
                "message": "Detected possible SQL injection via string formatting.",
            },
        }
    ]
}


def test_semgrep_adapter_parses_representative_findings():
    findings = SemgrepAdapter.parse(SEMGREP_REPORT)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.scanner == "semgrep"
    assert finding.rule_id == "python.lang.security.audit.formatted-sql-query"
    # Semgrep ERROR maps into the shared enum as HIGH.
    assert finding.severity == Severity.HIGH
    assert finding.location.path == "app/db.py"
    assert finding.location.start_line == 42
    assert finding.location.end_line == 44
    assert "SQL injection" in finding.message


def test_semgrep_adapter_no_findings():
    assert SemgrepAdapter.parse({"results": []}) == []


# --------------------------------------------------------------------------- #
# CodeQL (Requirement 4.3) — SARIF 2.1.0, parsed via the shared SARIF parser.
# --------------------------------------------------------------------------- #

CODEQL_SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {
                "driver": {
                    "name": "CodeQL",
                    "rules": [
                        {
                            "id": "py/sql-injection",
                            "properties": {"security-severity": "9.8"},
                        }
                    ],
                }
            },
            "results": [
                {
                    "ruleId": "py/sql-injection",
                    "level": "error",
                    "message": {"text": "This query depends on a user-provided value."},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "app/db.py"},
                                "region": {"startLine": 42, "endLine": 42},
                            },
                            "logicalLocations": [
                                {"fullyQualifiedName": "app.db.run_query"}
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}


def test_codeql_adapter_parses_sarif_with_security_severity():
    findings = CodeQLAdapter.parse(CODEQL_SARIF)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.scanner == "codeql"
    assert finding.rule_id == "py/sql-injection"
    # security-severity 9.8 -> CRITICAL (overrides the SARIF `level`).
    assert finding.severity == Severity.CRITICAL
    assert finding.location.path == "app/db.py"
    assert finding.location.start_line == 42
    assert finding.location.symbol == "app.db.run_query"
    assert "user-provided value" in finding.message


def test_codeql_adapter_no_findings():
    empty_sarif = {"version": "2.1.0", "runs": [{"tool": {"driver": {}}, "results": []}]}
    assert CodeQLAdapter.parse(empty_sarif) == []


# --------------------------------------------------------------------------- #
# Gitleaks (Requirement 4.4) — native JSON array (or `null` when clean).
# --------------------------------------------------------------------------- #

GITLEAKS_REPORT = [
    {
        "RuleID": "aws-access-token",
        "File": "config/settings.py",
        "StartLine": 8,
        "EndLine": 8,
        "Description": "AWS Access Key",
    }
]


def test_gitleaks_adapter_parses_representative_findings():
    findings = GitleaksAdapter.parse(GITLEAKS_REPORT)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.scanner == "gitleaks"
    assert finding.rule_id == "aws-access-token"
    # Leaked secrets have no native severity; the adapter reports HIGH.
    assert finding.severity == Severity.HIGH
    assert finding.location.path == "config/settings.py"
    assert finding.location.start_line == 8
    assert finding.location.symbol == "aws-access-token"
    assert finding.message == "AWS Access Key"


def test_gitleaks_adapter_null_payload_is_no_findings():
    # Gitleaks emits `null` (not `[]`) when there are no leaks.
    assert GitleaksAdapter.parse(None) == []


# --------------------------------------------------------------------------- #
# Checkov (Requirement 4.5) — native JSON `results.failed_checks`.
# --------------------------------------------------------------------------- #

CHECKOV_REPORT = {
    "check_type": "terraform",
    "results": {
        "failed_checks": [
            {
                "check_id": "CKV_AWS_20",
                "check_name": "S3 Bucket has an ACL defined which allows public access.",
                "file_path": "infra/s3.tf",
                "file_line_range": [1, 10],
                "resource": "aws_s3_bucket.data",
                "severity": "HIGH",
            }
        ]
    },
}


def test_checkov_adapter_parses_representative_findings():
    findings = CheckovAdapter.parse(CHECKOV_REPORT)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.scanner == "checkov"
    assert finding.rule_id == "CKV_AWS_20"
    assert finding.severity == Severity.HIGH
    assert finding.location.path == "infra/s3.tf"
    assert finding.location.start_line == 1
    assert finding.location.end_line == 10
    assert finding.location.symbol == "aws_s3_bucket.data"
    assert "public access" in finding.message


def test_checkov_adapter_handles_multi_framework_list_payload():
    # Checkov emits a list of result blocks (one per framework) when multiple
    # frameworks are scanned; both the single-object and list shapes are handled.
    payload = [
        CHECKOV_REPORT,
        {"check_type": "cloudformation", "results": {"failed_checks": []}},
    ]
    findings = CheckovAdapter.parse(payload)
    assert len(findings) == 1
    assert findings[0].rule_id == "CKV_AWS_20"


def test_checkov_adapter_handles_double_wrapped_list_payload():
    # Regression: real Checkov emits a single top-level JSON *array*, which
    # base.load_json_multi wraps again into a list — i.e. the parser receives a
    # list-of-list. The previous single-level iteration silently dropped these
    # (0 findings even when Checkov reported failures). It must now flatten them.
    double_wrapped = [
        [
            CHECKOV_REPORT,
            {"check_type": "dockerfile", "results": {"failed_checks": [
                {
                    "check_id": "CKV_DOCKER_3",
                    "check_name": "Ensure that a user is created",
                    "file_path": "Dockerfile",
                    "file_line_range": [1, 1],
                    "resource": "Dockerfile.",
                }
            ]}},
        ]
    ]
    findings = CheckovAdapter.parse(double_wrapped)
    assert len(findings) == 2
    assert {f.rule_id for f in findings} == {"CKV_AWS_20", "CKV_DOCKER_3"}


# --------------------------------------------------------------------------- #
# Trivy (Requirement 4.6) — native JSON `Results` with vulns/misconfig/secrets.
# --------------------------------------------------------------------------- #

TRIVY_REPORT = {
    "Results": [
        {
            "Target": "requirements.txt",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2021-33503",
                    "PkgName": "urllib3",
                    "Severity": "CRITICAL",
                    "Title": "urllib3 denial of service",
                }
            ],
        },
        {
            "Target": "Dockerfile",
            "Misconfigurations": [
                {
                    "ID": "DS002",
                    "Severity": "HIGH",
                    "Title": "Image user should not be 'root'",
                    "CauseMetadata": {"StartLine": 3, "EndLine": 3},
                }
            ],
        },
    ]
}


def test_trivy_adapter_parses_vulnerabilities_and_misconfigurations():
    findings = TrivyAdapter.parse(TRIVY_REPORT)

    assert len(findings) == 2
    assert all(f.scanner == "trivy" for f in findings)

    vuln = next(f for f in findings if f.rule_id == "CVE-2021-33503")
    assert vuln.severity == Severity.CRITICAL
    assert vuln.location.path == "requirements.txt"
    assert vuln.location.symbol == "urllib3"
    assert "denial of service" in vuln.message

    misc = next(f for f in findings if f.rule_id == "DS002")
    assert misc.severity == Severity.HIGH
    assert misc.location.path == "Dockerfile"
    assert misc.location.start_line == 3
    assert misc.location.end_line == 3


def test_trivy_adapter_no_findings():
    assert TrivyAdapter.parse({"Results": []}) == []


# --------------------------------------------------------------------------- #
# Failure path — a missing tool surfaces as ScannerError from run_scanner.
# --------------------------------------------------------------------------- #

def test_run_scanner_missing_tool_raises_scanner_error():
    missing_binary = "definitely-not-an-installed-scanner-xyz"
    with pytest.raises(ScannerError) as exc_info:
        run_scanner([missing_binary, "--version"], scanner_name="bandit")

    err = exc_info.value
    assert err.scanner == "bandit"
    assert "not installed" in err.reason


def test_load_json_on_empty_output_raises_scanner_error():
    # A well-behaved scanner always emits at least an empty report document;
    # empty output means the tool errored before producing one.
    with pytest.raises(ScannerError):
        base.load_json("   ", scanner_name="semgrep")


# --------------------------------------------------------------------------- #
# Trivy category tagging (dependency / iac / secret) — normalization respects it
# --------------------------------------------------------------------------- #

from app.security.intelligence.normalize import normalize as _normalize  # noqa: E402


def test_trivy_tags_categories_per_finding_type():
    """Trivy vuln→dependency, misconfig→iac, secret→secret (not all 'dependency')."""
    payload = {
        "Results": [
            {
                "Target": "requirements.txt",
                "Vulnerabilities": [
                    {"VulnerabilityID": "CVE-1", "Severity": "HIGH", "Title": "vuln"}
                ],
                "Misconfigurations": [
                    {"ID": "AWS-1", "Severity": "HIGH", "Title": "open sg",
                     "CauseMetadata": {"StartLine": 1, "EndLine": 2}}
                ],
                "Secrets": [
                    {"RuleID": "aws-access-key-id", "Severity": "CRITICAL",
                     "Title": "leaked key", "StartLine": 7, "EndLine": 7}
                ],
            }
        ]
    }
    findings = TrivyAdapter.parse(payload)
    cats = {f.rule_id: f.category for f in findings}
    assert cats["CVE-1"] == "dependency"
    assert cats["AWS-1"] == "iac"
    assert cats["aws-access-key-id"] == "secret"

    # Normalization must carry the finding-level category through (not the
    # scanner-wide "dependency" default).
    normalized = {nf.rule_identity: nf.category for nf in (_normalize(f) for f in findings)}
    assert normalized["aws-access-key-id"] == "secret"
    assert normalized["aws-1"] == "iac"
    assert normalized["cve-1"] == "dependency"
