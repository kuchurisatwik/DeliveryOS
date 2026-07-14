"""Layer 4 Merge Confidence — a pure, deterministic function (Requirement 13).

This module is the **single source of truth** for the advisory merge-confidence
score. The design's Layer 4 section specifies
``compute_merge_confidence(inputs) -> Merge_Confidence`` derived deterministically
from testing confidence, security confidence, coverage, remaining findings, and
Quality Gate status (13.1); identical inputs must produce identical values
(13.2); and the result is recorded as **advisory** and never triggers an
automatic merge (13.3).

Everything here is **pure and deterministic** — no I/O, no hidden state, no
randomness. :func:`compute_merge_confidence` depends only on its
:class:`~app.security.models.MergeConfidenceInputs`, so two identical inputs
always yield identical :class:`~app.security.models.Merge_Confidence` values
(Property 19 / Requirement 13.2). The function only *computes a number*; it has
no capability to merge anything (Requirement 13.3).

Weighting scheme (advisory 0–100 score)
----------------------------------------
The score is a weighted sum of four positive contributions minus a penalty for
unresolved findings, clamped to ``[0, 100]``. The positive weights sum to 100 so
a perfectly clean input (full testing/security confidence, full coverage, gate
passed, no remaining findings) scores exactly ``100``:

===========================  ======  =======================================
Dimension                    Weight  Contribution
===========================  ======  =======================================
Testing confidence            40     ``testing_confidence * 40``
Security confidence           30     ``security_confidence * 30``
Coverage                      15     ``min(coverage_percent, 100) / 100 * 15``
Quality Gate status           15     ``15`` if ``passed`` else ``0``
---------------------------  ------  ---------------------------------------
Remaining findings (penalty)  −20    ``min(remaining_findings, 10) * 2``
===========================  ======  =======================================

Rationale: testing and security confidence dominate (70 of 100 points),
mirroring the deterministic-first philosophy that discovered-and-verified
security state and test results matter most. Coverage and a passed Quality Gate
each contribute a smaller fixed slice. Remaining (unresolved) findings apply a
graduated penalty — each remaining finding subtracts 2 points, saturating at 10
findings (−20) so the penalty never dominates the whole score into meaningless
territory. Because every term is a deterministic function of the inputs and the
final value is clamped, the result is stable and reproducible.

This extends the historical ``IterationController.calculate_merge_confidence``
weighting (30 build + 50 test-pass + 20 coverage) by folding build/test signal
into ``testing_confidence`` and adding the security dimension
(``security_confidence`` + Quality Gate + remaining findings).
"""

from __future__ import annotations

from app.security.models import (
    GateStatus,
    Merge_Confidence,
    MergeConfidenceInputs,
)

# --- Weighting constants (positive weights sum to 100) ----------------------

#: Points allotted to testing confidence (build + test-pass signal).
TESTING_WEIGHT = 40.0
#: Points allotted to security confidence (findings resolved / verified state).
SECURITY_WEIGHT = 30.0
#: Points allotted to code coverage.
COVERAGE_WEIGHT = 15.0
#: Points awarded when the Quality Gate has passed (0 when failed).
QUALITY_GATE_WEIGHT = 15.0

#: Points subtracted per remaining (unresolved) finding.
PENALTY_PER_FINDING = 2.0
#: Maximum number of remaining findings that contribute to the penalty. Beyond
#: this the penalty saturates so it never dwarfs the whole score.
PENALTY_FINDING_CAP = 10

#: Advisory score bounds.
SCORE_MIN = 0.0
SCORE_MAX = 100.0


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))


def compute_merge_confidence(inputs: MergeConfidenceInputs) -> Merge_Confidence:
    """Return the advisory :class:`Merge_Confidence` for ``inputs``.

    Pure and deterministic (Requirement 13.2 / Property 19): the score is a
    weighted sum of testing confidence, security confidence, coverage, and
    Quality Gate status, minus a graduated penalty for remaining findings,
    clamped to ``[0, 100]`` (Requirement 13.1). The returned value is marked
    ``advisory=True`` and this function performs no merge action of any kind
    (Requirement 13.3) — it only computes a number.
    """
    testing = _clamp(inputs.testing_confidence, 0.0, 1.0) * TESTING_WEIGHT
    security = _clamp(inputs.security_confidence, 0.0, 1.0) * SECURITY_WEIGHT
    coverage = _clamp(inputs.coverage_percent, 0.0, 100.0) / 100.0 * COVERAGE_WEIGHT
    gate = QUALITY_GATE_WEIGHT if inputs.quality_gate_status is GateStatus.PASSED else 0.0

    remaining = max(inputs.remaining_findings, 0)
    penalty = min(remaining, PENALTY_FINDING_CAP) * PENALTY_PER_FINDING

    score = _clamp(testing + security + coverage + gate - penalty, SCORE_MIN, SCORE_MAX)

    return Merge_Confidence(score=round(score, 2), inputs=inputs, advisory=True)
