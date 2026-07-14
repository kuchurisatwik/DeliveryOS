"""Layer 3 Context Enrichment — attach contextual signals to findings (Requirement 7).

:func:`enrich` is a **pure, deterministic** function (no I/O, no hidden state) that
takes the deduplicated :class:`~app.security.models.Normalized_Finding`s and the
Layer 1 :class:`~app.schemas.repository.RepositoryContext` and returns NEW enriched
findings. Because :class:`Normalized_Finding` is frozen, enrichment never mutates in
place — it produces fresh instances via :func:`dataclasses.replace`.

For every finding it attaches:

* ``reachability`` — a numeric factor in ``[0, 1]`` derived from the Layer 1 call
  graph reachability inputs (:class:`~app.schemas.repository.SymbolReachability`):
  ``reachable_from_entrypoint`` / ``has_callers`` / ``caller_count`` are mapped into
  the factor (Requirement 7.1).
* ``business_criticality`` — a factor in ``[0, 1]`` derived from the repository
  context: findings in directly-changed (target) symbols and findings referenced by
  many related symbols are treated as more business-critical (Requirement 7.2).
* ``exposure`` — :class:`~app.security.models.Exposure` ∈ ``{PUBLIC, INTERNAL}``
  (Requirement 7.3).
* ``auth_context`` — :class:`~app.security.models.AuthContext` (Requirement 7.4).

It also populates the two remaining scoring inputs the design's ``Normalized_Finding``
carries — ``exploitability`` and ``repository_context`` — so the downstream risk
scorer (Requirement 8) has every factor available.

Every enrichment field is always populated: where a signal cannot be determined from
the provided context, a **documented, deterministic default** is used (never ``None``).
Given the same finding and the same ``repo_context``, :func:`enrich` always produces
the same enrichment.
"""

from __future__ import annotations

import dataclasses

from app.schemas.repository import RepositoryContext, SymbolReachability
from app.security.models import (
    AuthContext,
    Exposure,
    Normalized_Finding,
)

# ---------------------------------------------------------------------------
# Documented deterministic defaults (used when a signal is undeterminable)
# ---------------------------------------------------------------------------

#: Neutral reachability when no call-graph signal matches the finding (7.1).
DEFAULT_REACHABILITY = 0.5
#: Neutral business criticality when the repo context carries no signal (7.2).
DEFAULT_BUSINESS_CRITICALITY = 0.5
#: Conservative default exposure when nothing marks the code as public (7.3).
DEFAULT_EXPOSURE = Exposure.INTERNAL
#: Default auth context when it cannot be inferred (7.4).
DEFAULT_AUTH_CONTEXT = AuthContext.UNKNOWN
#: Neutral exploitability when no exploit signal is available (Req 8 input).
DEFAULT_EXPLOITABILITY = 0.5
#: Repository-context factor when the finding's path is unknown to the context.
DEFAULT_REPOSITORY_CONTEXT = 0.5

#: Reachability weights (sum to 1.0) mapping call-graph signals into ``[0, 1]``.
_W_ENTRYPOINT = 0.5
_W_HAS_CALLERS = 0.25
_W_CALLER_COUNT = 0.25
#: Caller count at/above which the caller-count contribution saturates.
_CALLER_COUNT_SATURATION = 5

#: Path fragments that indicate an externally reachable (public) surface (7.3).
_PUBLIC_PATH_MARKERS = (
    "route",
    "router",
    "api",
    "controller",
    "handler",
    "endpoint",
    "view",
    "public",
    "webhook",
)
#: Path fragments that indicate authentication-related code (7.4).
_AUTH_PATH_MARKERS = (
    "auth",
    "login",
    "logout",
    "session",
    "token",
    "jwt",
    "oauth",
    "permission",
    "credential",
    "identity",
)


def _canonical_path(path: str) -> str:
    """Canonicalize a file path for stable, OS-independent matching."""
    return (path or "").replace("\\", "/").strip().lower()


