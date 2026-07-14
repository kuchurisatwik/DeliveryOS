"""Property 5: Finding aggregation and provenance (security-pipeline).

Exercises :class:`app.security.detection.runner.DetectionStage` with in-memory
FAKE scanner adapters, each configured (via Hypothesis) to return a specific
list of :class:`Finding` objects. All adapters succeed (scanner-failure
containment is Property 6 / task 4.4), so the stage aggregates every finding as
a multiset union of the per-scanner lists.

The test asserts:
* the multiset of ``DetectionResult.findings`` equals the multiset union of all
  the per-scanner finding lists (Requirement 3.3); and
* every aggregated ``Finding`` retains its originating scanner, affected
  location, and scanner-assigned severity unchanged from what the fake returned
  (Requirement 3.5).

The empty case (adapters returning empty lists, or no adapters) is covered by
the generated inputs.

Validates: Requirements 3.3, 3.5
"""

from __future__ import annotations

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.detection.runner import DetectionStage
from app.security.models import Finding, ScanScope
from app.workflows.context import WorkflowContext
from tests.security.strategies import findings


# --------------------------------------------------------------------------- #
# In-memory fake scanner adapter
# --------------------------------------------------------------------------- #


class FakeScanner:
    """A ScannerAdapter that always succeeds, returning preconfigured findings."""

    def __init__(self, name: str, scanner_findings: list[Finding]) -> None:
        self.name = name
        self._findings = list(scanner_findings)

    def scan(self, scope: ScanScope) -> list[Finding]:
        return list(self._findings)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _hashable(f: Finding):
    """A fully-identifying, hashable projection of a Finding for multiset compare."""
    return (
        f.scanner,
        f.rule_id,
        f.location,  # frozen dataclass -> hashable
        f.severity,
        f.message,
        frozenset(f.raw.items()),
    )


def _provenance(f: Finding):
    """The provenance triple that must be retained (Requirement 3.5)."""
    return (f.scanner, f.location, f.severity)


def _make_context() -> WorkflowContext:
    """A minimal WorkflowContext; DetectionStage only reads scope inputs."""
    return WorkflowContext(
        repository="owner/repo",
        repo_name="repo",
        clone_url="https://example.invalid/owner/repo.git",
        branch="main",
        commit_sha="deadbeef",
        changed_files=["app/module.py"],
    )


# --------------------------------------------------------------------------- #
# Property
# --------------------------------------------------------------------------- #


# Feature: security-pipeline, Property 5: For any collection of per-scanner finding lists produced when all scanners complete, the Detection_Layer's aggregated output equals the multiset union of those lists, and every aggregated Finding retains its originating scanner, affected location, and scanner-assigned severity.
@settings(max_examples=100)
@given(per_scanner=st.lists(st.lists(findings(), max_size=5), max_size=6))
def test_property_05_aggregation_and_provenance(
    per_scanner: list[list[Finding]],
) -> None:
    # Build one fake adapter per generated finding list. Names are unique so the
    # runner tracks each adapter's coverage independently; each adapter succeeds.
    adapters = [
        FakeScanner(f"scanner_{i}", scanner_findings)
        for i, scanner_findings in enumerate(per_scanner)
    ]

    context = _make_context()
    DetectionStage(adapters=adapters).execute(context)

    result = context.detection_result
    assert result is not None

    # Expected multiset union of every per-scanner finding list.
    expected_union: list[Finding] = [f for lst in per_scanner for f in lst]

    # (3.3) Aggregated output equals the multiset union of the per-scanner lists.
    assert Counter(_hashable(f) for f in result.findings) == Counter(
        _hashable(f) for f in expected_union
    )

    # (3.5) Every aggregated Finding retains scanner / location / severity — the
    # multiset of provenance triples is preserved exactly.
    assert Counter(_provenance(f) for f in result.findings) == Counter(
        _provenance(f) for f in expected_union
    )

    # All adapters completed, so every one is marked complete (no incomplete).
    assert len(result.coverage) == len(adapters)
    assert all(c.status == "complete" for c in result.coverage)
