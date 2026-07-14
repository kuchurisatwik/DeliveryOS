"""Layer 3 Deterministic Verification — re-verify AI patches (Requirement 11).

Every AI-proposed :class:`~app.security.models.CandidatePatch` is re-checked by the
deterministic Layer 2 scanners before it can be accepted; AI only *proposes* fixes,
the scanners *decide* whether a fix is real. This module implements that
verification following the design's "pure core, impure shell" separation:

* :func:`decide_verification` — the **pure core**. Given a patch and two finding
  sets (the pre-patch ``baseline`` and the post-patch findings produced by
  re-running the scanners), it deterministically returns a
  :class:`~app.security.models.VerificationOutcome`. It accepts the patch (and the
  caller marks the target ``fixed``) **iff** the targeted finding is resolved in the
  post-patch set AND the patch introduces no finding absent from the baseline
  (Requirement 11.2); otherwise it rejects the patch (Requirement 11.3 — resolution
  not confirmed, or 11.4 — a new finding was introduced). Because it depends only on
  its arguments, the same ``(baseline, post_patch)`` pair always yields the same
  outcome, which is what lets Property 15 (task 7.8) test it with mocked scanner
  results.

* :class:`Verifier` — the **impure shell**. It re-runs the Layer 2 scanners against
  the patched scope (Requirement 11.1) via an *injected* patched-scan callable, then
  normalizes/deduplicates the raw findings so their identities line up with the
  baseline's normalized identities, and hands both sets to :func:`decide_verification`.
  The scan callable is injectable so the whole verifier can be exercised without any
  scanner subprocess or network (the integration test in task 7.9 supplies a fake or
  a fixture-backed scan).

Identity model
--------------
Findings are compared by their normalized ``finding_id`` (a pure function of
``(rule_identity, canonical_location)`` assigned by
:func:`app.security.intelligence.normalize.normalize`). ``baseline`` is expected to
be the pre-patch *normalized* finding set; the post-patch raw scanner findings are
normalized here with the *same* function so ids are directly comparable:

* **target resolved** — ``patch.target_finding_id`` is absent from the post-patch ids.
* **no new finding introduced** — every post-patch id is already present in the
  baseline ids (the set difference ``post_patch − baseline`` is empty).
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from app.security.intelligence.dedup import deduplicate
from app.security.intelligence.normalize import normalize
from app.security.models import (
    CandidatePatch,
    Finding,
    Normalized_Finding,
    ScanScope,
    VerificationOutcome,
)

#: Signature of the injected impure boundary: apply ``patch`` to the patched scope,
#: re-run the Layer 2 scanners, and return the raw :class:`Finding`s. In production
#: this wraps the :class:`~app.security.detection.runner.DetectionStage` adapters
#: (mirroring the validate-after-repair approach in ``app/workflows/quality_stages.py``);
#: in tests it is a fake mapping ``(patch, scope) -> findings``.
PatchedScanner = Callable[[CandidatePatch, ScanScope], Sequence[Finding]]


def decide_verification(
    patch: CandidatePatch,
    baseline: Iterable[Normalized_Finding],
    post_patch: Iterable[Normalized_Finding],
) -> VerificationOutcome:
    """Decide whether a candidate patch is accepted (Requirements 11.2–11.4).

    Pure and deterministic: the outcome depends only on ``patch.target_finding_id``
    and the ``finding_id`` sets of ``baseline`` and ``post_patch``. No I/O, no hidden
    state — this is the function Property 15 exercises with mocked scanner results.

    Decision rule::

        resolved_target = target_finding_id ∉ post_patch ids
        introduced      = post_patch ids − baseline ids        (findings absent from baseline)
        accepted        = resolved_target AND introduced is empty

    Args:
        patch: The candidate patch under verification; its ``target_finding_id``
            names the finding the patch is meant to resolve.
        baseline: The pre-patch normalized finding set (the identities that existed
            before the patch was applied).
        post_patch: The normalized finding set produced by re-running the scanners
            against the patched code.

    Returns:
        A :class:`VerificationOutcome` recording ``accepted`` (True iff the target is
        resolved and nothing new was introduced), ``resolved_target`` (whether the
        targeted finding is absent post-patch), and ``introduced_findings`` (the
        sorted ids of any post-patch findings absent from the baseline).
    """
    baseline_ids = {f.finding_id for f in baseline}
    post_ids = {f.finding_id for f in post_patch}

    resolved_target = patch.target_finding_id not in post_ids
    introduced = tuple(sorted(post_ids - baseline_ids))

    accepted = resolved_target and not introduced
    return VerificationOutcome(
        accepted=accepted,
        resolved_target=resolved_target,
        introduced_findings=introduced,
    )


class Verifier:
    """Re-runs the Layer 2 scanners to deterministically verify a patch (Req 11).

    The side-effecting boundary (applying the patch + running scanners) is confined
    to the injected :data:`PatchedScanner`; the accept/reject decision is delegated
    to the pure :func:`decide_verification`, keeping this class thin and the decision
    logic independently testable.
    """

    def __init__(self, scan_patched: PatchedScanner) -> None:
        """Create a verifier.

        Args:
            scan_patched: Injected callable that applies a patch to the patched
                scope, re-runs the Layer 2 scanners, and returns the raw findings.
                Injecting it keeps :meth:`verify` free of subprocess/network
                dependencies so it can be exercised with fakes or fixtures.
        """
        self._scan_patched = scan_patched

    def verify(
        self,
        patch: CandidatePatch,
        baseline: Sequence[Normalized_Finding],
        scope: ScanScope,
    ) -> VerificationOutcome:
        """Re-run the scanners against the patched scope and decide (Req 11.1–11.4).

        Re-runs the scanners (impure, Requirement 11.1), normalizes and deduplicates
        the raw post-patch findings with the *same* :func:`normalize` used to build
        the baseline so their identities are comparable, then defers to the pure
        :func:`decide_verification` for the accept/reject decision.

        Args:
            patch: The candidate patch to verify.
            baseline: The pre-patch normalized finding set.
            scope: The :class:`ScanScope` to re-scan (the patched code surface).

        Returns:
            The :class:`VerificationOutcome` from :func:`decide_verification`.
        """
        raw_post: Sequence[Finding] = self._scan_patched(patch, scope)
        post_patch = deduplicate([normalize(f) for f in raw_post])
        return decide_verification(patch, baseline, post_patch)
