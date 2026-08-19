"""Runner tests — Schemathesis profile membership and mutating-tier ordering.

These assert over the adapter set that ``default_adapters`` builds, so no tool,
target, or network is involved. They pin the design commitments in Requirement 10:
Schemathesis is present exactly once in both profiles, declares itself mutating, and
is ordered ahead of the active ZAP adapter in the serial mutating tier so its traffic
seeds ZAP's site tree before the active scan.
"""

from dast.adapters import SchemathesisAdapter, ZapAdapter
from dast.runner import default_adapters


def _schemathesis_adapters(adapters):
    return [a for a in adapters if isinstance(a, SchemathesisAdapter)]


def _mutating_in_order(adapters):
    """The serial mutating tier, built the way the runner builds it: filter to
    ``mutating`` truthy while preserving list order."""
    return [a for a in adapters if getattr(a, "mutating", False)]


def test_fast_profile_has_exactly_one_schemathesis_adapter():
    # Validates: Requirements 10.1
    adapters = default_adapters("fast")
    assert len(_schemathesis_adapters(adapters)) == 1


def test_deep_profile_has_exactly_one_schemathesis_adapter():
    # Validates: Requirements 10.2
    adapters = default_adapters("deep")
    assert len(_schemathesis_adapters(adapters)) == 1


def test_schemathesis_adapter_is_mutating():
    # Validates: Requirements 10.3
    (schemathesis,) = _schemathesis_adapters(default_adapters("deep"))
    assert schemathesis.mutating is True


def test_deep_profile_places_schemathesis_before_active_zap_in_mutating_tier():
    # Validates: Requirements 10.4
    mutating = _mutating_in_order(default_adapters("deep"))

    schemathesis_index = next(
        i for i, a in enumerate(mutating) if isinstance(a, SchemathesisAdapter)
    )
    active_zap_index = next(
        i
        for i, a in enumerate(mutating)
        if isinstance(a, ZapAdapter) and getattr(a, "mutating", False)
    )

    # The active ZAP adapter ("zap-active") is the mutating ZAP face.
    assert mutating[active_zap_index].name == "zap-active"
    assert schemathesis_index < active_zap_index
