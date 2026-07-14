"""Reusable Hypothesis strategies for the DeliveryOS Security Pipeline core.

These generators produce the immutable data models defined in
``app.security.models`` so the deterministic security core (normalize,
deduplicate, enrich, risk-score, verify, quality-gate, merge-confidence,
config resolution, report assembly) can be property-tested with a shared,
consistent input space.

Design references:
- design.md "Testing Strategy" → build reusable Hypothesis strategies for
  ``Finding``, ``Normalized_Finding``, ``Location``, ``Severity``,
  ``RiskScoreInputs``, ``QualityGateThresholds``, ``SonarMetrics``,
  ``MergeConfidenceInputs``, well-formed/malformed ``Repo_Config``, and
  finding sets with controlled duplicate groups and baseline/post-patch
  relationships.

Edge cases exercised by these strategies:
- empty inputs (empty finding lists, empty scan scopes, empty configs),
- missing fields (``defaults_applied`` populated; optional enrichment ``None``),
- non-ASCII strings (identifiers, paths, messages),
- boundary numerics (0.0 / 1.0 factors, zero and large thresholds),
- mixed parseable / unparseable file sets.

Requirements traced: 5.1 (Common_Schema), 6.1 (deduplication inputs),
8.1 (risk-score inputs).
"""

from __future__ import annotations

from typing import Any

from hypothesis import strategies as st

from app.security.models import (
    AITriage,
    AuthContext,
    CandidatePatch,
    ConfigSubstitution,
    Exposure,
    Finding,
    FindingStatus,
    GateStatus,
    Location,
    MergeConfidenceInputs,
    Normalized_Finding,
    Priority,
    QualityGateThresholds,
    RiskScoreInputs,
    ScannerCoverage,
    Severity,
    SonarMetrics,
)

# ---------------------------------------------------------------------------
# Primitive / text strategies (include non-ASCII and empty edge cases)
# ---------------------------------------------------------------------------

#: Text that may contain non-ASCII characters and may be empty.
text_any = st.text(max_size=40)

#: Non-empty text that may contain non-ASCII characters.
text_nonempty = st.text(min_size=1, max_size=40)

#: Identifiers: mix of plain ASCII and non-ASCII to stress downstream logic.
identifiers = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=20),
    st.text(alphabet="ñüéçΩ字符测试λμ", min_size=1, max_size=10),
)

#: Factor in the closed unit interval, with 0.0 and 1.0 included as boundaries.
unit_factor = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)

#: A non-negative "multiplier" style factor with boundary values.
nonneg_factor = st.floats(
    min_value=0.0,
    max_value=100.0,
    allow_nan=False,
    allow_infinity=False,
)

#: Coverage percentage including the 0 and 100 boundaries.
coverage_percent = st.floats(
    min_value=0.0,
    max_value=100.0,
    allow_nan=False,
    allow_infinity=False,
)

FINDING_CATEGORIES = ("code", "secret", "iac", "dependency", "container")
SCANNER_NAMES = ("bandit", "semgrep", "codeql", "gitleaks", "checkov", "trivy")
MAINTAINABILITY_RATINGS = ("A", "B", "C", "D", "E")


# ---------------------------------------------------------------------------
# File-path strategies (parseable / unparseable / mixed sets)
# ---------------------------------------------------------------------------

#: A path that is expected to be parseable (a Python source file).
parseable_paths = st.builds(
    lambda stem: f"{stem}.py",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_/", min_size=1, max_size=25),
)

#: A path that is expected to be unparseable / non-source (binary, data, docs).
unparseable_paths = st.builds(
    lambda stem, ext: f"{stem}.{ext}",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_/", min_size=1, max_size=25),
    st.sampled_from(("bin", "png", "lock", "min.js", "so", "dat")),
)


