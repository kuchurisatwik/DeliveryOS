"""Property 7: Normalization conformance and preservation (security-pipeline).

Exercises :func:`app.security.intelligence.normalize.normalize`, the pure
Layer 3 function that converts a raw :class:`~app.security.models.Finding` into a
``Common_Schema`` :class:`~app.security.models.Normalized_Finding`.

The generated input space deliberately includes both *complete* findings and
findings with an arbitrary subset of the ``Common_Schema``-required source
fields (``scanner``, ``rule_id``, ``location``, ``severity``, ``message``)
missing or empty. Raw ``Finding`` objects are built directly with blanked
fields (``None`` / empty / whitespace-only) so the "missing required field"
edge case (Requirement 5.3) is fully exercised.

The test asserts, for every generated finding:
* the output conforms to the ``Common_Schema`` — every required field is
  populated with a non-empty value (Requirement 5.1);
* the originating scanner (when present) is retained in the ``scanners``
  provenance set, and the affected location and severity are preserved
  unchanged when present (Requirement 5.2); and
* ``defaults_applied`` equals *exactly* the set of source fields that were
  missing/empty — and is empty when nothing was missing (Requirement 5.3).

Validates: Requirements 5.1, 5.2, 5.3
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.intelligence.normalize import (
    _REQUIRED_SOURCE_FIELDS,
    normalize,
)
from app.security.models import Finding, Location, Normalized_Finding, Severity
from tests.security.strategies import identifiers, locations, severities

# --------------------------------------------------------------------------- #
# Strategies for "present" (genuinely non-empty) source-field values.
# --------------------------------------------------------------------------- #

# Text guaranteed non-blank per normalize's `_is_empty_str` (a value is "empty"
# if it is None or strips to ""). `identifiers` never contains whitespace, so it
# is always treated as present.
_present_text = identifiers

# Values that normalize treats as MISSING/EMPTY for string-like fields.
_blank_values = st.sampled_from([None, "", "   ", "\t", "\n"])


@st.composite
def findings_with_missing_fields(
    draw: st.DrawFn,
) -> tuple[Finding, frozenset[str]]:
    """A raw ``Finding`` plus the exact set of missing/empty required fields.

    For each of the five ``Common_Schema``-required source fields the strategy
    independently decides whether it is *present* (a genuinely non-empty value)
    or *missing/empty* (``None`` / blank / whitespace-only for strings, ``None``
    for location/severity). The empty subset (a fully-complete finding) and the
    full subset (everything missing) are both reachable.
    """

    missing: set[str] = set()

    # --- scanner -------------------------------------------------------- #
    if draw(st.booleans()):
        scanner = draw(_blank_values)
        missing.add("scanner")
    else:
        scanner = draw(_present_text)

    # --- rule_id -------------------------------------------------------- #
    if draw(st.booleans()):
        rule_id = draw(_blank_values)
        missing.add("rule_id")
    else:
        rule_id = draw(_present_text)

    # --- location ------------------------------------------------------- #
    # Missing == None OR a Location whose path is blank/whitespace-only.
    if draw(st.booleans()):
        location = draw(
            st.one_of(
                st.none(),
                st.builds(
                    Location,
                    path=st.sampled_from(["", "   ", "\t"]),
                    start_line=st.integers(min_value=0, max_value=10),
                    end_line=st.integers(min_value=0, max_value=10),
                ),
            )
        )
        missing.add("location")
    else:
        location = draw(locations())

    # --- severity ------------------------------------------------------- #
    if draw(st.booleans()):
        severity = None
        missing.add("severity")
    else:
        severity = draw(severities())

    # --- message -------------------------------------------------------- #
    if draw(st.booleans()):
        message = draw(_blank_values)
        missing.add("message")
    else:
        message = draw(_present_text)

    # Finding is a (frozen) dataclass without runtime type enforcement, so we can
    # construct it directly with blanked fields to model raw scanner output.
    finding = Finding(
        scanner=scanner,  # type: ignore[arg-type]
        rule_id=rule_id,  # type: ignore[arg-type]
        location=location,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        message=message,  # type: ignore[arg-type]
        raw={},
    )
    return finding, frozenset(missing)


# Feature: security-pipeline, Property 7: For any raw Finding (including ones missing schema-required fields), normalize produces a Normalized_Finding conforming to the Common_Schema, preserves the originating scanner, location, and severity, and for every missing required field assigns the documented default and records that field in defaults_applied (exactly the set of fields that were missing).
@settings(max_examples=100)
@given(case=findings_with_missing_fields())
def test_property_07_normalization_conformance_and_preservation(
    case: tuple[Finding, frozenset[str]],
) -> None:
    finding, expected_missing = case

    result = normalize(finding)

    # ------------------------------------------------------------------ #
    # (5.1) Output conforms to Common_Schema: every required field populated
    #       with a non-empty value.
    # ------------------------------------------------------------------ #
    assert isinstance(result, Normalized_Finding)
    assert isinstance(result.finding_id, str) and result.finding_id.strip() != ""
    assert isinstance(result.rule_identity, str) and result.rule_identity.strip() != ""
    assert isinstance(result.location, Location)
    assert result.location.path.strip() != ""
    assert isinstance(result.severity, Severity)
    assert isinstance(result.scanners, frozenset) and len(result.scanners) >= 1
    assert all(s.strip() != "" for s in result.scanners)
    assert isinstance(result.category, str) and result.category.strip() != ""
    assert isinstance(result.message, str) and result.message.strip() != ""

    # ------------------------------------------------------------------ #
    # (5.2) Preservation of originating scanner, location, and severity when
    #       present on the raw finding.
    # ------------------------------------------------------------------ #
    if "scanner" not in expected_missing:
        # normalize trims the scanner name before retaining it as provenance.
        assert finding.scanner.strip() in result.scanners
    if "location" not in expected_missing:
        assert result.location == finding.location
    if "severity" not in expected_missing:
        assert result.severity == finding.severity

    # ------------------------------------------------------------------ #
    # (5.3) defaults_applied equals EXACTLY the set of missing/empty fields;
    #       empty when nothing was missing. Every recorded name is a valid
    #       required source field and appears at most once.
    # ------------------------------------------------------------------ #
    applied = result.defaults_applied
    assert len(applied) == len(set(applied))  # no duplicate records
    assert set(applied) <= set(_REQUIRED_SOURCE_FIELDS)
    assert set(applied) == set(expected_missing)
    if not expected_missing:
        assert applied == ()
