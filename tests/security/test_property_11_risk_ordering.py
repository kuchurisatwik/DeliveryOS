"""Property 11: Risk ordering (security-pipeline).

Exercises :func:`app.security.intelligence.scoring.order_by_risk`.

For any set of scored :class:`~app.security.models.Normalized_Finding`s, the
ordered output is a *permutation* of the input (no finding added or dropped) and
is *monotonically non-increasing* in ``Risk_Score``.

The permutation check uses object identity (``id``) multisets: ``order_by_risk``
sorts the very same finding objects, so the output must contain exactly the same
objects as the input with no additions or drops. The monotonicity check walks
consecutive pairs and asserts each ``risk_score`` is >= the next.

Empty and singleton inputs are covered as edge cases, and a small example test
confirms un-scored findings (``risk_score is None``) sort to the end.

Validates: Requirements 8.3
"""

from __future__ import annotations

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.intelligence.scoring import order_by_risk, score_findings
from app.security.models import Location, Normalized_Finding, Severity
from tests.security.strategies import normalized_findings


def _finding(finding_id: str, risk_score: float | None) -> Normalized_Finding:
    """Build a minimal Normalized_Finding with an explicit risk_score."""
    return Normalized_Finding(
        finding_id=finding_id,
        rule_identity="rule",
        location=Location(path="a.py", start_line=1, end_line=1),
        severity=Severity.LOW,
        scanners=frozenset({"bandit"}),
        category="code",
        message="",
        risk_score=risk_score,
    )


def _identity_multiset(findings: tuple[Normalized_Finding, ...]) -> Counter:
    """Multiset of object identities — an exact "same objects" fingerprint."""
    return Counter(id(f) for f in findings)


# Feature: security-pipeline, Property 11: For any set of scored Normalized_Findings, the ordered output is a permutation of the input (no finding added or dropped) and is monotonically non-increasing in Risk_Score.
@settings(max_examples=100)
@given(findings=st.lists(normalized_findings(scored=True), max_size=12))
def test_property_11_risk_ordering(findings: list[Normalized_Finding]) -> None:
    scored = score_findings(tuple(findings))
    ordered = order_by_risk(scored)

    # (1) Permutation: exactly the same finding objects, none added or dropped.
    assert len(ordered) == len(scored)
    assert _identity_multiset(ordered) == _identity_multiset(scored)

    # (2) Monotonically non-increasing in risk_score across the output.
    scores = [f.risk_score for f in ordered]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


@settings(max_examples=100)
@given(findings=st.lists(normalized_findings(scored=True), max_size=12))
def test_property_11_ordering_is_stable_for_equal_scores(
    findings: list[Normalized_Finding],
) -> None:
    """Equal-scored findings keep their original relative order (stable sort)."""
    scored = score_findings(tuple(findings))
    ordered = order_by_risk(scored)

    # For any pair adjacent in the output with equal scores, their original
    # indices must be increasing (stability).
    original_index = {id(f): i for i, f in enumerate(scored)}
    for a, b in zip(ordered, ordered[1:]):
        if a.risk_score == b.risk_score:
            assert original_index[id(a)] < original_index[id(b)]


def test_property_11_empty_input() -> None:
    """Empty input yields empty output (edge case)."""
    assert order_by_risk(()) == ()


def test_property_11_unscored_findings_sort_last() -> None:
    """Un-scored findings (risk_score is None) are ordered after scored ones."""
    high = _finding("high", 9.0)
    low = _finding("low", 1.0)
    unscored = _finding("unscored", None)

    ordered = order_by_risk((low, unscored, high))

    # Same objects preserved (permutation), scored ones ranked by score, and the
    # un-scored finding lands at the end.
    assert _identity_multiset(ordered) == _identity_multiset((low, unscored, high))
    assert [f.finding_id for f in ordered] == ["high", "low", "unscored"]
