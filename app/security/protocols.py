"""Injectable adapter Protocols for the Security Pipeline.

The design's "pure core, impure shell" principle isolates every side-effecting
boundary (scanner subprocesses, LLM calls, SonarQube HTTP, GitHub API) behind a
:class:`typing.Protocol`. Concrete adapters implementing these protocols are
injected into each layer, enabling the deterministic core to be exercised with
in-memory fakes and mocks.

The method signatures mirror the design "Components and Interfaces" section.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from typing import TYPE_CHECKING

from app.security.models import (
    AITriage,
    CandidatePatch,
    Finding,
    Normalized_Finding,
    Pull_Request_Report,
    ScanScope,
    SonarMetrics,
)

# ``RepoContext`` is the Layer 1 repository-context model produced by the
# repository-intelligence stack (reusing/extending ``app/schemas/repository.py``).
# It is referenced only in type hints; ``from __future__ import annotations``
# keeps these annotations lazy so no concrete import coupling is introduced here.
if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.schemas.repository import RepositoryContext as RepoContext


@runtime_checkable
class ScannerAdapter(Protocol):
    """A deterministic security scanner (Bandit, Semgrep, CodeQL, ...).

    Each adapter invokes its underlying tool scoped to ``scope`` and parses the
    tool's native output into the shared :class:`Finding` type (Requirements 3, 4).
    """

    name: str

    def scan(self, scope: ScanScope) -> list[Finding]: ...


class AITriageAdapter(Protocol):
    """Produces an :class:`AITriage` for a normalized finding (Requirement 9)."""

    def triage(self, f: Normalized_Finding, ctx: RepoContext) -> AITriage: ...


class AIRepairAdapter(Protocol):
    """Generates a proposal-only candidate patch for a finding (Requirement 10).

    Returns ``None`` when no patch can be produced, in which case the finding is
    marked unresolved with a recorded reason (10.4).
    """

    def repair(self, f: Normalized_Finding, ctx: RepoContext) -> CandidatePatch | None: ...


class SonarClient(Protocol):
    """Fetches SonarQube metrics for the Quality_Gate (Requirement 12.1)."""

    def fetch_metrics(self, commit_sha: str) -> SonarMetrics: ...


class GitHubReporter(Protocol):
    """Posts the Pull_Request_Report and commits patches to the PR branch.

    The final merge decision is always left to a human; this adapter never
    invokes a merge (Requirements 14.1, 14.5, 13.3, 10.3).
    """

    def post_report(self, commit_sha: str, report: Pull_Request_Report) -> None: ...

    def commit_patches(self, commit_sha: str, patches: list[CandidatePatch]) -> None: ...
