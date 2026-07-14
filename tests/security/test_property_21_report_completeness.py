"""Property 21: Report completeness (Requirements 14.2, 14.3, 14.4).

# Feature: security-pipeline, Property 21: For any IntelligenceResult plus
# governance outputs, the assembled Pull_Request_Report contains a testing
# summary, a security summary, the merge confidence, and fixed/remaining finding
# lists that match the source partitions; its quality_gate status matches the
# evaluated gate with the unsatisfied thresholds present exactly when the gate
# failed; and its incomplete_scanners equals exactly the set of scanners marked
# incomplete.

Validates: Requirements 14.2, 14.3, 14.4
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.governance.report import (
    INCOMPLETE_STATUS,
    assemble_pull_request_report,
)
from app.security.models import (
    GateStatus,
    IntelligenceResult,
    Merge_Confidence,
    Quality_Gate,
    UnsatisfiedThreshold,
)
from tests.security.strategies import (
    identifiers,
    merge_confidence_inputs,
    normalized_findings,
    scanner_coverages,
    text_any,
    text_nonempty,
)


@st.composite
def disjoint_partitions(draw: st.DrawFn):
    """Two disjoint Normalized_Finding lists (fixed vs remaining).

    Disjointness is guaranteed by assigning distinct ``finding_id`` namespaces
    to each partition, so the two source lists never share a finding.
    """

    n_fixed = draw(st.integers(min_value=0, max_value=4))
    n_remaining = draw(st.integers(min_value=0, max_value=4))
    fixed = [
        draw(normalized_findings(finding_id=f"fixed-{i}")) for i in range(n_fixed)
    ]
    remaining = [
        draw(normalized_findings(finding_id=f"rem-{i}")) for i in range(n_remaining)
    ]
    return fixed, remaining


@st.composite
def merge_confidences(draw: st.DrawFn) -> Merge_Confidence:
    return Merge_Confidence(
        score=draw(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
        ),
        inputs=draw(merge_confidence_inputs()),
    )


@st.composite
def unsatisfied_thresholds(draw: st.DrawFn) -> UnsatisfiedThreshold:
    return UnsatisfiedThreshold(
        name=draw(identifiers),
        expected=draw(text_nonempty),
        actual=draw(text_any),
    )


@st.composite
def quality_gates(draw: st.DrawFn) -> Quality_Gate:
    """A Quality_Gate: PASSED with no unsatisfied thresholds, or FAILED with some."""

    if draw(st.booleans()):
        return Quality_Gate(status=GateStatus.PASSED, unsatisfied=())
    unsatisfied = draw(st.lists(unsatisfied_thresholds(), min_size=1, max_size=4))
    return Quality_Gate(status=GateStatus.FAILED, unsatisfied=tuple(unsatisfied))


@settings(max_examples=100)
@given(
    partitions=disjoint_partitions(),
    merge_confidence=merge_confidences(),
    quality_gate=quality_gates(),
    coverage=st.lists(scanner_coverages(), max_size=8),
    commit_sha=identifiers,
    testing_summary=text_nonempty,
)
def test_property_21_report_completeness(
    partitions,
    merge_confidence: Merge_Confidence,
    quality_gate: Quality_Gate,
    coverage: list,
    commit_sha: str,
    testing_summary: str,
) -> None:
    fixed, remaining = partitions
    intelligence_result = IntelligenceResult(
        fixed=tuple(fixed), remaining=tuple(remaining)
    )

    report = assemble_pull_request_report(
        commit_sha=commit_sha,
        intelligence_result=intelligence_result,
        merge_confidence=merge_confidence,
        quality_gate=quality_gate,
        coverage=coverage,
        testing_summary=testing_summary,
    )

    # Fixed/remaining lists match the source partitions exactly (14.2).
    assert report.fixed_findings == tuple(fixed)
    assert report.remaining_findings == tuple(remaining)

    # The advisory merge confidence is present and preserved (14.2).
    assert report.merge_confidence is merge_confidence

    # Testing + security summaries are present, non-empty strings (14.2).
    assert isinstance(report.testing_summary, str) and report.testing_summary
    assert isinstance(report.security_summary, str) and report.security_summary

    # Quality gate matches the evaluated gate; unsatisfied thresholds present
    # exactly when the gate failed (14.3).
    assert report.quality_gate is quality_gate
    assert report.quality_gate.status == quality_gate.status
    if quality_gate.status is GateStatus.FAILED:
        assert len(report.quality_gate.unsatisfied) > 0
    else:
        assert report.quality_gate.unsatisfied == ()

    # incomplete_scanners equals exactly the coverage entries marked incomplete
    # (14.4), preserving order.
    expected_incomplete = tuple(
        c for c in coverage if c.status == INCOMPLETE_STATUS
    )
    assert report.incomplete_scanners == expected_incomplete
    assert all(c.status == INCOMPLETE_STATUS for c in report.incomplete_scanners)


if __name__ == "__main__":  # pragma: no cover
    test_property_21_report_completeness()
