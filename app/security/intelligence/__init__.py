"""Layer 3 — Intelligence Layer deterministic core.

This package holds the *pure*, deterministic stages of the Intelligence Layer:
normalization, deduplication, context enrichment, and risk scoring/ordering. Each
stage is expressed as a pure function over the immutable data models in
:mod:`app.security.models` so it can be exhaustively validated with property-based
tests. The non-deterministic AI stages (triage, repair) and the deterministic
verification re-run live in sibling modules and are bracketed by these pure
transforms.

Public surface:

* :func:`app.security.intelligence.normalize.normalize` — convert a raw
  :class:`~app.security.models.Finding` into a
  :class:`~app.security.models.Normalized_Finding` conforming to the
  ``Common_Schema`` (Requirement 5).
* :func:`app.security.intelligence.dedup.deduplicate` — collapse
  :class:`~app.security.models.Normalized_Finding`s sharing a
  ``(rule_identity, canonical_location)`` key into one, unioning their
  originating scanners (Requirement 6).
* :func:`app.security.intelligence.enrich.enrich` — attach contextual signals
  (reachability, business criticality, exposure, auth context) plus the
  remaining scoring inputs to each finding (Requirement 7).
* :func:`app.security.intelligence.scoring.compute_risk_score` — the
  deterministic ``Risk_Score`` product (Requirement 8.1); with
  :func:`~app.security.intelligence.scoring.score_finding`,
  :func:`~app.security.intelligence.scoring.score_findings`, and
  :func:`~app.security.intelligence.scoring.order_by_risk` for attaching scores
  and ordering findings by risk descending (Requirements 8.2, 8.3).
"""

from app.security.intelligence.dedup import deduplicate
from app.security.intelligence.enrich import enrich
from app.security.intelligence.normalize import normalize
from app.security.intelligence.scoring import (
    build_inputs,
    compute_risk_score,
    order_by_risk,
    score_finding,
    score_findings,
)

__all__ = [
    "deduplicate",
    "enrich",
    "normalize",
    "compute_risk_score",
    "build_inputs",
    "score_finding",
    "score_findings",
    "order_by_risk",
]
