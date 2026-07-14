"""Property 18: Configuration substitution (Requirement 15.2).

# Feature: security-pipeline, Property 18: For any Repo_Config containing an
# arbitrary subset of malformed values, each malformed field resolves to its
# documented default and produces exactly one ConfigSubstitution naming that
# field, while well-formed fields produce no substitution.

Validates: Requirements 15.2
"""

from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.config.repo_config import ConfigResolver
from app.security.models import QualityGateThresholds
from tests.security.strategies import malformed_repo_config

# Documented default thresholds (Requirement 15.3 / 12.3).
_DEFAULTS = QualityGateThresholds()

# The resolver names malformed threshold substitutions as ``thresholds.<field>``.
_THRESHOLD_FIELD_NAMES = {f.name for f in dataclass_fields(QualityGateThresholds)}


@settings(max_examples=100)
@given(malformed_repo_config())
def test_property_18_config_substitution(sample: dict) -> None:
    config = sample["config"]
    malformed_fields = sample["malformed_fields"]
    well_formed_fields = sample["well_formed_fields"]

    # The resolver consumes JSON text with a top-level ``thresholds`` object.
    raw = json.dumps({"thresholds": config})

    resolved, substitutions = ConfigResolver.resolve(raw)

    # Index substitutions by their (thresholds-qualified) field name.
    sub_fields = [s.field for s in substitutions]

    # Every substitution names a threshold field (no spurious substitutions).
    for s in substitutions:
        assert s.field.startswith("thresholds."), s.field
        assert s.field[len("thresholds.") :] in _THRESHOLD_FIELD_NAMES, s.field

    # Exactly one substitution per malformed field, and no more substitutions
    # than malformed fields (well-formed fields add none).
    assert len(substitutions) == len(malformed_fields)

    for name in malformed_fields:
        qualified = f"thresholds.{name}"
        # Exactly one ConfigSubstitution naming this malformed field.
        assert sub_fields.count(qualified) == 1, (name, sub_fields)
        # The malformed field resolves to its documented default.
        assert getattr(resolved.thresholds, name) == getattr(_DEFAULTS, name)

    # Well-formed fields produce no substitution.
    for name in well_formed_fields:
        qualified = f"thresholds.{name}"
        assert qualified not in sub_fields, (name, sub_fields)


if __name__ == "__main__":  # pragma: no cover
    test_property_18_config_substitution()
