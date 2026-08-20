"""The seeding import uses a generous timeout, ordinary calls keep the short one.

ZAP's OpenAPI import is a single synchronous REST call during which ZAP fetches
every endpoint, so on a large spec / slow target it easily outruns the short
default per-call timeout. These tests pin that the import (and spider) call is
issued with the dedicated ``DAST_ZAP_IMPORT_TIMEOUT`` while a normal view call is
issued with no per-call override (i.e. the client's short default applies).

A tiny recording stand-in for ``httpx.Client`` captures the ``timeout`` each call
was issued with — no network, no real ZAP.
"""

from __future__ import annotations

from typing import Any

from dast.adapters.zap_client import ZapClient
from dast.config import DastSettings


class _Resp:
    """Minimal httpx.Response stand-in: a 200 with an empty JSON object."""

    status_code = 200

    def json(self) -> dict[str, Any]:
        # Carries fields the pollers read (status=100 → "done") so a spider call
        # completes without a real ZAP; other callers just ignore the extra keys.
        return {"status": "100", "scan": "0"}


class _RecordingHttpx:
    """Records the ``timeout`` kwarg each ``get`` was called with."""

    def __init__(self) -> None:
        self.timeouts: list[Any] = []

    def get(self, path: str, **kwargs: Any) -> _Resp:
        # Sentinel distinguishes "no per-call timeout given" from an explicit None.
        self.timeouts.append(kwargs.get("timeout", "UNSET"))
        return _Resp()


def _settings() -> DastSettings:
    return DastSettings(DAST_ZAP_IMPORT_TIMEOUT=300, DAST_ZAP_API_KEY=None)


def test_import_openapi_uses_import_timeout() -> None:
    rec = _RecordingHttpx()
    client = ZapClient(settings=_settings(), client=rec)  # type: ignore[arg-type]

    client.import_openapi("http://dast:8020/spec.json", target_url="http://target")

    assert rec.timeouts == [300]


def test_spider_uses_import_timeout_for_the_scan_kickoff() -> None:
    rec = _RecordingHttpx()
    client = ZapClient(settings=_settings(), client=rec)  # type: ignore[arg-type]

    # spider() kicks off the scan (import-timeout) then polls status; the stub reads
    # status=100 on the first poll so it returns cleanly. The kickoff call is what
    # must carry the import timeout.
    client.spider("http://target", timeout=5)

    assert rec.timeouts[0] == 300


def test_ordinary_view_call_has_no_per_call_timeout_override() -> None:
    rec = _RecordingHttpx()
    client = ZapClient(settings=_settings(), client=rec)  # type: ignore[arg-type]

    client.urls(base_url="http://target")

    # No override → the client's configured default applies (recorded as UNSET).
    assert rec.timeouts == ["UNSET"]
