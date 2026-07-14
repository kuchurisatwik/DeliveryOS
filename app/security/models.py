"""Immutable data models for the DeliveryOS Security Pipeline.

These are the net-new, security-specific models from the design "Data Models"
section. All models are immutable dataclasses (``frozen=True``) and enumerations
use :class:`enum.Enum`, keeping the deterministic security core expressible as
pure functions over well-defined, hashable data.

Layer 1 / repository-context models (``GitDiff``, ``ChangedFeature``,
``RepoContext``, ``SymbolRef``, graphs) are intentionally *not* redefined here.
They are handled by the Layer 1 extension tasks which reuse and extend the
existing ``app/schemas/repository.py`` (:class:`RepositoryContext`) and the
repository indexer/retriever stack. Validation/coverage results likewise reuse
``app/schemas/quality.py`` rather than being duplicated.

Requirements traced: 3.5 (finding provenance), 5.1 (Common_Schema).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


# ---------------------------------------------------------------------------
# Detection scope (Layer 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanScope:
    """The code surface a scanner adapter is scoped to (Requirement 3.2).

    Derived once from the repository context (the changed feature's paths plus
    related symbols) and shared identically with every scanner adapter.
    """

    paths: tuple[str, ...]
    related_symbols: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Raw findings (Layer 2 output)
# ---------------------------------------------------------------------------


class Severity(Enum):
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


@dataclass(frozen=True)
class Location:
    """Affected source location for a finding (Requirement 3.5)."""

    path: str
    start_line: int
    end_line: int
    symbol: str | None = None


@dataclass(frozen=True)
class Finding:
    """A single vulnerability reported by a Scanner.

    Records the originating scanner, affected location, and scanner-assigned
    severity as provenance (Requirement 3.5).
    """

    scanner: str
    rule_id: str
    location: Location
    severity: Severity
    message: str
    raw: Mapping[str, object]


# ---------------------------------------------------------------------------
# Common_Schema / Normalized_Finding (Layer 3)
# ---------------------------------------------------------------------------


class FindingStatus(Enum):
    OPEN = "open"
    FIXED = "fixed"
    UNRESOLVED = "unresolved"


class Exposure(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"


class AuthContext(Enum):
    """Authentication context enrichment classification (Requirement 7.4)."""

    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"
    UNKNOWN = "unknown"


class Priority(Enum):
    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3


@dataclass(frozen=True)
class AITriage:
    """AI-produced triage attached to a finding (Requirement 9)."""

    explanation: str
    priority: Priority
    suggested_fix: str
    likely_false_positive: bool


@dataclass(frozen=True)
class CandidatePatch:
    """A proposal-only candidate patch produced by AI_Repair (Requirement 10)."""

    target_finding_id: str
    diff: str


@dataclass(frozen=True)
class Normalized_Finding:
    """A Finding converted into the Common_Schema (Requirement 5).

    Preserves scanner/location/severity (5.2). Missing required fields are
    filled with documented defaults and recorded in ``defaults_applied`` (5.3).
    The set of originating scanners is retained after deduplication (6.2).
    """

    finding_id: str
    rule_identity: str
    location: Location
    severity: Severity
    scanners: frozenset[str]
    category: str  # code/secret/iac/dependency/container
    message: str
    defaults_applied: tuple[str, ...] = ()
    # Enrichment (Requirement 7)
    reachability: float | None = None
    business_criticality: float | None = None
    exposure: Exposure | None = None
    auth_context: AuthContext | None = None
    exploitability: float | None = None
    repository_context: float | None = None
    # Scoring (Requirement 8)
    risk_score: float | None = None
    # AI stages (Requirements 9, 10)
    triage: AITriage | None = None
    likely_false_positive: bool = False
    candidate_patch: CandidatePatch | None = None
    status: FindingStatus = FindingStatus.OPEN
    unresolved_reason: str | None = None


# ---------------------------------------------------------------------------
# Risk scoring inputs (Layer 3, Requirement 8)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskScoreInputs:
    """Inputs to the deterministic Risk_Score product (Requirement 8.1)."""

    severity: float
    reachability: float
    business_criticality: float
    exploitability: float
    repository_context: float


# ---------------------------------------------------------------------------
# Verification (Layer 3, Requirement 11)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationOutcome:
    """Outcome of deterministically re-verifying a candidate patch."""

    accepted: bool
    resolved_target: bool
    introduced_findings: tuple[str, ...]


# ---------------------------------------------------------------------------
# Quality Gate (Layer 4, Requirement 12)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityGateThresholds:
    """Configurable Quality_Gate thresholds with documented defaults (12.3)."""

    max_critical_findings: int = 0
    min_coverage_percent: float = 90.0
    max_leaked_secrets: int = 0
    max_blocking_iac_issues: int = 0
    # SonarQube-derived thresholds (12.1)
    max_code_smells: int | None = None
    max_technical_debt_minutes: int | None = None
    max_security_hotspots: int | None = None
    min_maintainability_rating: str | None = None


class GateStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True)
class UnsatisfiedThreshold:
    name: str
    expected: str
    actual: str


@dataclass(frozen=True)
class Quality_Gate:
    """Quality_Gate evaluation result (Requirement 12.4/12.5)."""

    status: GateStatus
    unsatisfied: tuple[UnsatisfiedThreshold, ...] = ()


@dataclass(frozen=True)
class SonarMetrics:
    """SonarQube metrics consumed by the Quality_Gate (Requirement 12.1)."""

    coverage_percent: float
    code_smells: int
    technical_debt_minutes: int
    security_hotspots: int
    maintainability_rating: str


# ---------------------------------------------------------------------------
# Merge Confidence (Layer 4, Requirement 13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MergeConfidenceInputs:
    testing_confidence: float
    security_confidence: float
    coverage_percent: float
    remaining_findings: int
    quality_gate_status: GateStatus


@dataclass(frozen=True)
class Merge_Confidence:
    """Advisory merge confidence (Requirement 13.3 — never auto-merges)."""

    score: float
    inputs: MergeConfidenceInputs
    advisory: bool = True


# ---------------------------------------------------------------------------
# Layer results and report supporting models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScannerCoverage:
    """Per-scanner coverage status (Requirements 3.4, 14.4)."""

    scanner: str
    status: str  # "complete" | "incomplete"
    reason: str | None = None


@dataclass(frozen=True)
class ConfigSubstitution:
    """Records a malformed Repo_Config value replaced by a default (15.2)."""

    field: str
    provided: str
    applied_default: str


@dataclass(frozen=True)
class DetectionResult:
    """Aggregated Detection_Layer output: findings + per-scanner coverage."""

    findings: tuple[Finding, ...]
    coverage: tuple[ScannerCoverage, ...] = ()


@dataclass(frozen=True)
class IntelligenceResult:
    """Intelligence_Layer output partitioned into fixed and remaining findings."""

    fixed: tuple[Normalized_Finding, ...] = ()
    remaining: tuple[Normalized_Finding, ...] = ()


@dataclass(frozen=True)
class Pull_Request_Report:
    """The report attached to the Pull Request (Requirement 14)."""

    commit_sha: str
    testing_summary: str
    security_summary: str
    fixed_findings: tuple[Normalized_Finding, ...]
    remaining_findings: tuple[Normalized_Finding, ...]
    merge_confidence: Merge_Confidence
    quality_gate: Quality_Gate
    incomplete_scanners: tuple[ScannerCoverage, ...] = ()
    config_substitutions: tuple[ConfigSubstitution, ...] = ()
    failed_layer: str | None = None


# ---------------------------------------------------------------------------
# Resolved configuration (Requirement 15)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedConfig:
    """Single immutable resolved configuration consumed by all layers (15)."""

    thresholds: QualityGateThresholds = field(default_factory=QualityGateThresholds)
    scanner_rules: Mapping[str, object] = field(default_factory=dict)
    pipeline_settings: Mapping[str, object] = field(default_factory=dict)
