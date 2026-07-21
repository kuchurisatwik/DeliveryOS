"""Per-repository scan state — powers the ``auto`` scan scope (first-scan = full).

The ``auto`` scope mode wants a simple, durable answer to one question: *have we
ever successfully security-scanned this repository before?* If not, the pipeline
scans the **whole repo** (onboarding baseline); afterwards it scans only the
commit's changed files.

This module keeps that answer in a small JSON file **on the pipeline side** (never
inside the scanned repo), keyed by repository full name (``owner/repo``). It is
intentionally dependency-free and fail-open:

* a missing / unreadable / corrupt state file makes every repo look like a
  first scan (so a repo can never silently skip its onboarding full scan), and
* writes are atomic (temp file + replace) so a crash mid-write cannot corrupt the
  store for the next run.

For a single-instance deployment the JSON file is sufficient. A multi-instance /
HA deployment should swap in a DB-backed implementation of the same tiny surface
(:meth:`is_first_scan` / :meth:`mark_scanned`).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

from app.utils.logger import logger


class JsonFileRepoScanState:
    """JSON-file-backed record of which repositories have been scanned."""

    def __init__(self, path: str) -> None:
        self._path = path

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def is_first_scan(self, repository: str) -> bool:
        """True when ``repository`` has no recorded successful scan yet.

        Fail-open: any read problem is treated as "first scan" so onboarding's
        whole-repo scan is never skipped due to a missing/corrupt state file.
        """
        if not repository:
            return False
        return repository not in self._load()

    def mark_scanned(self, repository: str, commit_sha: str | None = None) -> None:
        """Record that ``repository`` has been successfully scanned (idempotent)."""
        if not repository:
            return
        data = self._load()
        data[repository] = {
            "first_scanned_at": data.get(repository, {}).get("first_scanned_at")
            or datetime.now(timezone.utc).isoformat(),
            "last_commit": commit_sha or "",
        }
        self._save(data)

    # ------------------------------------------------------------------ #
    # I/O (fail-open)
    # ------------------------------------------------------------------ #
    def _load(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        try:
            parent = os.path.dirname(self._path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            # Atomic write: temp file in the same dir, then replace.
            fd, tmp = tempfile.mkstemp(prefix="scanstate-", suffix=".json", dir=parent or None)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                os.replace(tmp, self._path)
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:  # pragma: no cover
                        pass
        except OSError as exc:  # pragma: no cover - best effort
            logger.warning("Failed to persist repo scan state to %s: %s", self._path, exc)


def default_state_path() -> str:
    """Resolve the state-file path from ``SECURITY_STATE_DIR`` (pipeline-side)."""
    try:
        from app.config.settings import settings

        state_dir = getattr(settings, "SECURITY_STATE_DIR", "") or os.path.join(
            ".deliveryos", "state"
        )
    except Exception:  # noqa: BLE001 - never break scope resolution on settings
        state_dir = os.path.join(".deliveryos", "state")
    return os.path.join(state_dir, "scanned_repos.json")


def get_default_state() -> JsonFileRepoScanState:
    """Return the default JSON-file-backed scan-state store."""
    return JsonFileRepoScanState(default_state_path())
