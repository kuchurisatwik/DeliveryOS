"""Layer 4 Governance — Pull Request report assembly (Requirement 14).

The core of this module is :func:`assemble_pull_request_report`, a **pure**
function that builds an immutable :class:`~app.security.models.Pull_Request_Report`
from the pipeline outputs. Keeping it pure (no I/O, no mutation of its inputs)
lets the design's *Property 21: Report completeness* validate it directly, and
lets the Layer 4 workflow simply hand it the results the earlier layers already
produced.

What the report captures (design "Layer 4 → Pull Request Report", Req 14):

* testing summary + security summary (14.2)
* the fixed and remaining ``Normalized_Finding`` partitions (14.2)
* the advisory ``Merge_Confidence`` (14.2, 13.3)
* the ``Quality_Gate`` status, whose ``unsatisfied`` thresholds are present
  exactly when the gate failed (14.3)
* any scanner whose coverage was marked ``incomplete`` (14.4)
* the ``ConfigSubstitution`` records for malformed config values (15.2)

Crucially, assembling the report is **advisory only**: it records the merge
confidence and gate status but never triggers a merge — the final merge decision
is explicitly left to a human reviewer (Requirement 14.5). This module contains
no merge action of any kind.

:func:`render_security_sections` is a second pure function that renders an
assembled report to a Markdown fragment; the workflow appends that fragment to
the existing ``AI_REPORT.md`` without disturbing the report's prior content.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from app.security.models import (
    ConfigSubstitution,
    Finding,
    GateStatus,
    IntelligenceResult,
    Merge_Confidence,
    Normalized_Finding,
    Pull_Request_Report,
    Quality_Gate,
    ScannerCoverage,
    Severity,
)

#: Coverage status string marking a scanner whose run did not complete (3.4, 14.4).
INCOMPLETE_STATUS = "incomplete"

#: Max length of a scanner failure reason shown in the report. Tool stderr (e.g.
#: CodeQL's multi-hundred-line evaluation log) is truncated so the report stays
#: readable instead of dumping raw logs.
_MAX_REASON_LEN = 200

#: Max number of individual findings listed per section. Findings arrive
#: risk-ordered from Layer 3, so the highest-risk ones are shown; the remainder
#: are summarized by a count line to keep the report readable on large commits.
_MAX_LISTED_FINDINGS = 50


def _short_reason(reason: str | None) -> str:
    """First line of a scanner failure reason, collapsed and length-capped."""
    if not reason:
        return "no reason recorded"
    first = reason.strip().splitlines()[0].strip()
    if len(first) > _MAX_REASON_LEN:
        first = first[: _MAX_REASON_LEN - 1].rstrip() + "…"
    return first


def select_incomplete_scanners(
    coverage: Sequence[ScannerCoverage],
) -> tuple[ScannerCoverage, ...]:
    """Return exactly the coverage entries marked ``incomplete`` (Requirement 14.4).

    A pure filter over the Detection_Layer's per-scanner coverage. Order is
    preserved so the report lists scanners in the order they were recorded.
    """
    return tuple(c for c in coverage if c.status == INCOMPLETE_STATUS)


def build_security_summary(
    intelligence_result: IntelligenceResult,
    quality_gate: Quality_Gate,
    incomplete_scanners: Sequence[ScannerCoverage],
) -> str:
    """Compose a one-line security summary from the Layer 3/4 outputs (Req 14.2).

    Pure and deterministic: identical inputs yield an identical summary string.
    """
    fixed = len(intelligence_result.fixed)
    remaining = len(intelligence_result.remaining)
    gate = quality_gate.status.value
    parts = [
        f"{fixed} finding(s) fixed",
        f"{remaining} finding(s) remaining",
        f"quality gate {gate}",
    ]
    if incomplete_scanners:
        names = ", ".join(c.scanner for c in incomplete_scanners)
        parts.append(f"incomplete scanner coverage: {names}")
    return "; ".join(parts) + "."


def assemble_pull_request_report(
    *,
    commit_sha: str,
    intelligence_result: IntelligenceResult,
    merge_confidence: Merge_Confidence,
    quality_gate: Quality_Gate,
    coverage: Sequence[ScannerCoverage] = (),
    config_substitutions: Sequence[ConfigSubstitution] = (),
    testing_summary: str = "",
    security_summary: str | None = None,
    failed_layer: str | None = None,
) -> Pull_Request_Report:
    """Assemble an immutable :class:`Pull_Request_Report` (Requirement 14).

    This is the pure assembly entry point the Layer 4 workflow calls. It performs
    no I/O and does not mutate its inputs; it only projects the previous layers'
    typed outputs into the report shape.

    Args:
        commit_sha: The ``Commit_SHA`` the report is attached to (14.1).
        intelligence_result: Layer 3 output whose ``fixed``/``remaining``
            partitions become the report's fixed/remaining finding lists (14.2).
        merge_confidence: The advisory :class:`Merge_Confidence` (14.2, 13.3).
        quality_gate: The evaluated :class:`Quality_Gate`; its ``unsatisfied``
            thresholds are surfaced exactly when the status is ``failed`` (14.3).
        coverage: All per-scanner coverage entries; only the ``incomplete`` ones
            appear in the report (14.4).
        config_substitutions: Malformed-config substitution records (15.2).
        testing_summary: Testing summary text (14.2). Defaults to empty.
        security_summary: Security summary text (14.2). When ``None`` a summary is
            derived deterministically from the results via
            :func:`build_security_summary`.
        failed_layer: Name of the layer that failed, if any (1.4). ``None`` on a
            fully successful run.

    Returns:
        A frozen :class:`Pull_Request_Report`. Assembly is advisory only and never
        triggers a merge (Requirement 14.5).
    """
    incomplete = select_incomplete_scanners(coverage)
    if security_summary is None:
        security_summary = build_security_summary(
            intelligence_result, quality_gate, incomplete
        )
    return Pull_Request_Report(
        commit_sha=commit_sha,
        testing_summary=testing_summary,
        security_summary=security_summary,
        fixed_findings=tuple(intelligence_result.fixed),
        remaining_findings=tuple(intelligence_result.remaining),
        merge_confidence=merge_confidence,
        quality_gate=quality_gate,
        incomplete_scanners=incomplete,
        config_substitutions=tuple(config_substitutions),
        failed_layer=failed_layer,
    )


# ---------------------------------------------------------------------------
# Markdown rendering (pure) — appended to the existing AI_REPORT.md
# ---------------------------------------------------------------------------


def _format_finding(finding: Normalized_Finding) -> str:
    """Render a single finding as an informative Markdown block (pure).

    Renders the rule identity, severity/category, location, and scanner
    provenance on a headline line, then — when present — the AI triage
    (priority + explanation + suggested-fix approach) and the AI-generated
    patch diff as a fenced code block. This is what makes advisory mode
    (``SECURITY_VERIFY_PATCHES=false``) useful for the human reviewer:
    every remaining finding carries an AI explanation and a concrete diff
    the reviewer can apply.
    """
    loc = finding.location
    where = f"{loc.path}:{loc.start_line}"
    scanners = ", ".join(sorted(finding.scanners)) if finding.scanners else "unknown"
    parts: list[str] = [
        f"- **{finding.rule_identity}** "
        f"({finding.severity.name}, {finding.category}) at `{where}` "
        f"— scanners: {scanners}"
    ]
    if finding.unresolved_reason:
        parts[0] += f" — {finding.unresolved_reason}"

    # AI triage (priority + explanation + suggested-fix approach).
    triage = finding.triage
    if triage is not None:
        fp = " · likely false positive" if triage.likely_false_positive else ""
        parts.append(f"  - **AI triage:** {triage.priority.name}{fp}")
        if triage.explanation:
            parts.append(f"  - _{triage.explanation.strip()}_")
        if triage.suggested_fix:
            parts.append(f"  - **Suggested fix approach:** {triage.suggested_fix.strip()}")

    # AI candidate patch (unified diff) — the concrete change the reviewer can apply.
    patch = finding.candidate_patch
    if patch is not None and patch.diff.strip():
        diff_body = patch.diff.strip()
        # Cap absurdly long diffs so the report stays readable.
        if len(diff_body) > 4000:
            diff_body = diff_body[:4000].rstrip() + "\n… (truncated)"
        parts.append("  - **Suggested change:**")
        parts.append("    ```diff")
        for line in diff_body.splitlines():
            parts.append(f"    {line}")
        parts.append("    ```")

    return "\n".join(parts)


_SEVERITY_ORDER = (
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
)


def _severity_breakdown(findings: Sequence[Normalized_Finding]) -> str:
    """Render a one-line severity histogram, or 'none' when empty."""
    counts = Counter(f.severity for f in findings)
    present = [f"{s.name}: {counts[s]}" for s in _SEVERITY_ORDER if counts.get(s)]
    return ", ".join(present) if present else "none"


def _scanner_table(
    coverage: Sequence[ScannerCoverage], raw_findings: Sequence[Finding]
) -> list[str]:
    """Render a per-scanner status table: ran/failed + raw finding counts."""
    per_scanner: Counter[str] = Counter(f.scanner for f in raw_findings)
    lines = [
        "| Scanner | Status | Findings | Detail |\n",
        "|---|---|---|---|\n",
    ]
    for c in coverage:
        if c.status == INCOMPLETE_STATUS:
            status = "❌ failed"
            count = "—"
            detail = _short_reason(c.reason)
        else:
            status = "✅ ran"
            count = str(per_scanner.get(c.scanner, 0))
            detail = "completed"
        lines.append(f"| {c.scanner} | {status} | {count} | {detail} |\n")
    return lines


def _append_finding_list(
    lines: list[str], findings: Sequence[Normalized_Finding]
) -> None:
    """Append a bulleted finding list, capped at ``_MAX_LISTED_FINDINGS`` (pure).

    Findings arrive risk-ordered, so the highest-risk ones are listed; when the
    list is longer than the cap, a trailing line summarizes how many were omitted
    so the report stays readable on large commits without hiding the true count.
    """
    if not findings:
        lines.append("None.\n")
        return
    for f in findings[:_MAX_LISTED_FINDINGS]:
        lines.append(_format_finding(f) + "\n")
    omitted = len(findings) - _MAX_LISTED_FINDINGS
    if omitted > 0:
        lines.append(
            f"- _…and {omitted} more (showing the {_MAX_LISTED_FINDINGS} "
            "highest-risk findings; see the severity breakdown above for the "
            "full distribution)._\n"
        )


def render_security_sections(
    report: Pull_Request_Report,
    *,
    coverage: Sequence[ScannerCoverage] = (),
    raw_findings: Sequence[Finding] = (),
    scanned_file_count: int | None = None,
) -> str:
    """Render an assembled report to an informative Markdown fragment (pure).

    Appended to ``AI_REPORT.md`` by the workflow. Advisory only — never triggers a
    merge (Requirement 14.5).

    The optional ``coverage`` (full per-scanner list), ``raw_findings`` (the
    Detection_Layer's aggregated findings) and ``scanned_file_count`` enrich the
    report with a per-scanner status table, a severity breakdown, and the scanned
    scope. When omitted, the function degrades to the report's own fields (so the
    pure Property-21 checks and older callers still work).
    """
    lines: list[str] = []
    lines.append("\n---\n")
    lines.append("## 🔒 Security Pipeline Report\n")

    if report.failed_layer:
        lines.append(
            f"> ⚠️ **Pipeline halted:** the `{report.failed_layer}` layer failed; "
            "results below are partial.\n"
        )

    lines.append(f"**Commit:** `{report.commit_sha}`\n")
    lines.append(f"**Security Summary:** {report.security_summary}\n")
    if scanned_file_count is not None:
        lines.append(f"**Scanned scope:** {scanned_file_count} changed file(s).\n")
    if report.testing_summary:
        lines.append(f"**Testing Summary:** {report.testing_summary}\n")

    # At-a-glance findings by severity across fixed + remaining.
    all_findings = tuple(report.fixed_findings) + tuple(report.remaining_findings)
    lines.append(f"\n**Findings by severity:** {_severity_breakdown(all_findings)}\n")

    # Per-scanner status table (only when coverage is provided).
    lines.append("\n### 🛰️ Scanner Coverage\n")
    if coverage:
        completed = sum(1 for c in coverage if c.status != INCOMPLETE_STATUS)
        lines.append(
            f"{completed}/{len(coverage)} scanner(s) completed. "
            "A ❌ scanner ran but its result could not be collected — treat "
            "its coverage as unknown, not clean.\n\n"
        )
        lines.extend(_scanner_table(coverage, raw_findings))
    elif report.incomplete_scanners:
        lines.append("The following scanners did not complete (coverage incomplete):\n")
        for c in report.incomplete_scanners:
            lines.append(f"- **{c.scanner}** — {_short_reason(c.reason)}\n")
    else:
        lines.append("All scanners completed.\n")

    # Merge confidence — advisory only (13.3, 14.5).
    mc = report.merge_confidence
    lines.append("\n### Merge Confidence (advisory)\n")
    lines.append(f"**Score:** {mc.score} (advisory — human makes the final merge decision)\n")

    # Quality gate + unsatisfied thresholds only when failed (14.3).
    lines.append("\n### Quality Gate\n")
    lines.append(f"**Status:** {report.quality_gate.status.value}\n")
    if report.quality_gate.status is GateStatus.FAILED:
        lines.append("\n**Unsatisfied thresholds:**\n")
        if report.quality_gate.unsatisfied:
            for t in report.quality_gate.unsatisfied:
                lines.append(f"- `{t.name}`: expected {t.expected}, actual {t.actual}\n")
        else:
            lines.append("- (none recorded)\n")
        # Clarify the common coverage-only artifact (no SonarQube / security-only).
        unsat_names = {t.name for t in report.quality_gate.unsatisfied}
        if unsat_names == {"min_coverage_percent"}:
            lines.append(
                "\n> ℹ️ The gate failed only on coverage. In security-only runs "
                "without SonarQube configured, coverage reports as 0 and this "
                "threshold cannot pass — this is a configuration artifact, not a "
                "security finding.\n"
            )

    # Fixed findings (14.2).
    lines.append(f"\n### ✅ Fixed Findings ({len(report.fixed_findings)})\n")
    _append_finding_list(lines, report.fixed_findings)

    # Remaining findings (14.2).
    lines.append(f"\n### ❗ Remaining Findings ({len(report.remaining_findings)})\n")
    _append_finding_list(lines, report.remaining_findings)

    # Config substitutions (15.2).
    if report.config_substitutions:
        lines.append("\n### ⚙️ Configuration Substitutions\n")
        lines.append("Malformed configuration values were replaced by defaults:\n")
        for s in report.config_substitutions:
            lines.append(
                f"- `{s.field}`: provided `{s.provided}`, applied default `{s.applied_default}`\n"
            )

    lines.append(
        "\n_The final merge decision is left to a human reviewer; "
        "this report is advisory and does not trigger a merge._\n"
    )
    return "".join(lines)
