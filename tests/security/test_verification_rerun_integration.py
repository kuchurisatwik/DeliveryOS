"""Integration test: Verifier re-runs the scanners against the patched scope.

Deterministic example/integration test (NOT property-based). Where Property 15
(``test_property_15_verification_decision``) exercises the *pure* decision core
``decide_verification`` in isolation, this test drives the full :class:`Verifier`
shell end-to-end through its injected :data:`PatchedScanner` boundary to prove
Requirement 11.1: the verifier **re-runs the scanners against the patched scope**
and feeds their (normalized, deduplicated) output into the decision.

The scanner boundary is replaced by a ``RecordingScanner`` fake — a callable that
records every ``(patch, scope)`` it is invoked with and returns canned raw
:class:`Finding` lists. Because the fake is a plain callable, the whole verifier is
exercised without any scanner subprocess or network.

Baselines are built by running the production :func:`normalize` over the same raw
:class:`Finding`s the fake returns, so the baseline's normalized ``finding_id``s
line up exactly with the identities the verifier derives post-patch (that identity
alignment is what the accept/reject decision depends on).

Requirements: 11.1
"""

from __future__ import annotations

from typing import Sequence

from app.security.intelligence.normalize import normalize
from app.security.models import (
    CandidatePatch,
    Finding,
    Location,
    Normalized_Finding,
    ScanScope,
    Severity,
)
from app.security.intelligence.verify import Verifier


# --------------------------------------------------------------------------- #
# Test doubles / helpers.
# --------------------------------------------------------------------------- #


class RecordingScanner:
    """A fake ``PatchedScanner`` that records its calls and returns canned findings.

    Mirrors the injectable ``(patch, scope) -> Sequence[Finding]`` boundary the
    :class:`Verifier` re-runs. Each invocation appends the received
    ``(patch, scope)`` pair to :attr:`calls` so the test can assert the verifier
    re-ran the scanners against the patched scope exactly once (Requirement 11.1).
    """

    def __init__(self, canned: Sequence[Finding]) -> None:
        self._canned = list(canned)
        self.calls: list[tuple[CandidatePatch, ScanScope]] = []

    def __call__(self, patch: CandidatePatch, scope: ScanScope) -> Sequence[Finding]:
        self.calls.append((patch, scope))
        return list(self._canned)


def _raw(scanner: str, rule_id: str, path: str, start: int, end: int) -> Finding:
    """Build a representative raw scanner :class:`Finding`."""
    return Finding(
        scanner=scanner,
        rule_id=rule_id,
        location=Location(path=path, start_line=start, end_line=end),
        severity=Severity.HIGH,
        message=f"{rule_id} at {path}:{start}",
        raw={},
    )


def _normalized_id(finding: Finding) -> str:
    """The normalized ``finding_id`` the verifier will derive for ``finding``."""
    return normalize(finding).finding_id


# Representative raw findings used across the scenarios.
_TARGET_RAW = _raw("bandit", "B602", "app/handlers.py", 12, 13)
_OTHER_RAW = _raw("semgrep", "sql-injection", "app/db.py", 42, 44)
_NEW_RAW = _raw("bandit", "B307", "app/handlers.py", 20, 20)

_TARGET_ID = _normalized_id(_TARGET_RAW)
_NEW_ID = _normalized_id(_NEW_RAW)

_SCOPE = ScanScope(paths=("app/handlers.py", "app/db.py"), related_symbols=("run",))


def _baseline(*raw: Finding) -> list[Normalized_Finding]:
    """Build a normalized baseline from raw findings (ids match the verifier's)."""
    return [normalize(f) for f in raw]


# --------------------------------------------------------------------------- #
# Requirement 11.1 — the Verifier re-runs the scanners against the patched scope.
# --------------------------------------------------------------------------- #


def test_verifier_reruns_scanner_once_with_patch_and_scope() -> None:
    # Baseline still contains the target and an unrelated finding.
    baseline = _baseline(_TARGET_RAW, _OTHER_RAW)
    patch = CandidatePatch(target_finding_id=_TARGET_ID, diff="--- a\n+++ b\n")
    # Post-patch the scanner no longer reports the target (only the other finding).
    scanner = RecordingScanner([_OTHER_RAW])

    Verifier(scanner).verify(patch, baseline, _SCOPE)

    # Requirement 11.1: scanners re-run exactly once against the given patch + scope.
    assert len(scanner.calls) == 1
    called_patch, called_scope = scanner.calls[0]
    assert called_patch is patch
    assert called_scope is _SCOPE


# --------------------------------------------------------------------------- #
# The raw findings from the fake scanner are normalized/deduped and drive the
# decision. Three representative cases (a) accepted, (b) rejected/unresolved,
# (c) rejected with introduced_findings.
# --------------------------------------------------------------------------- #


def test_case_a_target_resolved_and_nothing_new_is_accepted() -> None:
    baseline = _baseline(_TARGET_RAW, _OTHER_RAW)
    patch = CandidatePatch(target_finding_id=_TARGET_ID, diff="")
    # (a) target gone post-patch, remaining finding was already in the baseline.
    scanner = RecordingScanner([_OTHER_RAW])

    outcome = Verifier(scanner).verify(patch, baseline, _SCOPE)

    assert outcome.resolved_target is True
    assert outcome.introduced_findings == ()
    assert outcome.accepted is True


def test_case_b_target_still_present_is_rejected() -> None:
    baseline = _baseline(_TARGET_RAW, _OTHER_RAW)
    patch = CandidatePatch(target_finding_id=_TARGET_ID, diff="")
    # (b) scanner still reports the target -> not resolved -> rejected.
    scanner = RecordingScanner([_TARGET_RAW, _OTHER_RAW])

    outcome = Verifier(scanner).verify(patch, baseline, _SCOPE)

    assert outcome.resolved_target is False
    assert outcome.accepted is False
    assert outcome.introduced_findings == ()


def test_case_c_new_finding_introduced_is_rejected() -> None:
    baseline = _baseline(_TARGET_RAW)
    patch = CandidatePatch(target_finding_id=_TARGET_ID, diff="")
    # (c) target resolved, but a brand-new finding (absent from baseline) appears.
    scanner = RecordingScanner([_NEW_RAW])

    outcome = Verifier(scanner).verify(patch, baseline, _SCOPE)

    assert outcome.resolved_target is True
    assert outcome.accepted is False
    assert outcome.introduced_findings == (_NEW_ID,)


def test_raw_scanner_output_is_deduplicated_before_the_decision() -> None:
    # Two raw findings that normalize to the SAME identity (same rule + location,
    # different scanner) must collapse to a single introduced finding, proving the
    # verifier normalizes AND deduplicates the raw scanner output before deciding.
    baseline = _baseline(_TARGET_RAW)
    patch = CandidatePatch(target_finding_id=_TARGET_ID, diff="")
    dup_a = _raw("bandit", "B307", "app/handlers.py", 20, 20)
    dup_b = _raw("semgrep", "B307", "app/handlers.py", 20, 20)  # same rule_identity+loc
    scanner = RecordingScanner([dup_a, dup_b])

    outcome = Verifier(scanner).verify(patch, baseline, _SCOPE)

    assert outcome.resolved_target is True
    assert outcome.accepted is False
    # Deduplicated to exactly one introduced id (not two).
    assert outcome.introduced_findings == (_NEW_ID,)