def _clamp01(value: float) -> float:
    """Clamp a numeric factor into the ``[0, 1]`` interval."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _matching_reachability(
    finding: Normalized_Finding, repo_context: RepositoryContext
) -> list[SymbolReachability]:
    """Return the reachability entries relevant to ``finding``.

    Preference order (deterministic):

    1. Entries whose ``symbol_name``/``qualified_name`` equals the finding's
       located symbol, when the finding carries one.
    2. Otherwise, entries whose ``file_path`` matches the finding's path.
    """
    reach = list(repo_context.reachability or [])
    if not reach:
        return []

    symbol = finding.location.symbol
    if symbol:
        by_symbol = [
            r
            for r in reach
            if r.symbol_name == symbol or r.qualified_name == symbol
        ]
        if by_symbol:
            return by_symbol

    finding_path = _canonical_path(finding.location.path)
    return [r for r in reach if _canonical_path(r.file_path) == finding_path]


def _reachability_factor(
    finding: Normalized_Finding, repo_context: RepositoryContext
) -> float:
    """Derive the ``[0, 1]`` reachability factor from call-graph signals (7.1).

    Aggregates the matching :class:`SymbolReachability` entries (a finding may map
    to several): the code is considered entrypoint-reachable / caller-having if
    *any* matching entry says so, and the caller count is the maximum across
    matches. Returns :data:`DEFAULT_REACHABILITY` when no entry matches.
    """
    matches = _matching_reachability(finding, repo_context)
    if not matches:
        return DEFAULT_REACHABILITY

    reachable = any(m.reachable_from_entrypoint for m in matches)
    has_callers = any(m.has_callers for m in matches)
    caller_count = max((m.caller_count for m in matches), default=0)

    factor = 0.0
    if reachable:
        factor += _W_ENTRYPOINT
    if has_callers:
        factor += _W_HAS_CALLERS
    saturated = min(max(caller_count, 0), _CALLER_COUNT_SATURATION)
    factor += (saturated / _CALLER_COUNT_SATURATION) * _W_CALLER_COUNT
    return _clamp01(factor)


def _target_paths(repo_context: RepositoryContext) -> set[str]:
    """Canonical paths of the directly-changed (target) symbols."""
    return {
        _canonical_path(s.file_path)
        for s in (repo_context.target_symbols or [])
        if s.file_path
    }


def _related_path_count(repo_context: RepositoryContext, path: str) -> int:
    """Count related symbols whose file path matches ``path``."""
    return sum(
        1
        for r in (repo_context.related_symbols or [])
        if r.file_path and _canonical_path(r.file_path) == path
    )


def _business_criticality_factor(
    finding: Normalized_Finding, repo_context: RepositoryContext
) -> float:
    """Derive the ``[0, 1]`` business-criticality factor from repo context (7.2).

    Findings located in directly-changed (target) symbols are treated as more
    business-critical, and centrality (many related symbols referencing the path)
    raises criticality further. Returns :data:`DEFAULT_BUSINESS_CRITICALITY` when
    the context carries no signal for the finding's path.
    """
    path = _canonical_path(finding.location.path)
    targets = _target_paths(repo_context)
    related_count = _related_path_count(repo_context, path)

    if not targets and related_count == 0:
        return DEFAULT_BUSINESS_CRITICALITY

    crit = DEFAULT_BUSINESS_CRITICALITY
    if path in targets:
        crit = max(crit, 0.75)
    saturated = min(related_count, _CALLER_COUNT_SATURATION)
    crit += (saturated / _CALLER_COUNT_SATURATION) * 0.25
    return _clamp01(crit)


def _exposure(
    finding: Normalized_Finding, repo_context: RepositoryContext
) -> Exposure:
    """Classify exposure as PUBLIC or INTERNAL (7.3).

    A finding is PUBLIC when its code is reachable from an entrypoint, or when its
    path matches a known public-surface marker (routes/api/controllers/etc.).
    Otherwise it defaults to :data:`DEFAULT_EXPOSURE` (INTERNAL).
    """
    matches = _matching_reachability(finding, repo_context)
    if any(m.reachable_from_entrypoint for m in matches):
        return Exposure.PUBLIC

    path = _canonical_path(finding.location.path)
    if any(marker in path for marker in _PUBLIC_PATH_MARKERS):
        return Exposure.PUBLIC

    return DEFAULT_EXPOSURE


def _auth_context(
    finding: Normalized_Finding, exposure: Exposure
) -> AuthContext:
    """Derive the authentication context (7.4).

    Code on an authentication-related path is treated as AUTHENTICATED; publicly
    exposed code with no auth markers is treated as UNAUTHENTICATED; everything
    else defaults to :data:`DEFAULT_AUTH_CONTEXT` (UNKNOWN).
    """
    path = _canonical_path(finding.location.path)
    if any(marker in path for marker in _AUTH_PATH_MARKERS):
        return AuthContext.AUTHENTICATED
    if exposure is Exposure.PUBLIC:
        return AuthContext.UNAUTHENTICATED
    return DEFAULT_AUTH_CONTEXT


def _repository_context_factor(
    finding: Normalized_Finding, repo_context: RepositoryContext
) -> float:
    """Derive the ``[0, 1]`` repository-context factor (Req 8 scoring input).

    Reflects how much the Layer 1 context knows about the finding's location: a
    directly-changed (target) path scores highest, a path known only through
    related symbols / reachability scores medium, and an unknown path falls back
    to :data:`DEFAULT_REPOSITORY_CONTEXT`.
    """
    path = _canonical_path(finding.location.path)
    if path in _target_paths(repo_context):
        return 1.0

    known_related = _related_path_count(repo_context, path) > 0
    known_reach = any(
        _canonical_path(r.file_path) == path
        for r in (repo_context.reachability or [])
    )
    if known_related or known_reach:
        return 0.75

    return DEFAULT_REPOSITORY_CONTEXT


def enrich(
    findings: list[Normalized_Finding],
    repo_context: RepositoryContext,
) -> list[Normalized_Finding]:
    """Enrich each finding with contextual signals (Requirement 7).

    Pure and deterministic: the returned findings depend only on ``findings`` and
    ``repo_context``. Since :class:`Normalized_Finding` is frozen, new instances are
    returned via :func:`dataclasses.replace`; inputs are never mutated. Ordering is
    preserved.

    Args:
        findings: The deduplicated findings to enrich.
        repo_context: The Layer 1 repository context providing call-graph
            reachability inputs, related symbols, and changed-feature data.

    Returns:
        A new list of enriched :class:`Normalized_Finding`s. Every finding has a
        non-``None`` ``reachability``, ``business_criticality``, ``exposure`` (in
        ``{PUBLIC, INTERNAL}``), ``auth_context``, ``exploitability``, and
        ``repository_context``; undeterminable signals use documented defaults.
    """
    enriched: list[Normalized_Finding] = []
    for finding in findings:
        reachability = _reachability_factor(finding, repo_context)
        business_criticality = _business_criticality_factor(finding, repo_context)
        exposure = _exposure(finding, repo_context)
        auth_context = _auth_context(finding, exposure)
        repository_context = _repository_context_factor(finding, repo_context)

        enriched.append(
            dataclasses.replace(
                finding,
                reachability=reachability,
                business_criticality=business_criticality,
                exposure=exposure,
                auth_context=auth_context,
                exploitability=DEFAULT_EXPLOITABILITY,
                repository_context=repository_context,
            )
        )
    return enriched
