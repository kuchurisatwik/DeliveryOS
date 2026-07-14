"""Layer 3 Risk Scoring and Ordering — pure functions (Requirement 8).

This module holds the deterministic risk-scoring stage of the Intelligence
Layer. It is the **single source of truth** for the ``Risk_Score`` formula: the
design's Data Models sketch a ``compute_risk_score`` alongside
:class:`~app.security.models.RiskScoreInputs`, but ``app/security/models.py``
only defines the immutable input record, so the computation lives here.

Everything in this module is **pure and deterministic** (no I/O, no hidden
state):

* :func:`compute_risk_score` returns the product
  ``Severity × Reachability × Business_Criticality × Exploitability ×
  Repository_Context`` (Requirement 8.1). Because it depends only on its input,
  identical inputs always yield identical scores (Requirement 8.2).
* :func:`score_finding` / :func:`score_findings` build a
  :class:`~app.security.models.RiskScoreInputs` from an enriched
  :class:`~app.security.models.Normalized_Finding` (mapping the
  :class:`~app.security.models.Severity` enum to its numeric value) and attach
  the computed ``risk_score`` via :func:`dataclasses.replace`, returning new
  frozen instances (Requirement 8.2).
* :func:`order_by_risk` returns the findings ordered by ``risk_score``
  descending. The result is a permutation of the input (nothing added or
  dropped) and the sort is *stable*, so findings with equal scores keep their
  original relative order (Requirement 8.3).
"""

from __future__ import annotations

from dataclasses import replace

from app.security.models import (
    Normalized_Finding,
    RiskScoreInputs,
    Severity,
)

#: Neutral multiplier applied for an enrichment factor that is absent (``None``).
#: A value of ``1.0`` leaves the product unchanged, so an un-enriched factor
#: neither inflates nor deflates the ``Risk_Score``.
_NEUTRAL_FACTOR = 1.0


def compute_risk_score(inputs: RiskScoreInputs) -> float:
    """Return the deterministic ``Risk_Score`` product (Requirement 8.1).

    ``Risk_Score = Severity × Reachability × Business_Criticality ×
    Exploitability × Repository_Context``.

    Pure and deterministic: the result depends only on ``inputs``, so two
    findings with identical scoring inputs receive identical scores
    (Requirement 8.2).
    """
    return (
        inputs.severity
        * inputs.reachability
        * inputs.business_criticality
        * inputs.exploitability
        * inputs.repository_context
    )


def _factor(value: float | None) -> float:
    """Coerce an optional enrichment factor to a float, defaulting to neutral.

    ``None`` (an un-enriched factor) maps to :data:`_NEUTRAL_FACTOR`; a present
    ``0.0`` is preserved (it is a meaningful, non-``None`` factor).
    """
    return _NEUTRAL_FACTOR if value is None else float(value)


def build_inputs(finding: Normalized_Finding) -> RiskScoreInputs:
    """Build :class:`RiskScoreInputs` from an enriched ``Normalized_Finding``.

    The :class:`Severity` enum is mapped to its numeric ``value``; each
    enrichment factor is taken from the finding, defaulting to a neutral ``1.0``
    when absent. Pure and deterministic.
    """
    return RiskScoreInputs(
        severity=float(finding.severity.value),
        reachability=_factor(finding.reachability),
        business_criticality=_factor(finding.business_criticality),
        exploitability=_factor(finding.exploitability),
        repository_context=_factor(finding.repository_context),
    )


def score_finding(finding: Normalized_Finding) -> Normalized_Finding:
    """Return a copy of ``finding`` with its ``risk_score`` attached.

    Builds the scoring inputs from the finding's own enrichment fields and
    computes the product via :func:`compute_risk_score`. Because the frozen
    dataclass is immutable, a new instance is returned via
    :func:`dataclasses.replace`. Pure and deterministic: identical scoring
    inputs yield identical ``risk_score`` values (Requirement 8.2).
    """
    score = compute_risk_score(build_inputs(finding))
    return replace(finding, risk_score=score)


def score_findings(
    findings: tuple[Normalized_Finding, ...],
) -> tuple[Normalized_Finding, ...]:
    """Attach ``risk_score`` to every finding, preserving order and count.

    Pure and deterministic; the output has the same length and order as the
    input with each finding's ``risk_score`` populated.
    """
    return tuple(score_finding(f) for f in findings)


def _score_key(finding: Normalized_Finding) -> float:
    """Sort key: a finding's ``risk_score`` treating ``None`` as ``-inf``.

    Un-scored findings (``risk_score is None``) sort to the end deterministically
    rather than raising, keeping :func:`order_by_risk` total over any input.
    """
    return finding.risk_score if finding.risk_score is not None else float("-inf")


def order_by_risk(
    findings: tuple[Normalized_Finding, ...],
) -> tuple[Normalized_Finding, ...]:
    """Return ``findings`` ordered by ``risk_score`` descending (Requirement 8.3).

    The output is a permutation of the input (no finding added or dropped) and
    is monotonically non-increasing in ``risk_score``. The sort is **stable**, so
    findings with equal scores retain their original relative order. Pure and
    deterministic.
    """
    return tuple(sorted(findings, key=_score_key, reverse=True))
