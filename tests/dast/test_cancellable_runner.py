"""The cancellable runner completes normally and aborts early on target death.

This is the mechanism behind nuclei's early-bail: a watchdog probes the target
while the subprocess runs and kills it the moment the target is confirmed down, so
a long scan against a crashed host degrades to a fast, honest failure instead of
grinding on to the full timeout.

Uses ``sys.executable`` as a stand-in long/short process — no nuclei, no network.
"""

from __future__ import annotations

import sys
import time

import pytest

from app.security.detection.adapters.base import ScannerError
from dast.adapters.base import run_scanner_cancellable


def test_completes_normally_and_captures_output():
    result = run_scanner_cancellable(
        [sys.executable, "-c", "print('hello-dast')"],
        scanner_name="nuclei",
        timeout=30,
        health_check=lambda: True,
    )
    assert result.returncode == 0
    assert "hello-dast" in result.stdout


def test_aborts_early_when_target_becomes_unreachable():
    # A process that would run for a minute, but the target reports down almost
    # immediately, so the watchdog must kill it in well under the timeout.
    started = time.monotonic()
    with pytest.raises(ScannerError) as excinfo:
        run_scanner_cancellable(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            scanner_name="nuclei",
            timeout=60,
            health_check=lambda: False,  # target is down
            health_interval=0.1,
            poll_interval=0.05,
        )
    elapsed = time.monotonic() - started
    assert "unreachable" in str(excinfo.value).lower()
    assert elapsed < 15, f"early-bail took too long ({elapsed:.1f}s)"


def test_a_broken_probe_does_not_abort_a_healthy_run():
    def boom() -> bool:
        raise RuntimeError("probe exploded")

    result = run_scanner_cancellable(
        [sys.executable, "-c", "print('ok')"],
        scanner_name="nuclei",
        timeout=30,
        health_check=boom,
        health_interval=0.1,
        poll_interval=0.05,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout
