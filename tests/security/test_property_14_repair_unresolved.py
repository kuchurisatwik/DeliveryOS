"""Property 14: Repair-unresolved handling (security-pipeline).

Exercises the pure core :func:`app.security.intelligence.repair.select_repairs`
with an injected *fake* :class:`app.security.protocols.AIRepairAdapter`, so the
property can be checked deterministically with no network.

Design reference — Property 14:
    *For any* finding for which AI_Repair yields no patch, that finding is
    marked ``unresolved`` and carries a recorded ``unresolved_reason``.

"AI_Repair yields no patch" has two shapes in the design (both handled by
:func:`select_repairs`, Requirement 10.4):

* the adapter returns ``None`` (declined a safe patch), and
* the adapter *raises* (adapter error).

In both cases every **repair-eligible** finding (scanner-confirmed and not
labeled a likely false positive) for which no patch was produced must come back
with ``status == FindingStatus.UNRESOLVED`` and a non-empty ``unresolved_reason``.

The generated findings are post-processed to guarantee eligibility (unique
scanner-confirmed ids, ``likely_false_positive=False``) so the adapter's
per-finding decision fully determines the expected outcome. The empty finding
list is a reachable edge case.

Validates: Requirements 10.4
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.intelligence.repair import (
    NO_PATCH_REASON,
    REPAIR_ERROR_REASON,
    is_repair_eligible,
    select_repairs,
)
from app.security.models import (
    CandidatePatch,
    FindingStatus,
    Normalized_Finding,
)
from tests.security.strategies import normalized_findings


# --------------------------------------------------------------------------- #
# Fake AIRepairAdapters (in-memory; no network) — satisfy the AIRepairAdapter
# protocol structurally via a `repair(f, ctx)` method.
# --------------------------------------------------------------------------- #


class FakeRepairAdapter:
    """Returns ``None`` for findings whose id is in ``no_patch_ids``.

    For every other finding it returns a proposal-only :class:`CandidatePatch`
    (with a deliberately mismatched ``target_finding_id`` to prove ``select_repairs``
    re-binds the association). ``ctx`` is ignored — the decision is data-driven.
    """

    def __init__(self, no_patch_ids: set[str]) -> None:
        self.no_patch_ids = no_patch_ids

    def repair(self, f: Normalized_Finding, ctx: object) -> CandidatePatch | None:
        if f.finding_id in self.no_patch_ids:
            return None
        return CandidatePatch(target_finding_id="__unrelated__", diff="a fix")


class RaisingRepairAdapter:
    """Raises for findings whose id is in ``raise_ids`` (models an adapter error).

    Non-raising findings receive a patch, so the test can mix raising and
    patch-producing behavior in a single run.
    """

    def __init__(self, raise_ids: set[str]) -> None:
        self.raise_ids = raise_ids

    def repair(self, f: Normalized_Finding, ctx: object) -> CandidatePatch | None:
        if f.finding_id in self.raise_ids:
            raise RuntimeError("simulated adapter failure")
        return CandidatePatch(target_finding_id=f.finding_id, diff="a fix")


# --------------------------------------------------------------------------- #
# Strategy: eligible findings with unique ids + a per-finding "no patch" flag.
# --------------------------------------------------------------------------- #


@st.composite
def eligible_findings_with_flags(
    draw: st.DrawFn,
) -> tuple[list[Normalized_Finding], set[str]]:
    """A list of repair-eligible findings plus the set of ids to yield no patch.

    Post-processing guarantees each finding is scanner-confirmed (the strategy
    already draws a non-empty ``scanners`` set), NOT labeled a likely false
    positive, carries a unique ``finding_id``, and starts from a clean
    ``OPEN``/no-patch state so the adapter decision fully determines the outcome.
    The empty list (no findings, no decisions) is reachable.
    """
    raw = draw(st.lists(normalized_findings(), max_size=8))
    findings: list[Normalized_Finding] = []
    for i, f in enumerate(raw):
        findings.append(
            replace(
                f,
                finding_id=f"finding-{i}",
                likely_false_positive=False,
                candidate_patch=None,
                status=FindingStatus.OPEN,
                unresolved_reason=None,
            )
        )

    ids = [f.finding_id for f in findings]
    # Independently decide, per finding, whether the adapter yields no patch.
    flags = draw(st.lists(st.booleans(), min_size=len(ids), max_size=len(ids)))
    no_patch_ids = {fid for fid, no_patch in zip(ids, flags) if no_patch}
    return findings, no_patch_ids


# --------------------------------------------------------------------------- #
# Property 14
# --------------------------------------------------------------------------- #


# Feature: security-pipeline, Property 14: For any finding for which AI_Repair yields no patch, that finding is marked unresolved and carries a recorded unresolved_reason.
@settings(max_examples=100)
@given(data=eligible_findings_with_flags())
def test_property_14_no_patch_marks_unresolved(
    data: tuple[list[Normalized_Finding], set[str]],
) -> None:
    findings, no_patch_ids = data
    adapter = FakeRepairAdapter(no_patch_ids)

    result = select_repairs(findings, adapter, ctx=None)

    # select_repairs preserves count and order.
    assert len(result) == len(findings)
    assert [r.finding_id for r in result] == [f.finding_id for f in findings]

    for original, r in zip(findings, result):
        assert is_repair_eligible(original)  # guaranteed by construction
        if original.finding_id in no_patch_ids:
            # (10.4) No patch → unresolved with a recorded, non-empty reason.
            assert r.status == FindingStatus.UNRESOLVED
            assert r.unresolved_reason is not None
            assert r.unresolved_reason.strip() != ""
            assert r.unresolved_reason == NO_PATCH_REASON
            assert r.candidate_patch is None
        else:
            # Patch produced → not marked unresolved; association re-bound.
            assert r.status != FindingStatus.UNRESOLVED
            assert r.candidate_patch is not None
            assert r.candidate_patch.target_finding_id == original.finding_id


# Feature: security-pipeline, Property 14: For any finding for which AI_Repair yields no patch, that finding is marked unresolved and carries a recorded unresolved_reason.
@settings(max_examples=100)
@given(data=eligible_findings_with_flags())
def test_property_14_adapter_error_marks_unresolved(
    data: tuple[list[Normalized_Finding], set[str]],
) -> None:
    findings, raise_ids = data
    adapter = RaisingRepairAdapter(raise_ids)

    result = select_repairs(findings, adapter, ctx=None)

    assert len(result) == len(findings)

    for original, r in zip(findings, result):
        if original.finding_id in raise_ids:
            # (10.4) Adapter raised → still unresolved with a recorded reason.
            assert r.status == FindingStatus.UNRESOLVED
            assert r.unresolved_reason is not None
            assert r.unresolved_reason.strip() != ""
            assert r.unresolved_reason == REPAIR_ERROR_REASON
            assert r.candidate_patch is None
        else:
            # No error → patch attached, not marked unresolved.
            assert r.status != FindingStatus.UNRESOLVED
            assert r.candidate_patch is not None
            assert r.candidate_patch.target_finding_id == original.finding_id
