"""Storage tests, including the read/write race a real scan exposed.

A scan record is rewritten every time the scan advances (queued → running →
done), while the UI polls it several times a second. Both sides of that race
produced a real bug on the first live run against Juice Shop.
"""

import threading
import time

import pytest

from dast import storage
from dast.models import ScanRecord


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.dast_settings, "DAST_STATE_DIR", str(tmp_path))


def _record(scan_id="abc123", status="queued") -> ScanRecord:
    return ScanRecord(
        scan_id=scan_id,
        target_url="https://staging.test",
        commit_sha="deadbeef",
        profile="fast",
        kind="deploy",
        status=status,
    )


def test_round_trip():
    storage.save(_record())
    loaded = storage.load("abc123")
    assert loaded is not None
    assert loaded.target_url == "https://staging.test"
    assert loaded.status == "queued"


def test_missing_scan_returns_none():
    assert storage.load("nope") is None


def test_save_overwrites_in_place():
    storage.save(_record(status="queued"))
    storage.save(_record(status="done"))
    assert storage.load("abc123").status == "done"


def test_list_recent_is_newest_first():
    for i in range(3):
        r = _record(scan_id=f"s{i}")
        r.submitted_at = 1000 + i
        storage.save(r)
    assert [r.scan_id for r in storage.list_recent()] == ["s2", "s1", "s0"]


def test_concurrent_writes_never_make_a_scan_look_missing():
    """A poll landing mid-write must not report 'no such scan'.

    This is the bug the first live scan hit: the request thread writes the record
    at submit time while the queue worker immediately rewrites it as ``running``.
    A read landing inside that window failed transiently, :func:`storage.load`
    returned ``None``, and the API answered 404 for a scan that plainly existed.

    **Two** writers are required to reproduce it — with a single writer the window
    is too narrow and this test passes even with the retries removed, which is
    exactly how the first version of it fooled us.
    """
    storage.save(_record())
    stop = threading.Event()
    misses: list[str] = []

    def writer():
        n = 0
        while not stop.is_set():
            storage.save(_record(status="running" if n % 2 else "queued"))
            n += 1

    def reader():
        while not stop.is_set():
            if storage.load("abc123") is None:
                misses.append("phantom 404")

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=writer),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    time.sleep(1.5)
    stop.set()
    for t in threads:
        t.join()

    assert not misses, f"record appeared missing {len(misses)} time(s) during writes"


def test_findings_are_serialised_with_severity_names():
    from app.security.models import Finding, Location, Severity

    finding = Finding(
        scanner="nuclei",
        rule_id="CVE-2021-44228",
        location=Location(path="/api/x", start_line=0, end_line=0, symbol="q"),
        severity=Severity.CRITICAL,
        message="log4shell",
        raw={"matched-at": "https://x/api/x"},
        category="dast",
    )
    payload = storage.finding_to_dict(finding)
    assert payload["severity"] == "CRITICAL"
    assert payload["location"] == {"path": "/api/x", "symbol": "q"}
    assert payload["raw"]["matched-at"] == "https://x/api/x"


def test_unserialisable_raw_payload_does_not_break_storage():
    from app.security.models import Finding, Location, Severity

    finding = Finding(
        scanner="nuclei",
        rule_id="x",
        location=Location(path="/", start_line=0, end_line=0),
        severity=Severity.LOW,
        message="m",
        raw={"obj": object()},
    )
    assert isinstance(storage.finding_to_dict(finding)["raw"], str)
