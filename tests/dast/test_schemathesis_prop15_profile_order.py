# Feature: dast-schemathesis, Property 15: Schemathesis is present in both profiles and ordered before the active ZAP scan
"""Property 15 — Schemathesis is present in both profiles and ordered before the
active ZAP scan.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**

Schemathesis wires into the existing two-tier runner exactly once per profile, and
its position in the serial mutating tier is load-bearing: because ``run_scan`` runs
mutating tools serially *in list order*, ``default_adapters`` must place the
``SchemathesisAdapter`` **before** the active ``ZapAdapter`` so ZAP's site tree is
seeded with real, authenticated traffic before the active scan attacks it. So, over
any profile value:

* the ``fast`` and ``deep`` profiles each contain exactly one ``SchemathesisAdapter``
  (Req 10.1, 10.2);
* that adapter's ``mutating`` flag is ``True``, so the runner assigns it to the serial
  mutating tier rather than the concurrent read-only tier (Req 10.3);
* whenever the active ZAP adapter is also present, Schemathesis precedes it in the
  mutating-tier ordering the runner builds (Req 10.4); and
* Schemathesis is still included and run when the active ZAP adapter is absent, i.e.
  it does not depend on ZAP's presence (Req 10.5).

The invariant is checked against ``dast.runner.default_adapters`` and the same
order-preserving mutating-tier filter ``run_scan`` uses — no subprocess, no network.
"""

from __future__ import annotations

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from dast.adapters import SchemathesisAdapter, ZapAdapter
from dast.runner import default_adapters

#: The two named profiles the service ships with.
_KNOWN_PROFILES = ("fast", "deep")


# --------------------------------------------------------------------------- #
# Helpers — mirror how run_scan derives the serial mutating tier
# --------------------------------------------------------------------------- #
def _mutating_tier(adapters: list[object]) -> list[object]:
    """The serial mutating tier, built exactly as ``run_scan`` builds it.

    ``run_scan`` filters the tool list to the mutating tools while preserving list
    order, so replicating that filter here lets the property assert over the precise
    execution order the runner will use.
    """
    return [t for t in adapters if getattr(t, "mutating", False)]


def _is_schemathesis(adapter: object) -> bool:
    return isinstance(adapter, SchemathesisAdapter)


def _is_active_zap(adapter: object) -> bool:
    """The active ZAP adapter — the mutating ZAP face whose site tree Schemathesis seeds."""
    return isinstance(adapter, ZapAdapter) and getattr(adapter, "name", None) == "zap-active"


# --------------------------------------------------------------------------- #
# Strategy — the whole profile input space: the two known profiles plus arbitrary
# text (any non-"deep" string behaves like the fast profile).
# --------------------------------------------------------------------------- #
_PROFILES = st.one_of(
    st.sampled_from(_KNOWN_PROFILES),
    st.text(max_size=20),
)


# --------------------------------------------------------------------------- #
# The umbrella property over arbitrary profiles
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=200)
@given(profile=_PROFILES)
def test_schemathesis_present_mutating_and_ordered_before_active_zap(profile: str) -> None:
    """Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5

    For any profile value, exactly one Schemathesis adapter is present, it is a
    mutating-tier tool, and whenever the active ZAP adapter is present Schemathesis
    precedes it in the serial mutating-tier order; Schemathesis is included even when
    the active ZAP adapter is absent.
    """
    adapters = default_adapters(profile)

    # Exactly one Schemathesis adapter, whatever the profile (Req 10.1, 10.2, 10.5).
    schemathesis = [a for a in adapters if _is_schemathesis(a)]
    assert len(schemathesis) == 1

    # It is a mutating-tier tool (Req 10.3).
    assert schemathesis[0].mutating is True

    tier = _mutating_tier(adapters)
    # Being mutating means it lands in the serial tier the runner will execute.
    assert schemathesis[0] in tier

    active_zap = [a for a in tier if _is_active_zap(a)]
    if active_zap:
        # When both are present, Schemathesis runs first so it seeds ZAP's tree (Req 10.4).
        assert tier.index(schemathesis[0]) < tier.index(active_zap[0])
    else:
        # Absent active ZAP: Schemathesis still runs, independent of ZAP (Req 10.5).
        assert schemathesis[0] in tier


# --------------------------------------------------------------------------- #
# The two named profiles each carry exactly one Schemathesis adapter
# --------------------------------------------------------------------------- #
@hyp_settings(max_examples=100)
@given(profile=st.sampled_from(_KNOWN_PROFILES))
def test_both_named_profiles_include_exactly_one_schemathesis(profile: str) -> None:
    """Validates: Requirements 10.1, 10.2, 10.3

    Both the fast and deep profiles include exactly one mutating Schemathesis adapter.
    """
    adapters = default_adapters(profile)
    schemathesis = [a for a in adapters if _is_schemathesis(a)]
    assert len(schemathesis) == 1
    assert schemathesis[0].mutating is True


# --------------------------------------------------------------------------- #
# Example-based companions (concrete, illustrative)
# --------------------------------------------------------------------------- #
def test_example_fast_profile_has_schemathesis_and_no_active_zap() -> None:
    """Req 10.1, 10.5 — fast profile includes Schemathesis with no active ZAP present."""
    adapters = default_adapters("fast")
    assert sum(1 for a in adapters if _is_schemathesis(a)) == 1
    assert not [a for a in adapters if _is_active_zap(a)]


def test_example_deep_profile_orders_schemathesis_before_active_zap() -> None:
    """Req 10.2, 10.4 — deep profile places Schemathesis before the active ZAP scan."""
    tier = _mutating_tier(default_adapters("deep"))
    schema_idx = next(i for i, a in enumerate(tier) if _is_schemathesis(a))
    zap_idx = next(i for i, a in enumerate(tier) if _is_active_zap(a))
    assert schema_idx < zap_idx


def test_example_unknown_profile_behaves_like_fast() -> None:
    """Req 10.5 — an arbitrary profile string still includes Schemathesis, no active ZAP."""
    adapters = default_adapters("staging-smoke")
    assert sum(1 for a in adapters if _is_schemathesis(a)) == 1
    assert not [a for a in adapters if _is_active_zap(a)]
