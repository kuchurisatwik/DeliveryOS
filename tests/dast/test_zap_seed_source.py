"""ZAP seeds from the engine-synthesised spec URL when the scope carries one.

These tests lock in the endpoint-engine → ZAP integration: when the service
synthesises an OpenAPI spec (because the target publishes none) and serves it back
at ``DastScope.spec_url``, the ZAP adapter must import *that* URL to seed its site
tree — not the target's own (absent) ``/openapi.json``. When ``spec_url`` is unset,
the adapter must keep its prior behaviour of importing the target's spec path, so
scans of spec-publishing targets are unchanged.

They use the in-memory :class:`FakeZapClient`, whose ``import_openapi`` records the
exact URL it was asked to fetch as the first seed request — which is what lets us
assert *which* spec ZAP was pointed at, with no network.
"""

from __future__ import annotations

from dast.adapters.zap_adapter import ZapAdapter
from dast.config import DastSettings
from dast.models import DastScope

from tests.dast._zap_fakes import FakeZapClient

TARGET = "http://target.internal"


def _settings() -> DastSettings:
    """A ZAP settings object with the knobs this scan flow reads, all local."""
    return DastSettings(
        DAST_OPENAPI_PATH="/openapi.json",
        DAST_ZAP_CANARY_PATH="/canary/xss",
        DAST_ZAP_LOGOUT_EXCLUDE=".*/logout.*",
        DAST_ZAP_RATE_LIMIT=20,
        DAST_ZAP_COVERAGE_TOLERANCE=0.8,
        DAST_ZAP_TIMEOUT_THRESHOLD=20,
    )


def _fake() -> FakeZapClient:
    """A fake that seeds two endpoints and passes both canary boundaries."""
    return FakeZapClient(
        reachable=True,
        seedable_endpoints=[f"{TARGET}/canary/xss", f"{TARGET}/items"],
        canary_at_start=True,
        canary_at_end=True,
        requests_made=5,
    )


def test_seeds_from_spec_url_when_present() -> None:
    """A scope with ``spec_url`` set makes ZAP import our synthesised spec."""
    fake = _fake()
    adapter = ZapAdapter(active=False, client=fake, settings=_settings())
    spec_url = "http://dast:8020/internal/openapi/abc123"

    adapter.scan(
        DastScope(
            target_url=TARGET,
            spec_paths=("/canary/xss", "/items"),
            spec_url=spec_url,
            profile="fast",
        )
    )

    # The very first request ZAP makes is the spec import fetch; it must be OUR URL.
    assert fake.sent_requests[0].url == spec_url


def test_falls_back_to_target_openapi_path_when_spec_url_absent() -> None:
    """Without ``spec_url`` the adapter imports the target's own spec path (unchanged)."""
    fake = _fake()
    adapter = ZapAdapter(active=False, client=fake, settings=_settings())

    adapter.scan(
        DastScope(
            target_url=TARGET,
            spec_paths=("/canary/xss", "/items"),
            profile="fast",
        )
    )

    assert fake.sent_requests[0].url == f"{TARGET}/openapi.json"
