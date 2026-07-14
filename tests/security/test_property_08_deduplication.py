"""Property 8: Deduplication (security-pipeline).

Exercises :func:`app.security.intelligence.dedup.deduplicate` over sets of
:class:`~app.security.models.Normalized_Finding`s containing controlled
duplicate groups (built by ``duplicate_grouped_findings``).

The dedup key is ``(rule_identity, canonical_location)`` where
``canonical_location`` is ``(_canonical_path(path), start_line, end_line,
symbol or "")`` — exactly the derivation used inside ``dedup.py``. Rather than
trusting the strategy's ground-truth group map (which keys on the *raw* path and
ignores ``symbol``), the expected grouping is recomputed here with dedup's own
``_dedup_key`` so the test asserts against dedup's exact canonicalization.

The test asserts:
* the number of output findings equals the number of distinct dedup-key groups
  in the input (Requirement 6.1, 6.3 — distinct vulnerabilities preserved);
* each output finding's ``scanners`` frozenset equals the union of the
  originating scanners of every input finding sharing its dedup key
  (Requirement 6.2); and
* no two output findings share the same dedup key (each group collapses to one).

The empty-finding-list case is reachable from the strategy and additionally
asserted explicitly.

Validates: Requirements 6.1, 6.2, 6.3
"""

from __future__ import annotations

from collections import defaultdict

from hypothesis import given, settings

from app.security.intelligence.dedup import _dedup_key, deduplicate
from app.security.models import Normalized_Finding
from tests.security.strategies import duplicate_grouped_findings


# Feature: security-pipeline, Property 8: For any set of Normalized_Findings, deduplication collapses every group sharing the same (rule_identity, canonical_location) into a single finding whose scanners set equals the union of the group's originating scanners, while the number of output findings equals the number of distinct (rule_identity, canonical_location) groups (distinct vulnerabilities are preserved).
@settings(max_examples=100)
@given(grouped=duplicate_grouped_findings())
def test_property_08_deduplication(
    grouped: tuple[list[Normalized_Finding], dict],
) -> None:
    findings, _expected_group_map = grouped

    # Recompute the expected grouping using dedup's exact key derivation.
    members_by_key: dict = defaultdict(list)
    for finding in findings:
        members_by_key[_dedup_key(finding)].append(finding)

    result = deduplicate(findings)

    # (6.1, 6.3) One output per distinct (rule_identity, canonical_location).
    assert len(result) == len(members_by_key)

    # (6.1) Each distinct group collapses to a single output — no key repeats.
    output_keys = [_dedup_key(f) for f in result]
    assert len(output_keys) == len(set(output_keys))
    assert set(output_keys) == set(members_by_key)

    # (6.2) Each merged finding retains the union of its group's scanners.
    for finding in result:
        key = _dedup_key(finding)
        expected_scanners: set[str] = set()
        for member in members_by_key[key]:
            expected_scanners |= set(member.scanners)
        assert finding.scanners == frozenset(expected_scanners)


def test_property_08_deduplication_empty_list() -> None:
    """Edge case: deduplicating an empty finding list yields an empty list."""
    assert deduplicate([]) == []
