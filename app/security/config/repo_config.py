"""Per-repository ``Repo_Config`` resolution (Requirement 15).

The security pipeline resolves configuration exactly once, before the Detection
Layer runs (Requirement 1.5). Resolution follows a strict layering:

1. **Global/env settings** (``app.config.settings.settings``) are the base. These
   are process-wide defaults sourced from the environment / ``.env`` file.
2. **Documented pipeline defaults** (the ``QualityGateThresholds`` field defaults
   and empty scanner-rule/pipeline maps) fill anything the global layer does not
   provide (Requirement 15.3).
3. **Per-repository ``Repo_Config``** overrides both of the above where a value is
   present *and* well-formed (Requirement 15.1).

Malformed individual values are rejected: the corresponding documented default is
applied and a single :class:`ConfigSubstitution` naming that field is emitted
(Requirement 15.2). A fully absent config yields all defaults with no
substitutions (Requirement 15.3).

``Repo_Config`` is stored as JSON. JSON is chosen deliberately: it is available in
the standard library (no new dependency in the existing venv), and it matches the
JSON already used elsewhere in the project (e.g. the spec ``.config.kiro`` files).

The public entry point is :meth:`ConfigResolver.resolve`, returning the single
immutable :class:`ResolvedConfig` plus the list of substitutions the report later
surfaces.
"""

from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields
from typing import Any, Callable

from app.config.settings import settings
from app.security.models import (
    ConfigSubstitution,
    QualityGateThresholds,
    ResolvedConfig,
)

# Sentinel naming the whole config when the raw payload cannot be parsed at all.
_WHOLE_CONFIG_FIELD = "Repo_Config"

# The documented default thresholds (Requirement 12.3 / 15.3): zero critical
# findings, coverage >= 90%, zero leaked secrets, zero blocking IaC issues, and
# unset (None) SonarQube-derived thresholds.
_DEFAULT_THRESHOLDS = QualityGateThresholds()


def _is_int(value: Any) -> bool:
    """True for genuine ints, excluding bool (a subclass of int)."""

    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """True for genuine ints/floats, excluding bool."""

    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_negative_int(value: Any) -> bool:
    return _is_int(value) and value >= 0


def _coverage_percent(value: Any) -> bool:
    return _is_number(value) and 0.0 <= float(value) <= 100.0


def _optional_non_negative_int(value: Any) -> bool:
    return value is None or _non_negative_int(value)


def _maintainability_rating(value: Any) -> bool:
    # Sonar maintainability ratings are single letters A–E; accept case-insensitively.
    return value is None or (isinstance(value, str) and value.strip().upper() in {"A", "B", "C", "D", "E"})


# Per-threshold-field validators. Each maps a Repo_Config field name to a
# predicate that returns True when the provided value is well-formed. Fields
# absent from Repo_Config keep their documented default with no substitution.
_THRESHOLD_VALIDATORS: dict[str, Callable[[Any], bool]] = {
    "max_critical_findings": _non_negative_int,
    "min_coverage_percent": _coverage_percent,
    "max_leaked_secrets": _non_negative_int,
    "max_blocking_iac_issues": _non_negative_int,
    "max_code_smells": _optional_non_negative_int,
    "max_technical_debt_minutes": _optional_non_negative_int,
    "max_security_hotspots": _optional_non_negative_int,
    "min_maintainability_rating": _maintainability_rating,
}

# Some threshold values are coerced to their canonical type once validated.
_THRESHOLD_COERCE: dict[str, Callable[[Any], Any]] = {
    "min_coverage_percent": float,
    "min_maintainability_rating": lambda v: v if v is None else v.strip().upper(),
}


