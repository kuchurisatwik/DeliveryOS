"""Layer 3 Normalization — raw ``Finding`` -> ``Normalized_Finding`` (Requirement 5).

:func:`normalize` is a **pure, deterministic** function (no I/O, no hidden state)
that converts a single raw :class:`~app.security.models.Finding` produced by a
scanner into a :class:`~app.security.models.Normalized_Finding` conforming to the
``Common_Schema`` (Requirement 5.1). It:

* preserves the originating scanner (as the initial ``scanners`` frozenset /
  provenance), the affected location, and the scanner-assigned severity
  (Requirement 5.2);
* for every ``Common_Schema``-required field that is *missing or empty* on the raw
  finding, assigns the documented default value **and** records that field name in
  ``defaults_applied`` — the recorded set is exactly the set of missing fields
  (Requirement 5.3); and
* derives a stable ``finding_id``, a normalized cross-scanner ``rule_identity``,
  and a ``category`` (code/secret/iac/dependency/container) purely from the
  finding's own data.

Because the function is pure and deterministic, normalizing the same finding twice
always yields an identical :class:`Normalized_Finding` (identical ``finding_id``
included), which the downstream deduplication and scoring stages rely on.
"""

from __future__ import annotations

import hashlib

from app.security.models import (
    Finding,
    Location,
    Normalized_Finding,
    Severity,
)

# ---------------------------------------------------------------------------
# Documented defaults for missing / empty Common_Schema-required fields (5.3)
# ---------------------------------------------------------------------------

#: Applied when the originating scanner name is missing/empty.
DEFAULT_SCANNER = "unknown"
#: Applied when the scanner rule id is missing/empty (feeds ``rule_identity``).
DEFAULT_RULE_ID = "unknown-rule"
#: Applied when the affected location is missing/empty.
DEFAULT_LOCATION = Location(path="<unknown>", start_line=0, end_line=0)
#: Applied when the scanner-assigned severity is missing.
DEFAULT_SEVERITY = Severity.MEDIUM
#: Applied when the human-readable message is missing/empty.
DEFAULT_MESSAGE = "No description provided."
#: Applied when a scanner cannot be mapped to a known category.
DEFAULT_CATEGORY = "code"

#: The ``Common_Schema``-required source fields checked for missing/empty values.
#: The names recorded in ``defaults_applied`` are drawn from exactly this set.
_REQUIRED_SOURCE_FIELDS = ("scanner", "rule_id", "location", "severity", "message")

#: Maps an originating scanner to the ``Common_Schema`` category it produces.
_SCANNER_CATEGORY: dict[str, str] = {
    "bandit": "code",
    "semgrep": "code",
    "codeql": "code",
    "gitleaks": "secret",
    "checkov": "iac",
    "trivy": "dependency",
}


def _is_empty_str(value: object) -> bool:
    """True when ``value`` is ``None`` or a blank/whitespace-only string."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def _location_missing(location: Location | None) -> bool:
    """True when a location is absent or carries no usable path."""
    return location is None or _is_empty_str(getattr(location, "path", None))


def _canonical_path(path: str) -> str:
    """Canonicalize a file path for stable identity (OS-independent)."""
    return path.replace("\\", "/").strip()


def _normalize_rule_identity(rule_id: str) -> str:
    """Derive a normalized cross-scanner rule identity from a raw rule id.

    Normalization lowercases and trims the rule id and collapses internal
    whitespace so that the same underlying rule reported by different scanners
    canonicalizes to the same identity, enabling cross-scanner deduplication
    (Requirement 6) downstream.
    """
    return " ".join(rule_id.strip().lower().split())


def _derive_finding_id(rule_identity: str, location: Location) -> str:
    """Derive a stable, deterministic finding id from rule identity + location.

    Uses a content hash of the canonical identity components so the same finding
    always yields the same id (pure/deterministic) while distinct findings get
    distinct ids.
    """
    canonical = "|".join(
        (
            rule_identity,
            _canonical_path(location.path),
            str(location.start_line),
            str(location.end_line),
            location.symbol or "",
        )
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"finding-{digest}"


def normalize(finding: Finding) -> Normalized_Finding:
    """Convert a raw :class:`Finding` into a ``Common_Schema`` ``Normalized_Finding``.

    Pure and deterministic: the returned finding depends only on ``finding``.

    Args:
        finding: The raw scanner finding to normalize.

    Returns:
        A :class:`Normalized_Finding` with every ``Common_Schema``-required field
        populated. Missing/empty source fields are replaced by documented defaults
        and their names recorded in ``defaults_applied`` (Requirement 5.3), while
        present scanner/location/severity values are preserved (Requirement 5.2).
    """
    defaults_applied: list[str] = []

    # --- scanner (provenance) ---------------------------------------------
    raw_scanner = getattr(finding, "scanner", None)
    if _is_empty_str(raw_scanner):
        scanner = DEFAULT_SCANNER
        defaults_applied.append("scanner")
    else:
        scanner = raw_scanner.strip() if isinstance(raw_scanner, str) else raw_scanner

    # --- rule id -> normalized rule identity ------------------------------
    raw_rule_id = getattr(finding, "rule_id", None)
    if _is_empty_str(raw_rule_id):
        rule_id = DEFAULT_RULE_ID
        defaults_applied.append("rule_id")
    else:
        rule_id = raw_rule_id
    rule_identity = _normalize_rule_identity(rule_id)

    # --- location (preserved when present) --------------------------------
    raw_location = getattr(finding, "location", None)
    if _location_missing(raw_location):
        location = DEFAULT_LOCATION
        defaults_applied.append("location")
    else:
        location = raw_location

    # --- severity (preserved when present) --------------------------------
    raw_severity = getattr(finding, "severity", None)
    if raw_severity is None:
        severity = DEFAULT_SEVERITY
        defaults_applied.append("severity")
    else:
        severity = raw_severity

    # --- message ----------------------------------------------------------
    raw_message = getattr(finding, "message", None)
    if _is_empty_str(raw_message):
        message = DEFAULT_MESSAGE
        defaults_applied.append("message")
    else:
        message = raw_message

    # --- derived fields ---------------------------------------------------
    # Prefer a finding-level category hint (set by adapters whose output spans
    # multiple categories, e.g. Trivy dependency/iac/secret); otherwise fall back
    # to the scanner-wide default map.
    raw_category = getattr(finding, "category", None)
    if isinstance(raw_category, str) and raw_category.strip():
        category = raw_category.strip()
    else:
        category = _SCANNER_CATEGORY.get(
            scanner.lower() if isinstance(scanner, str) else "", DEFAULT_CATEGORY
        )
    finding_id = _derive_finding_id(rule_identity, location)

    return Normalized_Finding(
        finding_id=finding_id,
        rule_identity=rule_identity,
        location=location,
        severity=severity,
        scanners=frozenset({scanner}),
        category=category,
        message=message,
        defaults_applied=tuple(defaults_applied),
    )
