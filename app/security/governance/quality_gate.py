"""Layer 4 Quality Gate evaluation — pure function (Requirement 12).

This module holds the deterministic heart of the Governance Layer: given the
SonarQube :class:`~app.security.models.SonarMetrics`, the pipeline's findings,
and the resolved :class:`~app.security.models.QualityGateThresholds`, decide
whether the code satisfies the organizational Quality Gate.

The single public entry point, :func:`evaluate_quality_gate`, is **pure and
deterministic** — it performs no I/O and depends only on its arguments, so
identical inputs always yield an identical :class:`~app.security.models.Quality_Gate`.
Fetching the SonarQube metrics (the only side-effecting part of the gate) is
isolated in :mod:`app.security.governance.sonar_client` so this evaluation stays
trivially testable with in-memory data.

Decision rule (Requirement 12.4 / 12.5):

* Status is :attr:`~app.security.models.GateStatus.PASSED` **iff** every
  configured threshold is satisfied.
* Otherwise status is :attr:`~app.security.models.GateStatus.FAILED` and the
  ``unsatisfied`` tuple contains *exactly* the violated thresholds — one
  :class:`~app.security.models.UnsatisfiedThreshold` per violated threshold,
  and none when the gate passes.

Threshold → metric/finding mapping (Requirement 12.1)
-----------------------------------------------------

Finding-derived thresholds (evaluated against the pipeline ``findings``, each a
:class:`~app.security.models.Normalized_Finding`):

* ``max_critical_findings`` — count of findings whose ``severity`` is
  :attr:`~app.security.models.Severity.CRITICAL`; violated when the count
  exceeds the threshold.
* ``max_leaked_secrets`` — count of findings whose ``category == "secret"``;
  violated when the count exceeds the threshold.
* ``max_blocking_iac_issues`` — count of findings whose ``category == "iac"``
  with a blocking (``HIGH`` or ``CRITICAL``) ``severity``; violated when the
  count exceeds the threshold.

SonarQube-metric-derived thresholds (evaluated against ``metrics``):

* ``min_coverage_percent`` — compared to ``metrics.coverage_percent``; violated
  when coverage is below the minimum.
* ``max_code_smells`` — compared to ``metrics.code_smells`` (skipped when
  ``None``); violated when smells exceed the maximum.
* ``max_technical_debt_minutes`` — compared to ``metrics.technical_debt_minutes``
  (skipped when ``None``); violated when debt exceeds the maximum.
* ``max_security_hotspots`` — compared to ``metrics.security_hotspots``
  (skipped when ``None``); violated when hotspots exceed the maximum.
* ``min_maintainability_rating`` — compared to ``metrics.maintainability_rating``
  (skipped when ``None``); Sonar ratings run ``A`` (best) → ``E`` (worst), so the
  threshold is violated when the actual rating is *worse* than the minimum.

``None``-valued SonarQube thresholds are "unset" and are never evaluated, so they
can never appear in ``unsatisfied``.
"""

from __future__ import annotations

from typing import Sequence

from app.security.models import (
    GateStatus,
    Normalized_Finding,
    Quality_Gate,
    QualityGateThresholds,
    Severity,
    SonarMetrics,
    UnsatisfiedThreshold,
)

#: Blocking severities for Infrastructure-as-Code issues.
_BLOCKING_IAC_SEVERITIES = frozenset({Severity.HIGH, Severity.CRITICAL})

#: Sonar maintainability rating order: ``A`` best → ``E`` worst.
_MAINTAINABILITY_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}


def _rating_rank(rating: str) -> int:
    """Rank a Sonar maintainability rating (``A`` best → ``E`` worst).

    Unknown/malformed ratings rank as the worst possible value so they are
    treated conservatively (i.e. never silently pass a ``min_maintainability``
    requirement). Comparison is case-insensitive.
    """
    return _MAINTAINABILITY_ORDER.get(rating.strip().upper(), max(_MAINTAINABILITY_ORDER.values()) + 1)


def evaluate_quality_gate(
    metrics: SonarMetrics,
    findings: Sequence[Normalized_Finding],
    thresholds: QualityGateThresholds,
) -> Quality_Gate:
    """Evaluate the Quality Gate deterministically (Requirements 12.1, 12.4, 12.5).

    Returns a :class:`~app.security.models.Quality_Gate` whose status is
    ``PASSED`` iff every configured threshold is satisfied; otherwise ``FAILED``
    with ``unsatisfied`` listing exactly the violated thresholds. Pure: no I/O,
    result depends only on the arguments.
    """
    unsatisfied: list[UnsatisfiedThreshold] = []

    # --- Finding-derived thresholds -------------------------------------
    critical_count = sum(1 for f in findings if f.severity is Severity.CRITICAL)
    if critical_count > thresholds.max_critical_findings:
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="max_critical_findings",
                expected=f"<= {thresholds.max_critical_findings}",
                actual=str(critical_count),
            )
        )

    secret_count = sum(1 for f in findings if f.category == "secret")
    if secret_count > thresholds.max_leaked_secrets:
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="max_leaked_secrets",
                expected=f"<= {thresholds.max_leaked_secrets}",
                actual=str(secret_count),
            )
        )

    blocking_iac_count = sum(
        1
        for f in findings
        if f.category == "iac" and f.severity in _BLOCKING_IAC_SEVERITIES
    )
    if blocking_iac_count > thresholds.max_blocking_iac_issues:
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="max_blocking_iac_issues",
                expected=f"<= {thresholds.max_blocking_iac_issues}",
                actual=str(blocking_iac_count),
            )
        )

    # --- SonarQube-metric-derived thresholds ----------------------------
    if metrics.coverage_percent < thresholds.min_coverage_percent:
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="min_coverage_percent",
                expected=f">= {thresholds.min_coverage_percent}",
                actual=str(metrics.coverage_percent),
            )
        )

    if (
        thresholds.max_code_smells is not None
        and metrics.code_smells > thresholds.max_code_smells
    ):
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="max_code_smells",
                expected=f"<= {thresholds.max_code_smells}",
                actual=str(metrics.code_smells),
            )
        )

    if (
        thresholds.max_technical_debt_minutes is not None
        and metrics.technical_debt_minutes > thresholds.max_technical_debt_minutes
    ):
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="max_technical_debt_minutes",
                expected=f"<= {thresholds.max_technical_debt_minutes}",
                actual=str(metrics.technical_debt_minutes),
            )
        )

    if (
        thresholds.max_security_hotspots is not None
        and metrics.security_hotspots > thresholds.max_security_hotspots
    ):
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="max_security_hotspots",
                expected=f"<= {thresholds.max_security_hotspots}",
                actual=str(metrics.security_hotspots),
            )
        )

    if thresholds.min_maintainability_rating is not None and _rating_rank(
        metrics.maintainability_rating
    ) > _rating_rank(thresholds.min_maintainability_rating):
        unsatisfied.append(
            UnsatisfiedThreshold(
                name="min_maintainability_rating",
                expected=f">= {thresholds.min_maintainability_rating.strip().upper()}",
                actual=metrics.maintainability_rating,
            )
        )

    if unsatisfied:
        return Quality_Gate(status=GateStatus.FAILED, unsatisfied=tuple(unsatisfied))
    return Quality_Gate(status=GateStatus.PASSED, unsatisfied=())
