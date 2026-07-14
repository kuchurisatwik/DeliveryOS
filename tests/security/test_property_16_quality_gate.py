"""Property 16: Quality-gate decision (security-pipeline).

Exercises the pure ``evaluate_quality_gate`` core against generated
``SonarMetrics``, findings, and ``QualityGateThresholds``. The gate status is
``PASSED`` if and only if every configured threshold is satisfied; when
``FAILED``, the recorded ``unsatisfied`` set equals exactly the set of violated
thresholds (and is empty exactly when the gate passes).

The expected set of violated threshold *names* is recomputed independently here
using the same threshold -> metric/finding mapping documented in
``app/security/governance/quality_gate.py`` (critical count, secret count,
blocking IaC count, coverage, code smells, technical debt, security hotspots,
maintainability rating; ``None`` SonarQube thresholds are skipped).

Validates: Requirements 12.4, 12.5
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.governance.quality_gate import evaluate_quality_gate
from app.security.models import (
    GateStatus,
    Normalized_Finding,
    QualityGateThresholds,
    Severity,
    SonarMetrics,
)
from tests.security.strategies import (
    normalized_findings,
    quality_gate_thresholds,
    sonar_metrics,
)

# Sonar maintainability rating order (A best -> E worst), mirroring the
# implementation. Unknown ratings rank worst.
_MAINTAINABILITY_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
_BLOCKING_IAC_SEVERITIES = frozenset({Severity.HIGH, Severity.CRITICAL})


def _rating_rank(rating: str) -> int:
    return _MAINTAINABILITY_ORDER.get(
        rating.strip().upper(), max(_MAINTAINABILITY_ORDER.values()) + 1
    )


def _expected_violations(
    metrics: SonarMetrics,
    findings: list[Normalized_Finding],
    thresholds: QualityGateThresholds,
) -> set[str]:
    """Independently recompute the set of violated threshold names."""

    violations: set[str] = set()

    # --- Finding-derived thresholds ---
    critical_count = sum(1 for f in findings if f.severity is Severity.CRITICAL)
    if critical_count > thresholds.max_critical_findings:
        violations.add("max_critical_findings")

    secret_count = sum(1 for f in findings if f.category == "secret")
    if secret_count > thresholds.max_leaked_secrets:
        violations.add("max_leaked_secrets")

    blocking_iac_count = sum(
        1
        for f in findings
        if f.category == "iac" and f.severity in _BLOCKING_IAC_SEVERITIES
    )
    if blocking_iac_count > thresholds.max_blocking_iac_issues:
        violations.add("max_blocking_iac_issues")

    # --- SonarQube-metric-derived thresholds (None thresholds skipped) ---
    if metrics.coverage_percent < thresholds.min_coverage_percent:
        violations.add("min_coverage_percent")

    if (
        thresholds.max_code_smells is not None
        and metrics.code_smells > thresholds.max_code_smells
    ):
        violations.add("max_code_smells")

    if (
        thresholds.max_technical_debt_minutes is not None
        and metrics.technical_debt_minutes > thresholds.max_technical_debt_minutes
    ):
        violations.add("max_technical_debt_minutes")

    if (
        thresholds.max_security_hotspots is not None
        and metrics.security_hotspots > thresholds.max_security_hotspots
    ):
        violations.add("max_security_hotspots")

    if (
        thresholds.min_maintainability_rating is not None
        and _rating_rank(metrics.maintainability_rating)
        > _rating_rank(thresholds.min_maintainability_rating)
    ):
        violations.add("min_maintainability_rating")

    return violations


# Feature: security-pipeline, Property 16: For any (SonarMetrics, findings, QualityGateThresholds), the Quality_Gate status is PASSED iff every threshold is satisfied; when FAILED, the recorded unsatisfied set equals exactly the set of violated thresholds (and is empty exactly when the gate passes).
@settings(max_examples=100)
@given(
    metrics=sonar_metrics(),
    findings=st.lists(normalized_findings(), max_size=8),
    thresholds=quality_gate_thresholds(),
)
def test_property_16_quality_gate_decision(
    metrics: SonarMetrics,
    findings: list[Normalized_Finding],
    thresholds: QualityGateThresholds,
) -> None:
    gate = evaluate_quality_gate(metrics, findings, thresholds)

    expected = _expected_violations(metrics, findings, thresholds)
    actual_names = {u.name for u in gate.unsatisfied}

    # PASSED iff no threshold is violated.
    assert (gate.status is GateStatus.PASSED) == (len(expected) == 0)
    # The recorded unsatisfied set is exactly the violated thresholds.
    assert actual_names == expected
    # Each violated threshold is recorded exactly once (no duplicates).
    assert len(gate.unsatisfied) == len(actual_names)
    # unsatisfied is empty exactly when the gate passes.
    assert (len(gate.unsatisfied) == 0) == (gate.status is GateStatus.PASSED)