class ConfigResolver:
    """Resolves a raw ``Repo_Config`` payload into a single ``ResolvedConfig``.

    Layered on top of the global ``app.config.settings`` so env/global settings
    remain the base and per-repository ``Repo_Config`` overrides them.
    """

    @classmethod
    def resolve(
        cls, raw: str | None
    ) -> tuple[ResolvedConfig, list[ConfigSubstitution]]:
        """Resolve ``raw`` Repo_Config contents into ``(ResolvedConfig, subs)``.

        ``raw`` is the ``Repo_Config`` file contents (or ``None`` when absent).
        Returns the immutable resolved config and the list of substitutions
        recorded for malformed values.
        """

        base_scanner_rules, base_pipeline_settings = cls._base_from_global_settings()

        # Absent config -> all defaults, no substitutions (15.3).
        if raw is None:
            return (
                ResolvedConfig(
                    thresholds=_DEFAULT_THRESHOLDS,
                    scanner_rules=base_scanner_rules,
                    pipeline_settings=base_pipeline_settings,
                ),
                [],
            )

        substitutions: list[ConfigSubstitution] = []

        parsed = cls._parse(raw)
        if parsed is None:
            # Whole payload malformed: reject it wholesale, fall back to defaults,
            # and record a single substitution naming the config (15.2).
            substitutions.append(
                ConfigSubstitution(
                    field=_WHOLE_CONFIG_FIELD,
                    provided=raw if len(raw) <= 200 else raw[:197] + "...",
                    applied_default="all defaults",
                )
            )
            return (
                ResolvedConfig(
                    thresholds=_DEFAULT_THRESHOLDS,
                    scanner_rules=base_scanner_rules,
                    pipeline_settings=base_pipeline_settings,
                ),
                substitutions,
            )

        thresholds = cls._resolve_thresholds(parsed.get("thresholds"), substitutions)
        scanner_rules = cls._resolve_mapping(
            "scanner_rules", parsed.get("scanner_rules"), base_scanner_rules, substitutions
        )
        pipeline_settings = cls._resolve_mapping(
            "pipeline_settings",
            parsed.get("pipeline_settings"),
            base_pipeline_settings,
            substitutions,
        )

        return (
            ResolvedConfig(
                thresholds=thresholds,
                scanner_rules=scanner_rules,
                pipeline_settings=pipeline_settings,
            ),
            substitutions,
        )

    # ------------------------------------------------------------------
    # Base layer (global/env settings)
    # ------------------------------------------------------------------

    @staticmethod
    def _base_from_global_settings() -> tuple[dict[str, object], dict[str, object]]:
        """Seed scanner-rule and pipeline-setting maps from global settings.

        Global/env settings are the base layer; Repo_Config overrides them. Only
        settings that are meaningful to the security pipeline are surfaced here.
        """

        base_scanner_rules: dict[str, object] = {}
        base_pipeline_settings: dict[str, object] = {
            "workspace_dir": settings.WORKSPACE_DIR,
        }
        return base_scanner_rules, base_pipeline_settings

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(raw: str) -> dict[str, Any] | None:
        """Parse JSON ``Repo_Config``; return ``None`` if it is not a JSON object."""

        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(value, dict):
            return None
        return value

    # ------------------------------------------------------------------
    # Threshold resolution
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_thresholds(
        cls, raw_thresholds: Any, substitutions: list[ConfigSubstitution]
    ) -> QualityGateThresholds:
        """Resolve the ``thresholds`` block field-by-field against defaults."""

        # Absent thresholds block -> all documented defaults, no substitution.
        if raw_thresholds is None:
            return _DEFAULT_THRESHOLDS

        # Present but not an object -> reject wholesale, one substitution.
        if not isinstance(raw_thresholds, dict):
            substitutions.append(
                ConfigSubstitution(
                    field="thresholds",
                    provided=repr(raw_thresholds),
                    applied_default="default thresholds",
                )
            )
            return _DEFAULT_THRESHOLDS

        resolved: dict[str, Any] = {}
        for f in dataclass_fields(QualityGateThresholds):
            name = f.name
            default_value = getattr(_DEFAULT_THRESHOLDS, name)
            if name not in raw_thresholds:
                resolved[name] = default_value
                continue

            provided = raw_thresholds[name]
            validator = _THRESHOLD_VALIDATORS[name]
            if validator(provided):
                coerce = _THRESHOLD_COERCE.get(name)
                resolved[name] = coerce(provided) if coerce else provided
            else:
                # Malformed value: apply default + record exactly one substitution.
                resolved[name] = default_value
                substitutions.append(
                    ConfigSubstitution(
                        field=f"thresholds.{name}",
                        provided=repr(provided),
                        applied_default=repr(default_value),
                    )
                )

        return QualityGateThresholds(**resolved)

    # ------------------------------------------------------------------
    # Mapping resolution (scanner_rules / pipeline_settings)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_mapping(
        field_name: str,
        raw_value: Any,
        base: dict[str, object],
        substitutions: list[ConfigSubstitution],
    ) -> dict[str, object]:
        """Overlay a Repo_Config mapping onto its base map.

        Absent -> base unchanged (no substitution). Present-but-not-an-object ->
        reject, keep base, and record one substitution.
        """

        if raw_value is None:
            return dict(base)

        if not isinstance(raw_value, dict):
            substitutions.append(
                ConfigSubstitution(
                    field=field_name,
                    provided=repr(raw_value),
                    applied_default=repr(base),
                )
            )
            return dict(base)

        merged = dict(base)
        merged.update(raw_value)
        return merged
