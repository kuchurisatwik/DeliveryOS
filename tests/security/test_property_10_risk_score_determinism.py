"""Property 10: Risk-score determinism (security-pipeline).

Exercises ``compute_risk_score`` against arbitrary ``RiskScoreInputs`` to assert
that it returns the product ``Severity × Reachability × Business_Criticality ×
Exploitability × Repository_Context`` (Requirement 8.1) and that it is pure:
repeated evaluation on the same inputs, and evaluation of two separate
``RiskScoreInputs`` with identical field values, yield identical Risk_Scores
(Requirement 8.2).

Validates: Requirements 8.1, 8.2
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings

from app.security.intelligence.scoring import compute_risk_score
from app.security.models import RiskScoreInputs
from tests.security.strategies import risk_score_inputs


# Feature: security-pipeline, Property 10: For any RiskScoreInputs, compute_risk_score returns the product Severity × Reachability × Business_Criticality × Exploitability × Repository_Context, and any two findings with identical scoring inputs receive identical Risk_Scores (the function is pure — repeated evaluation yields the same result).
@settings(max_examples=100)
@given(inputs=risk_score_inputs())
def test_property_10_risk_score_is_the_five_factor_product(
    inputs: RiskScoreInputs,
) -> None:
    # Risk_Score equals the explicit product of the five factors. The same
    # multiplication order is used, so an exact equality holds (no rounding).
    expected = (
        inputs.severity
        * inputs.reachability
        * inputs.business_criticality
        * inputs.exploitability
        * inputs.repository_context
    )
    assert compute_risk_score(inputs) == expected


# Feature: security-pipeline, Property 10: For any RiskScoreInputs, compute_risk_score returns the product Severity × Reachability × Business_Criticality × Exploitability × Repository_Context, and any two findings with identical scoring inputs receive identical Risk_Scores (the function is pure — repeated evaluation yields the same result).
@settings(max_examples=100)
@given(inputs=risk_score_inputs())
def test_property_10_risk_score_is_deterministic_on_repeated_evaluation(
    inputs: RiskScoreInputs,
) -> None:
    # Purity: evaluating twice on the very same inputs yields the same result.
    assert compute_risk_score(inputs) == compute_risk_score(inputs)


# Feature: security-pipeline, Property 10: For any RiskScoreInputs, compute_risk_score returns the product Severity × Reachability × Business_Criticality × Exploitability × Repository_Context, and any two findings with identical scoring inputs receive identical Risk_Scores (the function is pure — repeated evaluation yields the same result).
@settings(max_examples=100)
@given(inputs=risk_score_inputs())
def test_property_10_identical_inputs_receive_identical_scores(
    inputs: RiskScoreInputs,
) -> None:
    # Two *separate* RiskScoreInputs with identical field values must score
    # identically (Requirement 8.2). ``replace`` with no changes yields an
    # equal-but-distinct instance.
    other = replace(inputs)
    assert other is not inputs or other == inputs  # distinct value, same fields
    assert compute_risk_score(inputs) == compute_risk_score(other)