@st.composite
def mixed_file_sets(draw: st.DrawFn) -> dict[str, list[str]]:
    """A file set mixing parseable and unparseable paths.

    Returns a dict with ``parseable`` and ``unparseable`` keys plus a combined
    ``all`` list, so tests can assert against a known partition. Either subset
    may be empty (edge case).
    """

    parseable = draw(st.lists(parseable_paths, max_size=6, unique=True))
    unparseable = draw(st.lists(unparseable_paths, max_size=6, unique=True))
    combined = list(parseable) + list(unparseable)
    return {"parseable": parseable, "unparseable": unparseable, "all": combined}


# ---------------------------------------------------------------------------
# Core enum / value strategies
# ---------------------------------------------------------------------------


def severities() -> st.SearchStrategy[Severity]:
    """Any :class:`Severity` enum member."""

    return st.sampled_from(list(Severity))


def exposures() -> st.SearchStrategy[Exposure]:
    return st.sampled_from(list(Exposure))


def auth_contexts() -> st.SearchStrategy[AuthContext]:
    return st.sampled_from(list(AuthContext))


def priorities() -> st.SearchStrategy[Priority]:
    return st.sampled_from(list(Priority))


def finding_statuses() -> st.SearchStrategy[FindingStatus]:
    return st.sampled_from(list(FindingStatus))


def gate_statuses() -> st.SearchStrategy[GateStatus]:
    return st.sampled_from(list(GateStatus))


@st.composite
def locations(draw: st.DrawFn) -> Location:
    """A :class:`Location`; ``start_line``/``end_line`` are ordered and >= 1."""

    start = draw(st.integers(min_value=1, max_value=10_000))
    length = draw(st.integers(min_value=0, max_value=500))
    symbol = draw(st.one_of(st.none(), identifiers))
    path = draw(st.one_of(parseable_paths, unparseable_paths))
    return Location(path=path, start_line=start, end_line=start + length, symbol=symbol)


@st.composite
def findings(draw: st.DrawFn) -> Finding:
    """A raw :class:`Finding` with full provenance (scanner/location/severity)."""

    return Finding(
        scanner=draw(st.sampled_from(SCANNER_NAMES)),
        rule_id=draw(identifiers),
        location=draw(locations()),
        severity=draw(severities()),
        message=draw(text_any),
        raw=draw(
            st.dictionaries(
                keys=st.text(max_size=10),
                values=st.one_of(st.integers(), st.text(max_size=10), st.booleans()),
                max_size=4,
            )
        ),
    )


@st.composite
def ai_triages(draw: st.DrawFn) -> AITriage:
    return AITriage(
        explanation=draw(text_any),
        priority=draw(priorities()),
        suggested_fix=draw(text_any),
        likely_false_positive=draw(st.booleans()),
    )


@st.composite
def candidate_patches(
    draw: st.DrawFn, target_finding_id: str | None = None
) -> CandidatePatch:
    tid = target_finding_id if target_finding_id is not None else draw(identifiers)
    return CandidatePatch(target_finding_id=tid, diff=draw(text_any))


# ---------------------------------------------------------------------------
# Normalized findings
# ---------------------------------------------------------------------------


