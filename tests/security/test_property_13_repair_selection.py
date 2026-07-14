"""Property 13: Repair selection and association (security-pipeline).

Exercises :func:`app.security.intelligence.repair.select_repairs` over arbitrary
mixed sets of :class:`app.security.models.Normalized_Finding` using an injected,
in-memory fake :class:`app.security.protocols.AIRepairAdapter` (no network).

Layer 3 AI_Repair must attempt a repair for *exactly* the repair-eligible findings
— those that are scanner-confirmed (carry scanner provenance) and are NOT labeled a
likely false positive (Requirement 10.1) — and every produced ``CandidatePatch``
must be associated with the finding it targets via ``target_finding_id``
(Requirement 10.2). ``select_repairs`` guarantees the association *by construction*:
it re-binds each patch's ``target_finding_id`` to the finding's ``finding_id``
regardless of what the adapter returned. To prove that re-binding actually happens,
the fake adapter below deliberately returns patches carrying a WRONG
``target_finding_id``.

The generated finding sets mix all three categories so the eligibility partition is
meaningfully exercised:
* not scanner-confirmed (empty ``scanners`` set) — must be skipped,
* scanner-confirmed but likely-false-positive — must be skipped (retained for human
  review, never dropped),
* eligible (scanner-confirmed, not a false positive) — must be attempted.

Assertions:
* the set of findings the adapter was invoked on equals exactly the eligible set
  (``is_repair_eligible``), with no finding attempted more than once,
* non-eligible findings were never passed to the adapter,
* every output finding carrying a ``candidate_patch`` has
  ``patch.target_finding_id == finding.finding_id`` (correct re-binding), and that
  ``finding_id`` references a finding present in the input set.

Validates: Requirements 10.1, 10.2
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.repository import RepositoryContext
from app.security.intelligence.repair import is_repair_eligible, select_repairs
from app.security.models import CandidatePatch, Normalized_Finding
from tests.security.strategies import normalized_findings


# --------------------------------------------------------------------------- #
# Fake AIRepairAdapter — records invocations, returns intentionally mis-targeted
# patches so the re-binding guarantee (10.2) is actually observable.
# --------------------------------------------------------------------------- #


class RecordingRepairAdapter:
    """In-memory :class:`AIRepairAdapter` fake.

    Records every finding it is asked to repair and, for findings whose id is in
    ``produce_for_ids``, returns a :class:`CandidatePatch` whose
    ``target_finding_id`` is DELIBERATELY WRONG. If ``select_repairs`` honors the
    association property, the wrong id must never survive into the output.
    """

    def __init__(self, produce_for_ids: set[str]) -> None:
        self.produce_for_ids = set(produce_for_ids)
        self.called_with: list[Normalized_Finding] = []

    def repair(self, f: Normalized_Finding, ctx: object) -> CandidatePatch | None:
        self.called_with.append(f)
        if f.finding_id in self.produce_for_ids:
            # Intentionally wrong target id — select_repairs must re-bind it.
            return CandidatePatch(
                target_finding_id=f"WRONG::{f.finding_id}",
                diff="--- a\n+++ b\n@@ secure fix @@",
            )
        return None


# --------------------------------------------------------------------------- #
# Strategy: a mixed finding set spanning all three eligibility categories, with
# unique finding ids and a chosen subset for which the adapter yields a patch.
# --------------------------------------------------------------------------- #

# Per-finding category controlling how eligibility is forced.
_NOT_CONFIRMED = "not_confirmed"  # empty scanners -> not scanner-confirmed
_FALSE_POSITIVE = "false_positive"  # scanner-confirmed but likely FP
_ELIGIBLE = "eligible"  # scanner-confirmed, not FP


@st.composite
def mixed_findings_and_patch_choice(
    draw: st.DrawFn,
) -> tuple[list[Normalized_Finding], set[str]]:
    """A mixed, unique-id finding list plus the ids the adapter should patch.

    The empty finding list is reachable (edge case). Each finding is coerced into
    one of the three eligibility categories so the partition is exercised.
    """
    base = draw(st.lists(normalized_findings(), max_size=8))

    findings: list[Normalized_Finding] = []
    for i, f in enumerate(base):
        category = draw(st.sampled_from((_NOT_CONFIRMED, _FALSE_POSITIVE, _ELIGIBLE)))
        # Guarantee unique ids so recording-by-id is unambiguous, and reset the
        # AI-stage fields to a clean pre-repair state.
        fid = f"finding-{i}"
        if category == _NOT_CONFIRMED:
            f = replace(f, finding_id=fid, scanners=frozenset(), candidate_patch=None)
        elif category == _FALSE_POSITIVE:
            f = replace(
                f,
                finding_id=fid,
                scanners=frozenset({"bandit"}),
                likely_false_positive=True,
                candidate_patch=None,
            )
        else:  # _ELIGIBLE
            f = replace(
                f,
                finding_id=fid,
                scanners=frozenset({"semgrep"}),
                likely_false_positive=False,
                candidate_patch=None,
            )
        findings.append(f)

    # Choose an arbitrary subset of ids for which the adapter produces a patch.
    all_ids = [f.finding_id for f in findings]
    produce_for_ids = set(
        draw(st.lists(st.sampled_from(all_ids), unique=True)) if all_ids else []
    )
    return findings, produce_for_ids


# --------------------------------------------------------------------------- #
# Property
# --------------------------------------------------------------------------- #


# Feature: security-pipeline, Property 13: For any set of Normalized_Findings, AI_Repair is attempted for exactly those findings that are scanner-confirmed and not labeled a likely false positive, and every produced CandidatePatch has a target_finding_id that references a finding present in the set.
@settings(max_examples=100)
@given(data=mixed_findings_and_patch_choice())
def test_property_13_repair_selection_and_association(
    data: tuple[list[Normalized_Finding], set[str]],
) -> None:
    findings, produce_for_ids = data
    adapter = RecordingRepairAdapter(produce_for_ids)
    ctx = RepositoryContext()

    result = select_repairs(findings, adapter, ctx)

    input_ids = {f.finding_id for f in findings}
    eligible_ids = {f.finding_id for f in findings if is_repair_eligible(f)}
    called_ids = [f.finding_id for f in adapter.called_with]

    # (10.1) Repair attempted for EXACTLY the eligible findings...
    assert set(called_ids) == eligible_ids
    # ...and each eligible finding is attempted exactly once (no duplicate calls).
    assert len(called_ids) == len(eligible_ids)
    # Non-eligible findings were never passed to the adapter.
    non_eligible_ids = input_ids - eligible_ids
    assert non_eligible_ids.isdisjoint(set(called_ids))

    # Output preserves count and order of the input findings.
    assert len(result) == len(findings)
    assert [r.finding_id for r in result] == [f.finding_id for f in findings]

    for out in result:
        if out.candidate_patch is not None:
            # (10.2) The patch is associated with the finding it targets: the
            # deliberately-wrong id from the adapter must have been re-bound.
            assert out.candidate_patch.target_finding_id == out.finding_id
            # ...and that target references a finding present in the input set.
            assert out.candidate_patch.target_finding_id in input_ids
            # Only eligible findings can carry a patch.
            assert out.finding_id in eligible_ids

    # Every finding the adapter produced a patch for must carry an associated
    # (correctly re-bound) patch in the output.
    patched_out = {r.finding_id for r in result if r.candidate_patch is not None}
    assert patched_out == (produce_for_ids & eligible_ids)
