"""Durable scan records — JSON files on disk.

Deliberately not a database. The SAST pipeline persists the same way, the volume
is small (one file per scan), and a file per scan is trivially inspectable when
someone asks "what did the scanner actually see?". The read/write surface here is
narrow enough that swapping in a real store later touches only this module.

Writes are atomic (temp file + replace) so a crash mid-write cannot leave a
half-written record that later fails to parse.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import time
import uuid
from typing import Any

from app.security.models import Finding
from app.utils.logger import logger
from dast.config import dast_settings
from dast.models import ScanRecord

_SCANS_SUBDIR = "scans"


def new_scan_id() -> str:
    """A short, unique, URL-safe id for one scan."""
    return uuid.uuid4().hex[:12]


def finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Serialise a shared ``Finding`` for storage and for the API.

    ``raw`` is kept: for a dynamic finding it holds the request and response that
    prove it, which is the first thing anyone triaging the finding wants to see.
    """
    return {
        "scanner": finding.scanner,
        "rule_id": finding.rule_id,
        "severity": finding.severity.name,
        "category": finding.category,
        "message": finding.message,
        "location": {
            "path": finding.location.path,
            "symbol": finding.location.symbol,
        },
        "raw": _json_safe(finding.raw),
    }


def _json_safe(value: Any) -> Any:
    """Best-effort conversion of arbitrary tool payloads into JSON-serialisable data."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _scans_dir() -> str:
    path = os.path.join(dast_settings.DAST_STATE_DIR, _SCANS_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _record_path(scan_id: str) -> str:
    return os.path.join(_scans_dir(), f"{scan_id}.json")


#: ``os.replace`` can fail transiently on Windows: a virus scanner or the search
#: indexer opens a freshly created file for a few milliseconds, and the rename
#: comes back as ``PermissionError`` (WinError 5/32). Retrying briefly is the
#: standard remedy — without it a scan silently disappears from the UI.
_REPLACE_ATTEMPTS = 5
_REPLACE_BACKOFF_SECONDS = 0.05

#: Reads race against those same writes — a UI poll routinely lands mid-``replace``.
_READ_ATTEMPTS = 4
_READ_BACKOFF_SECONDS = 0.03


def save(record: ScanRecord) -> None:
    """Persist a scan record atomically. Never raises — storage is not the scan."""
    path = _record_path(record.scan_id)
    try:
        payload = json.dumps(dataclasses.asdict(record), indent=2, default=str)
        directory = os.path.dirname(path)
        fd, temp_path = tempfile.mkstemp(prefix=".dast-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            _replace_with_retry(temp_path, path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:  # pragma: no cover - best effort
                pass
            raise
    except Exception as exc:  # noqa: BLE001 - a failed write must not fail the scan
        logger.error("Could not persist scan record %s: %s", record.scan_id, exc)


def _replace_with_retry(temp_path: str, path: str) -> None:
    """``os.replace`` with a short retry on transient Windows file locks."""
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(temp_path, path)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_BACKOFF_SECONDS * (attempt + 1))


def load(scan_id: str) -> ScanRecord | None:
    """Read one scan record, or ``None`` when it genuinely does not exist.

    Retries transient read failures for the same reason :func:`save` retries the
    rename. A scan is written repeatedly as it progresses (queued → running →
    done), so a poll from the UI regularly lands *during* an ``os.replace``. On
    Windows, opening the destination mid-swap fails — and returning ``None`` there
    makes the API answer "no such scan" for a scan that plainly exists, which then
    looks to the caller like the scan was lost.
    """
    path = _record_path(scan_id)
    for attempt in range(_READ_ATTEMPTS):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return ScanRecord(**json.load(fh))
        except (OSError, ValueError, TypeError):
            # Could be mid-write, mid-replace, or momentarily locked. Only conclude
            # the record is absent after the retries are exhausted.
            if attempt == _READ_ATTEMPTS - 1:
                return None
            time.sleep(_READ_BACKOFF_SECONDS * (attempt + 1))
    return None  # pragma: no cover - loop always returns


def list_recent(limit: int = 25) -> list[ScanRecord]:
    """Return the most recently submitted scan records, newest first."""
    directory = _scans_dir()
    records: list[ScanRecord] = []
    try:
        names = [n for n in os.listdir(directory) if n.endswith(".json")]
    except OSError:  # pragma: no cover - directory just created above
        return []
    for name in names:
        record = load(name[: -len(".json")])
        if record is not None:
            records.append(record)
    records.sort(key=lambda r: r.submitted_at, reverse=True)
    return records[:limit]