@st.composite
def normalized_findings(
    draw: st.DrawFn,
    *,
    finding_id: str | None = None,
    rule_identity: str | None = None,
    location: Location | None = None,
    enriched: bool | None = None,
    scored: bool | None = None,
) -> Normalized_Finding:
    """A :class:`Normalized_Finding`.

    ``enriched``/``scored`` control whether the optional enrichment and
    risk-score fields are populated. When left as ``None`` the strategy draws
    the choice, covering both the "missing fields" edge case (all ``None``) and
    fully-populated findings.
    """

    fid = finding_id if finding_id is not None else draw(identifiers)
    rid = rule_identity if rule_identity is not None else draw(identifiers)
    loc = location if location is not None else draw(locations())

    scanners = draw(
        st.frozensets(st.sampled_from(SCANNER_NAMES), min_size=1, max_size=len(SCANNER_NAMES))
    )
    # defaults_applied models the "missing required fields" edge case (5.3).
    defaults_applied = tuple(
        draw(
            st.lists(
                st.sampled_from(("message", "category", "severity", "location")),
                max_size=4,
                unique=True,
            )
        )
    )

    do_enrich = draw(st.booleans()) if enriched is None else enriched
    do_score = draw(st.booleans()) if scored is None else scored

    reachability = draw(unit_factor) if do_enrich else None
    business_criticality = draw(unit_factor) if do_enrich else None
    exposure = draw(exposures()) if do_enrich else None
    auth_context = draw(auth_contexts()) if do_enrich else None
    exploitability = draw(unit_factor) if do_enrich else None
    repository_context = draw(unit_factor) if do_enrich else None
    risk_score = draw(nonneg_factor) if do_score else None

    triage = draw(st.one_of(st.none(), ai_triages()))
    likely_fp = triage.likely_false_positive if triage is not None else draw(st.booleans())
    status = draw(finding_statuses())
    patch = draw(st.one_of(st.none(), candidate_patches(target_finding_id=fid)))
    unresolved_reason = (
        draw(text_nonempty) if status is FindingStatus.UNRESOLVED else None
    )

    return Normalized_Finding(
        finding_id=fid,
        rule_identity=rid,
        location=loc,
        severity=draw(severities()),
        scanners=scanners,
        category=draw(st.sampled_from(FINDING_CATEGORIES)),
        message=draw(text_any),
        defaults_applied=defaults_applied,
        reachability=reachability,
        business_criticality=business_criticality,
        exposure=exposure,
        auth_context=auth_context,
        exploitability=exploitability,
        repository_context=repository_context,
        risk_score=risk_score,
        triage=triage,
        likely_false_positive=likely_fp,
        candidate_patch=patch,
        status=status,
        unresolved_reason=unresolved_reason,
    )


# ---------------------------------------------------------------------------
# Scoring / gate / confidence inputs
# ---------------------------------------------------------------------------


@st.composite
def risk_score_inputs(draw: st.DrawFn) -> RiskScoreInputs:
    """Inputs to the Risk_Score product; each factor includes 0.0/1.0 bounds."""

    return RiskScoreInputs(
        severity=draw(nonneg_factor),
        reachability=draw(unit_factor),
        business_criticality=draw(unit_factor),
        exploitability=draw(unit_factor),
        repository_context=draw(unit_factor),
    )


@st.composite
def quality_gate_thresholds(draw: st.DrawFn) -> QualityGateThresholds:
    """Well-formed :class:`QualityGateThresholds` including boundary values."""

    return QualityGateThresholds(
        max_critical_findings=draw(st.integers(min_value=0, max_value=50)),
        min_coverage_percent=draw(coverage_percent),
        max_leaked_secrets=draw(st.integers(min_value=0, max_value=50)),
        max_blocking_iac_issues=draw(st.integers(min_value=0, max_value=50)),
        max_code_smells=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1000))),
        max_technical_debt_minutes=draw(
            st.one_of(st.none(), st.integers(min_value=0, max_value=100_000))
        ),
        max_security_hotspots=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1000))),
        min_maintainability_rating=draw(
            st.one_of(st.none(), st.sampled_from(MAINTAINABILITY_RATINGS))
        ),
    )


@st.composite
def sonar_metrics(draw: st.DrawFn) -> SonarMetrics:
    return SonarMetrics(
        coverage_percent=draw(coverage_percent),
        code_smells=draw(st.integers(min_value=0, max_value=2000)),
        technical_debt_minutes=draw(st.integers(min_value=0, max_value=200_000)),
        security_hotspots=draw(st.integers(min_value=0, max_value=2000)),
        maintainability_rating=draw(st.sampled_from(MAINTAINABILITY_RATINGS)),
    )


@st.composite
def merge_confidence_inputs(draw: st.DrawFn) -> MergeConfidenceInputs:
    return MergeConfidenceInputs(
        testing_confidence=draw(unit_factor),
        security_confidence=draw(unit_factor),
        coverage_percent=draw(coverage_percent),
        remaining_findings=draw(st.integers(min_value=0, max_value=500)),
        quality_gate_status=draw(gate_statuses()),
    )


