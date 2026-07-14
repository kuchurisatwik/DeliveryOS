"""Property 17: Configuration resolution (security-pipeline).

Exercises ``ConfigResolver.resolve`` against arbitrary well-formed
``Repo_Config`` inputs (including the fully-absent config) to assert that every
resolved threshold, scanner-rule, and pipeline setting equals the provided value
where the config supplies a well-formed value, and equals the documented default
everywhere else.

Validates: Requirements 12.2, 12.3, 15.1, 15.3
"""

from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.config.repo_config import ConfigResolver
from app.security.models import QualityGateThresholds
from tests.security.strategies import well_formed_repo_config

# The documented defaults the resolver falls back to (Requirement 12.3 / 15.3).
_DEFAULT_THRESHOLDS = QualityGateThresholds()

# The base scanner-rule / pipeline-setting maps seeded from global settings.
# Resolving an absent config surfaces exactly these as the documented defaults.
_BASE_SCANNER_RULES, _BASE_PIPELINE_SETTINGS = (
    ConfigResolver._base_from_global_settings()
)


def _expected_threshold_value(name: str, provided):
    """Mirror the resolver's canonical coercion for a well-formed value."""

    if name == "min_coverage_percent":
        return float(provided)
    if name == "min_maintainability_rating":
        return provided if provided is None else provided.strip().upper()
    return provided


# Feature: security-pipeline, Property 17: For any Repo_Config (including fully absent), each resolved threshold, scanner-rule, and pipeline setting equals the provided value where the config supplies a well-formed value and equals the documented default everywhere else.
@settings(max_examples=200)
@given(config=well_formed_repo_config())
def test_property_17_config_resolution_well_formed(config: dict) -> None:
    # The resolver reads a top-level ``thresholds`` object from the JSON payload.
    raw = json.dumps({"thresholds": config})

    resolved, substitutions = ConfigResolver.resolve(raw)

    # Well-formed values never produce substitutions.
    assert substitutions == []

    # Every threshold field: provided (coerced) where supplied, default elsewhere.
    for f in dataclass_fields(QualityGateThresholds):
        name = f.name
        resolved_value = getattr(resolved.thresholds, name)
        if name in config:
            assert resolved_value == _expected_threshold_value(name, config[name]), (
                f"provided field {name} was not honored"
            )
        else:
            assert resolved_value == getattr(_DEFAULT_THRESHOLDS, name), (
                f"unprovided field {name} did not fall back to its default"
            )

    # Scanner-rule and pipeline-setting maps: no Repo_Config override supplied, so
    # they equal the documented base/default maps everywhere.
    assert dict(resolved.scanner_rules) == _BASE_SCANNER_RULES
    assert dict(resolved.pipeline_settings) == _BASE_PIPELINE_SETTINGS


# Feature: security-pipeline, Property 17: For any Repo_Config (including fully absent), each resolved threshold, scanner-rule, and pipeline setting equals the provided value where the config supplies a well-formed value and equals the documented default everywhere else.
@settings(max_examples=100)
@given(_seed=st.integers())
def test_property_17_absent_config_yields_all_defaults(_seed: int) -> None:
    # Fully-absent config (None) yields all documented defaults and no substitutions.
    resolved, substitutions = ConfigResolver.resolve(None)

    assert substitutions == []
    assert resolved.thresholds == _DEFAULT_THRESHOLDS
    for f in dataclass_fields(QualityGateThresholds):
        assert getattr(resolved.thresholds, f.name) == getattr(
            _DEFAULT_THRESHOLDS, f.name
        )
    assert dict(resolved.scanner_rules) == _BASE_SCANNER_RULES
    assert dict(resolved.pipeline_settings) == _BASE_PIPELINE_SETTINGS
