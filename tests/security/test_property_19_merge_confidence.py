"""Property 19: Merge-confidence determinism (security-pipeline).

Exercises ``compute_merge_confidence`` against arbitrary ``MergeConfidenceInputs``
to assert that it returns a defined advisory score in the documented ``[0, 100]``
range (Requirement 13.1) and that it is pure: repeated evaluation on the same
inputs, and evaluation of two separate ``MergeConfidenceInputs`` with identical
field values, yield identical ``Merge_Confidence`` values (Requirement 13.2).

Validates: Requirements 13.1, 13.2
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings

from app.security.governance.merge_confidence import (
    SCORE_MAX,
    SCORE_MIN,
    compute_merge_confidence,
)
from app.security.models import MergeConfidenceInputs
from tests.security.strategies import merge_confidence_inputs


# Feature: security-pipeline, Property 19: For any MergeConfidenceInputs, compute_merge_confidence returns a defined advisory score, and identical inputs always produce identical Merge_Confidence values (the function is pure).
@settings(max_examples=100)
@given(inputs=merge_confidence_inputs())
def test_property_19_returns_defined_advisory_score_in_range(
    inputs: MergeConfidenceInputs,
) -> None:
    result = compute_merge_confidence(inputs)
    # The result is advisory (Requirement 13.3) and its score is a defined
    # float within the documented [0, 100] bounds (Requirement 13.1).
    assert result.advisory is True
    assert isinstance(result.score, float)
    assert SCORE_MIN <= result.score <= SCORE_MAX


# Feature: security-pipeline, Property 19: For any MergeConfidenceInputs, compute_merge_confidence returns a defined advisory score, and identical inputs always produce identical Merge_Confidence values (the function is pure).
@settings(max_examples=100)
@given(inputs=merge_confidence_inputs())
def test_property_19_is_deterministic_on_repeated_evaluation(
    inputs: MergeConfidenceInputs,
) -> None:
    # Purity: evaluating twice on the very same inputs yields an equal
    # Merge_Confidence (Requirement 13.2).
    assert compute_merge_confidence(inputs) == compute_merge_confidence(inputs)


# Feature: security-pipeline, Property 19: For any MergeConfidenceInputs, compute_merge_confidence returns a defined advisory score, and identical inputs always produce identical Merge_Confidence values (the function is pure).
@settings(max_examples=100)
@given(inputs=merge_confidence_inputs())
def test_property_19_identical_inputs_produce_identical_confidence(
    inputs: MergeConfidenceInputs,
) -> None:
    # Two *separate* MergeConfidenceInputs with identical field values must
    # produce equal Merge_Confidence values (Requirement 13.2). ``replace``
    # with no changes yields an equal-but-distinct instance.
    other = replace(inputs)
    assert compute_merge_confidence(inputs) == compute_merge_confidence(other)
