"""Property 12: Triage retention and non-mutation (security-pipeline).

Exercises :func:`app.security.intelligence.triage.attach_triage` — the pure core
that attaches an :class:`~app.security.models.AITriage` to each finding using an
injected :class:`~app.security.protocols.AITriageAdapter`.

For any set of :class:`~app.security.models.Normalized_Finding`s and any triage
results (including ones flagging likely false positives), attaching triage:

* **retains every finding** — the output has exactly one finding per input, in
  the same order, with the same ``finding_id``s (nothing dropped, even when a
  triage flags a likely false positive),
* **labels false positives exactly** — each output finding's
  ``likely_false_positive`` equals its triage's ``likely_false_positive`` flag,
* **does not mutate the Risk_Score** — each output finding's ``risk_score``
  equals the corresponding input finding's ``risk_score``,
* **attaches the triage** — each output finding carries the triage the adapter
  produced for it.

The test injects a FAKE :class:`AITriageAdapter` whose ``triage()`` returns a
Hypothesis-controlled :class:`AITriage` per finding (varying
``likely_false_positive``), so ``attach_triage`` is exercised deterministically
with no network. Findings are generated already scored (``scored=True``) so the
risk-score non-mutation assertion is meaningful.

Validates: Requirements 9.2, 9.3
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.intelligence.triage import attach_triage
from app.security.models import (
    AITriage,
    Location,
    Normalized_Finding,
    Priority,
    Severity,
)
from tests.security.strategies import ai_triages, normalized_findings


class _FakeTriageAdapter:
    """In-memory :class:`AITriageAdapter` returning pre-drawn triages in order.

    ``attach_triage`` calls :meth:`triage` exactly once per finding, in input
    order, so returning triages sequentially deterministically pairs each
    finding with its Hypothesis-controlled :class:`AITriage`.
    """

    def __init__(self, triages: list[AITriage]) -> None:
        self._triages = triages
        self._index = 0

    def triage(self, f: Normalized_Finding, ctx: object) -> AITriage:
        assessment = self._triages[self._index]
        self._index += 1
        return assessment


@st.composite
def _findings_with_triages(
    draw: st.DrawFn,
) -> tuple[list[Normalized_Finding], list[AITriage]]:
    """A scored finding list plus one adapter-produced triage per finding."""
    findings = draw(st.lists(normalized_findings(scored=True), max_size=12))
    triages = [draw(ai_triages()) for _ in findings]
    return findings, triages


# Feature: security-pipeline, Property 12: For any set of Normalized_Findings and any triage results (including ones flagging likely false positives), attaching triage retains every finding (none dropped), labels a finding as a likely false positive exactly when its triage flags it, and leaves each finding's Risk_Score unchanged.
@settings(max_examples=100)
@given(data=_findings_with_triages())
def test_property_12_triage_retention_and_non_mutation(
    data: tuple[list[Normalized_Finding], list[AITriage]],
) -> None:
    findings, triages = data
    adapter = _FakeTriageAdapter(triages)

    result = attach_triage(findings, adapter, ctx=None)

    # (1) Retention: exactly one output per input, same order, same ids.
    assert len(result) == len(findings)
    assert [f.finding_id for f in result] == [f.finding_id for f in findings]

    for original, triaged, assessment in zip(findings, result, triages):
        # (2) False-positive labeling matches the triage flag exactly.
        assert triaged.likely_false_positive == assessment.likely_false_positive
        # (3) Risk_Score is left unchanged by triage attachment.
        assert triaged.risk_score == original.risk_score
        # (4) The adapter-produced triage is attached to the finding.
        assert triaged.triage == assessment


def test_property_12_empty_input() -> None:
    """Empty input yields empty output (edge case)."""
    assert attach_triage([], _FakeTriageAdapter([]), ctx=None) == []


def test_property_12_false_positive_is_labeled_and_retained() -> None:
    """A finding flagged a likely false positive is labeled yet retained."""
    finding = Normalized_Finding(
        finding_id="fp-1",
        rule_identity="rule",
        location=Location(path="a.py", start_line=1, end_line=1),
        severity=Severity.HIGH,
        scanners=frozenset({"bandit"}),
        category="code",
        message="",
        risk_score=7.5,
    )
    fp_triage = AITriage(
        explanation="benign in this repo context",
        priority=Priority.P3,
        suggested_fix="no action needed",
        likely_false_positive=True,
    )

    result = attach_triage([finding], _FakeTriageAdapter([fp_triage]), ctx=None)

    assert len(result) == 1
    assert result[0].likely_false_positive is True
    assert result[0].triage == fp_triage
    # Retained (not dropped) and Risk_Score preserved.
    assert result[0].risk_score == finding.risk_score
