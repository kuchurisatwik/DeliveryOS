"""Layer 4 — Governance Layer.

The Governance Layer enforces the organizational Quality Gate, computes advisory
merge confidence, and assembles the Pull Request report (Requirements 12–14).

This package preserves the design's "pure core, impure shell" split:

* :func:`app.security.governance.quality_gate.evaluate_quality_gate` — the pure,
  deterministic Quality Gate decision over
  :class:`~app.security.models.SonarMetrics`, the pipeline findings, and the
  resolved :class:`~app.security.models.QualityGateThresholds` (Requirement 12).
* :class:`app.security.governance.sonar_client.HttpSonarClient` — the injectable
  :class:`app.security.protocols.SonarClient` adapter that fetches SonarQube
  metrics over HTTP, isolating the network boundary from the pure evaluation.
"""

from app.security.governance.quality_gate import evaluate_quality_gate
from app.security.governance.sonar_client import HttpSonarClient

__all__ = [
    "evaluate_quality_gate",
    "HttpSonarClient",
]
