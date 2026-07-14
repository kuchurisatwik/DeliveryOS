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

from typing import Sequence

from app.security.models import (
    ConfigSubstitution,
    GateStatus,
    IntelligenceResult,
    Merge_Confidence,
    Normalized_Finding,
    Pull_Request_Report,
    Quality_Gate,
    ScannerCoverage,
)

#: Coverage status string marking a scanner whose run did not complete (3.4, 14.4).
INCOMPLETE_STATUS = "incomplete"


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
    """Render a single finding as a Markdown bullet line (pure)."""
    loc = finding.location
    where = f"{loc.path}:{loc.start_line}"
    scanners = ", ".join(sorted(finding.scanners)) if finding.scanners else "unknown"
    line = (
        f"- **{finding.rule_identity}** "
        f"({finding.severity.name}, {finding.category}) at `{where}` "
        f"— scanners: {scanners}"
    )
    if finding.unresolved_reason:
        line += f" — {finding.unresolved_reason}"
    return line


def render_security_sections(report: Pull_Request_Report) -> str:
    """Render an assembled report to a Markdown fragment (pure).

    The returned string is appended to the existing ``AI_REPORT.md`` by the
    workflow. It never triggers a merge; it only presents the advisory results
    (Requirement 14.5).
    """
    lines: list[str] = []
    lines.append("\n---\n")
    lines.append("## 🔒 Security Pipeline Report\n")

    if report.failed_layer:
        lines.append(f"> ⚠️ **Pipeline halted:** `{report.failed_layer}` layer failed.\n")

    lines.append(f"**Security Summary:** {report.security_summary}\n")
    if report.testing_summary:
        lines.append(f"**Testing Summary:** {report.testing_summary}\n")

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

    # Fixed findings (14.2).
    lines.append(f"\n### ✅ Fixed Findings ({len(report.fixed_findings)})\n")
    if report.fixed_findings:
        for f in report.fixed_findings:
            lines.append(_format_finding(f) + "\n")
    else:
        lines.append("None.\n")

    # Remaining findings (14.2).
    lines.append(f"\n### ❗ Remaining Findings ({len(report.remaining_findings)})\n")
    if report.remaining_findings:
        for f in report.remaining_findings:
            lines.append(_format_finding(f) + "\n")
    else:
        lines.append("None.\n")

    # Incomplete scanners (14.4).
    lines.append("\n### 🛰️ Scanner Coverage\n")
    if report.incomplete_scanners:
        lines.append("The following scanners did not complete (coverage incomplete):\n")
        for c in report.incomplete_scanners:
            reason = f" — {c.reason}" if c.reason else ""
            lines.append(f"- **{c.scanner}**{reason}\n")
    else:
        lines.append("All scanners completed.\n")

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
