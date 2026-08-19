"""Schemathesis configuration tests.

These assert the ``DAST_SCHEMATHESIS_*`` defaults load and, most importantly, that the
Schemathesis version is pinned to an exact, immutable released version — never a
mutable tag like ``latest`` or a branch reference. The tool that decides whether a
build passes must not change without a reviewed change to the pinned identifier.

Settings are constructed with ``_env_file=None`` and a cleared environment so the tests
observe the code's declared defaults rather than whatever a local ``.env`` or shell
happens to set.
"""

import re

import pytest

from dast.config import DastSettings

# Every Schemathesis knob the design documents, with its documented default.
SCHEMATHESIS_DEFAULTS = {
    "DAST_SCHEMATHESIS_VERSION": "3.39.5",
    "DAST_SCHEMATHESIS_SCHEMA_FILE": None,
    "DAST_SCHEMATHESIS_SCHEMA_TIMEOUT": 30,
    "DAST_SCHEMATHESIS_SEED": 0,
    "DAST_SCHEMATHESIS_RATE_LIMIT": 10,
    "DAST_SCHEMATHESIS_CONNECT_TIMEOUT": 30,
    "DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT": 5,
    "DAST_SCHEMATHESIS_TIMEOUT": 900,
    "DAST_SCHEMATHESIS_TIMEOUT_THRESHOLD": 50,
    "DAST_SCHEMATHESIS_PROD_URL_PATTERN": None,
}

# Mutable references that must never appear as the pinned version (Req 14.1).
_MUTABLE_TAGS = {"latest", "stable", "main", "master", "head", "edge", "dev", "nightly"}

# An exact released version: SemVer core with optional pre-release/build metadata.
_EXACT_VERSION = re.compile(
    r"^\d+\.\d+(?:\.\d+)?(?:[-.][0-9A-Za-z.]+)?$"
)


@pytest.fixture()
def settings(monkeypatch):
    """A DastSettings instance built from declared defaults only.

    Clears any ``DAST_SCHEMATHESIS_*`` environment overrides and disables ``.env``
    loading so the assertions below reflect the code's defaults.
    """
    for key in SCHEMATHESIS_DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    return DastSettings(_env_file=None)


def test_schemathesis_defaults_load(settings):
    """Every documented Schemathesis default loads with its expected value (Req 13.2)."""
    for name, expected in SCHEMATHESIS_DEFAULTS.items():
        assert getattr(settings, name) == expected, name


def test_default_rate_limit_is_ten(settings):
    """The default request rate is 10 rps for a single-worker target (Req 13.2)."""
    assert settings.DAST_SCHEMATHESIS_RATE_LIMIT == 10


def test_version_is_a_non_empty_string(settings):
    version = settings.DAST_SCHEMATHESIS_VERSION
    assert isinstance(version, str)
    assert version.strip() != ""


def test_version_is_an_exact_pinned_version_not_latest_or_branch(settings):
    """The version names a single released version, never a mutable tag (Req 14.1)."""
    version = settings.DAST_SCHEMATHESIS_VERSION.strip()

    # Not a known mutable/rolling tag.
    assert version.lower() not in _MUTABLE_TAGS, version

    # Does not smell like a branch reference (e.g. 'branch/foo', 'refs/heads/x', 'git+...').
    lowered = version.lower()
    for marker in ("latest", "branch", "refs/", "heads/", "git+", "://", "@"):
        assert marker not in lowered, f"version {version!r} looks like a mutable/branch ref"

    # Names an exact, immutable released version (SemVer-ish).
    assert _EXACT_VERSION.match(version), (
        f"version {version!r} is not an exact released version identifier"
    )


def test_no_schemathesis_setting_uses_security_prefix():
    """Schemathesis config is DAST_-prefixed and never SECURITY_-prefixed (Req 1.6)."""
    schemathesis_fields = [
        name
        for name in DastSettings.model_fields
        if "SCHEMATHESIS" in name
    ]
    # Sanity: the settings we expect are actually present.
    assert set(SCHEMATHESIS_DEFAULTS).issubset(set(schemathesis_fields))

    for name in schemathesis_fields:
        assert name.startswith("DAST_"), name
        assert not name.startswith("SECURITY_"), name