@st.composite
def scanner_coverages(draw: st.DrawFn) -> ScannerCoverage:
    status = draw(st.sampled_from(("complete", "incomplete")))
    reason = draw(text_nonempty) if status == "incomplete" else None
    return ScannerCoverage(
        scanner=draw(st.sampled_from(SCANNER_NAMES)),
        status=status,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Finding sets with controlled duplicate groups (for deduplication, 6.1)
# ---------------------------------------------------------------------------


@st.composite
def duplicate_grouped_findings(
    draw: st.DrawFn,
) -> tuple[list[Normalized_Finding], dict[tuple[str, tuple[str, int, int]], int]]:
    """A finding list containing controlled duplicate groups.

    Duplicates are findings sharing the same ``(rule_identity,
    canonical_location)`` where canonical location is ``(path, start_line,
    end_line)``. Returns the shuffled findings and a map from each group key to
    the expected number of members, so dedup tests know the ground truth.

    Edge cases: an empty finding list (no groups) is reachable.
    """

    n_groups = draw(st.integers(min_value=0, max_value=4))
    findings_out: list[Normalized_Finding] = []
    expected: dict[tuple[str, tuple[str, int, int]], int] = {}

    for _ in range(n_groups):
        rule_identity = draw(identifiers)
        loc = draw(locations())
        key = (rule_identity, (loc.path, loc.start_line, loc.end_line))
        # Ensure distinct group keys; skip if collision (rare) by mutating id.
        if key in expected:
            rule_identity = rule_identity + "_x"
            key = (rule_identity, (loc.path, loc.start_line, loc.end_line))
        count = draw(st.integers(min_value=1, max_value=4))
        expected[key] = count
        for _ in range(count):
            findings_out.append(
                draw(
                    normalized_findings(
                        rule_identity=rule_identity,
                        location=loc,
                    )
                )
            )

    # Shuffle so dedup cannot rely on ordering.
    findings_out = draw(st.permutations(findings_out))
    return list(findings_out), expected


# ---------------------------------------------------------------------------
# Baseline / post-patch relationships (for verification, 11.x)
# ---------------------------------------------------------------------------


@st.composite
def baseline_and_post_patch(
    draw: st.DrawFn,
) -> dict[str, Any]:
    """Controlled baseline vs post-patch finding sets for verification tests.

    Produces:
    - ``baseline``: the findings present before the patch,
    - ``target_finding_id``: the finding the patch intends to resolve (or None
      when baseline is empty),
    - ``resolved``: whether the target was removed post-patch,
    - ``introduced``: newly-introduced findings absent from the baseline,
    - ``post_patch``: the resulting post-patch finding set.

    This lets verification tests assert the accept/reject decision (accept iff
    target resolved AND nothing new introduced).
    """

    baseline = draw(st.lists(normalized_findings(), max_size=5))

    if not baseline:
        return {
            "baseline": [],
            "target_finding_id": None,
            "resolved": False,
            "introduced": [],
            "post_patch": [],
        }

    target = draw(st.sampled_from(baseline))
    resolved = draw(st.booleans())
    introduced = draw(st.lists(normalized_findings(), max_size=3))

    baseline_ids = {f.finding_id for f in baseline}
    # Keep only introduced findings whose ids are genuinely new.
    introduced = [f for f in introduced if f.finding_id not in baseline_ids]

    post_patch = [f for f in baseline if not (resolved and f is target)]
    post_patch = post_patch + introduced
    post_patch = draw(st.permutations(post_patch))

    return {
        "baseline": baseline,
        "target_finding_id": target.finding_id,
        "resolved": resolved,
        "introduced": introduced,
        "post_patch": list(post_patch),
    }


# ---------------------------------------------------------------------------
# Repo_Config (raw) — well-formed and malformed variants (15.x)
# ---------------------------------------------------------------------------
#
# Repo_Config is consumed by ``ConfigResolver.resolve(raw)`` (built in task
# 1.3). Its raw form is a mapping of threshold / scanner-rule / pipeline
# settings. These strategies model that raw input space so config-resolution
# and config-substitution property tests have both valid and invalid inputs.

# Field name -> strategy producing a WELL-FORMED value.
_WELL_FORMED_FIELDS: dict[str, st.SearchStrategy[Any]] = {
    "max_critical_findings": st.integers(min_value=0, max_value=50),
    "min_coverage_percent": st.floats(
        min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
    ),
    "max_leaked_secrets": st.integers(min_value=0, max_value=50),
    "max_blocking_iac_issues": st.integers(min_value=0, max_value=50),
    "max_code_smells": st.integers(min_value=0, max_value=1000),
    "max_technical_debt_minutes": st.integers(min_value=0, max_value=100_000),
    "max_security_hotspots": st.integers(min_value=0, max_value=1000),
    "min_maintainability_rating": st.sampled_from(MAINTAINABILITY_RATINGS),
}

# Field name -> strategy producing a MALFORMED value (wrong type / out of range).
_MALFORMED_FIELDS: dict[str, st.SearchStrategy[Any]] = {
    "max_critical_findings": st.one_of(st.text(max_size=5), st.integers(max_value=-1)),
    "min_coverage_percent": st.one_of(
        st.text(max_size=5), st.floats(min_value=100.0001, max_value=1e6, allow_infinity=False)
    ),
    "max_leaked_secrets": st.one_of(st.text(max_size=5), st.integers(max_value=-1)),
    "max_blocking_iac_issues": st.one_of(st.booleans(), st.integers(max_value=-1)),
    "max_code_smells": st.one_of(st.text(max_size=5), st.integers(max_value=-1)),
    "max_technical_debt_minutes": st.one_of(st.text(max_size=5), st.integers(max_value=-1)),
    "max_security_hotspots": st.one_of(st.text(max_size=5), st.integers(max_value=-1)),
    "min_maintainability_rating": st.one_of(
        st.just("Z"), st.integers(), st.just("")
    ),
}


@st.composite
def well_formed_repo_config(draw: st.DrawFn) -> dict[str, Any]:
    """A raw Repo_Config mapping containing only well-formed values.

    An arbitrary subset of fields is present (possibly empty, the "fully absent
    config" edge case), each with a valid value.
    """

    field_names = draw(
        st.lists(st.sampled_from(list(_WELL_FORMED_FIELDS)), unique=True, max_size=len(_WELL_FORMED_FIELDS))
    )
    return {name: draw(_WELL_FORMED_FIELDS[name]) for name in field_names}


@st.composite
def malformed_repo_config(draw: st.DrawFn) -> dict[str, Any]:
    """A raw Repo_Config mapping with a controlled malformed subset.

    Returns a dict with:
    - ``config``: the raw mapping (mix of well-formed and malformed values),
    - ``malformed_fields``: the set of field names given malformed values,
    - ``well_formed_fields``: the set of field names given valid values.

    Guarantees at least one malformed field so substitution tests always have a
    substitution to assert. Well-formed fields may be empty.
    """

    all_fields = list(_MALFORMED_FIELDS)
    malformed_fields = draw(
        st.lists(st.sampled_from(all_fields), unique=True, min_size=1, max_size=len(all_fields))
    )
    remaining = [f for f in all_fields if f not in malformed_fields]
    well_formed_fields = draw(
        st.lists(st.sampled_from(remaining), unique=True, max_size=len(remaining))
    ) if remaining else []

    config: dict[str, Any] = {}
    for name in malformed_fields:
        config[name] = draw(_MALFORMED_FIELDS[name])
    for name in well_formed_fields:
        config[name] = draw(_WELL_FORMED_FIELDS[name])

    return {
        "config": config,
        "malformed_fields": set(malformed_fields),
        "well_formed_fields": set(well_formed_fields),
    }


@st.composite
def config_substitutions(draw: st.DrawFn) -> ConfigSubstitution:
    return ConfigSubstitution(
        field=draw(st.sampled_from(list(_WELL_FORMED_FIELDS))),
        provided=draw(text_any),
        applied_default=draw(text_nonempty),
    )
