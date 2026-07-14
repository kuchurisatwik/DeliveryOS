"""Property 15: Verification decision (security-pipeline).

Exercises the pure ``decide_verification`` core against controlled baseline /
post-patch finding sets. The verifier accepts a candidate patch (and marks the
target ``fixed``) if and only if the targeted finding is resolved in the
post-patch set AND the patch introduces no finding absent from the baseline;
otherwise it rejects the patch and the original finding stays ``unresolved``.

Validates: Requirements 11.2, 11.3, 11.4
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.intelligence.verify import decide_verification
from app.security.models import (
    CandidatePatch,
    Finding,  # noqa: F401  (kept for clarity of the model surface under test)
    Location,
    Normalized_Finding,
    Severity,
    VerificationOutcome,
)
from tests.security.strategies import baseline_and_post_patch


def _ids(findings) -> set[str]:
    return {f.finding_id for f in findings}


# Feature: security-pipeline, Property 15: For any candidate patch with a baseline finding set and a post-patch finding set, the verifier accepts the patch and marks the target `fixed` if and only if the targeted finding is resolved in the post-patch set AND the patch introduces no finding absent from the baseline; otherwise the patch is rejected and the original finding is marked `unresolved`.
@settings(max_examples=100)
@given(scenario=baseline_and_post_patch())
def test_property_15_verification_decision(scenario: dict) -> None:
    baseline = scenario["baseline"]
    post_patch = scenario["post_patch"]
    target_id = scenario["target_finding_id"]

    # When the baseline is empty the strategy yields no target; pick a stable
    # sentinel id so the patch still targets *something* absent from both sets.
    if target_id is None:
        target_id = "__no_target__"

    patch = CandidatePatch(target_finding_id=target_id, diff="")

    outcome = decide_verification(patch, baseline, post_patch)

    baseline_ids = _ids(baseline)
    post_ids = _ids(post_patch)

    expected_resolved = target_id not in post_ids
    expected_introduced = tuple(sorted(post_ids - baseline_ids))
    expected_accepted = expected_resolved and not expected_introduced

    assert outcome.resolved_target == expected_resolved
    assert outcome.introduced_findings == expected_introduced
    assert outcome.accepted == expected_accepted
    # Acceptance is exactly the conjunction (biconditional with the ground truth).
    assert outcome.accepted == (expected_resolved and len(expected_introduced) == 0)


# Feature: security-pipeline, Property 15: The accept/reject decision is consistent with the strategy's `resolved` / `introduced` ground truth.
@settings(max_examples=100)
@given(scenario=baseline_and_post_patch())
def test_property_15_matches_strategy_ground_truth(scenario: dict) -> None:
    baseline = scenario["baseline"]
    target_id = scenario["target_finding_id"]

    # Only meaningful when the strategy produced a real target from the baseline.
    if target_id is None:
        return

    resolved = scenario["resolved"]
    introduced = scenario["introduced"]

    patch = CandidatePatch(target_finding_id=target_id, diff="")
    outcome = decide_verification(patch, baseline, scenario["post_patch"])

    # A target id may recur elsewhere in the baseline, so ground-truth `resolved`
    # only implies the id was removed when it was unique. Derive the truth from
    # the actual post-patch id set, which is what the verifier is defined over.
    post_ids = _ids(scenario["post_patch"])
    assert outcome.resolved_target == (target_id not in post_ids)

    introduced_ids = tuple(sorted({f.finding_id for f in introduced} - _ids(baseline)))
    assert outcome.introduced_findings == introduced_ids

    # If the strategy resolved the (unique) target and introduced nothing, accept.
    if resolved and target_id not in post_ids and not introduced_ids:
        assert outcome.accepted is True
    # If anything new was introduced, the patch must be rejected.
    if introduced_ids:
        assert outcome.accepted is False


# ---------------------------------------------------------------------------
# Explicit examples (unit-style) covering the three canonical decisions.
# ---------------------------------------------------------------------------


def _nf(finding_id: str) -> Normalized_Finding:
    return Normalized_Finding(
        finding_id=finding_id,
        rule_identity=f"rule::{finding_id}",
        location=Location(path="src/app.py", start_line=1, end_line=2),
        severity=Severity.HIGH,
        scanners=frozenset({"bandit"}),
        category="code",
        message="example",
    )


def test_property_15_example_target_resolved_and_nothing_new_accepted() -> None:
    baseline = [_nf("f1"), _nf("f2")]
    patch = CandidatePatch(target_finding_id="f1", diff="")
    # f1 removed post-patch, no new findings.
    post_patch = [_nf("f2")]

    outcome = decide_verification(patch, baseline, post_patch)

    assert outcome == VerificationOutcome(
        accepted=True, resolved_target=True, introduced_findings=()
    )


def test_property_15_example_target_still_present_rejected() -> None:
    baseline = [_nf("f1"), _nf("f2")]
    patch = CandidatePatch(target_finding_id="f1", diff="")
    # f1 still present -> not resolved -> rejected.
    post_patch = [_nf("f1"), _nf("f2")]

    outcome = decide_verification(patch, baseline, post_patch)

    assert outcome.resolved_target is False
    assert outcome.accepted is False
    assert outcome.introduced_findings == ()


def test_property_15_example_new_finding_introduced_rejected() -> None:
    baseline = [_nf("f1")]
    patch = CandidatePatch(target_finding_id="f1", diff="")
    # f1 resolved, but a brand-new finding f9 appears -> rejected with f9 listed.
    post_patch = [_nf("f9")]

    outcome = decide_verification(patch, baseline, post_patch)

    assert outcome.resolved_target is True
    assert outcome.accepted is False
    assert outcome.introduced_findings == ("f9",)
