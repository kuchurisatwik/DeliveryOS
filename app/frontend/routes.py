"""One-page frontend for the security pipeline.

Serves a single static page (``GET /``) plus a thin JSON API the page uses to:

* view/update a handful of runtime settings (``/api/config``),
* register a repository and see the webhook URL to paste into GitHub
  (``/api/repos``),
* manually trigger a **whole-repo** scan (``/api/scan``), and
* poll recent scan jobs + queue stats (``/api/jobs``).

Both webhook pushes and manual scans go through the same in-process
:class:`~app.workflows.scan_queue.ScanQueue`, so the jobs list shows both.
Repositories are stored in a small JSON file under ``SECURITY_STATE_DIR`` (no DB).
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config.settings import settings
from app.schemas.webhook import PushEventSchema, RepositorySchema
from app.utils.logger import logger

router = APIRouter(tags=["frontend"])

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

#: Runtime-editable settings surfaced in the UI (safe subset; no secrets).
_EDITABLE = [
    "PIPELINE_MODE",
    "SECURITY_SCAN_SCOPE",
    "SECURITY_SCAN_WORKERS",
    "SECURITY_TRIAGE_MODE",
    "SECURITY_CORRELATE_FINDINGS",
    "SECURITY_VERIFY_PATCHES",
    "SECURITY_CODEQL_COMPILED",
]


# --------------------------------------------------------------------------- #
# Tiny JSON repo store (under SECURITY_STATE_DIR)
# --------------------------------------------------------------------------- #
def _repos_path() -> str:
    state_dir = getattr(settings, "SECURITY_STATE_DIR", "") or os.path.join(
        ".deliveryos", "state"
    )
    return os.path.join(state_dir, "repos.json")


def _load_repos() -> list[dict]:
    try:
        with open(_repos_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_repos(repos: list[dict]) -> None:
    path = _repos_path()
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(repos, fh, indent=2)


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
@router.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@router.get("/api/config")
def get_config(request: Request):
    cfg = {k: getattr(settings, k, None) for k in _EDITABLE}
    # Secrets are shown only as set/not-set — never their values.
    secrets = {
        "WEBHOOK_SECRET": bool(getattr(settings, "WEBHOOK_SECRET", None)),
        "GITHUB_TOKEN": bool(getattr(settings, "GITHUB_TOKEN", None)),
        "OPENROUTER_API_KEY": bool(getattr(settings, "OPENROUTER_API_KEY", None)),
    }
    webhook_url = str(request.base_url).rstrip("/") + "/github/webhook"
    return {"config": cfg, "secrets_set": secrets, "webhook_url": webhook_url}


class ConfigUpdate(BaseModel):
    values: dict[str, Any]


@router.post("/api/config")
def update_config(body: ConfigUpdate):
    applied = {}
    for key, value in body.values.items():
        if key not in _EDITABLE:
            continue
        # Coerce to the current field's type where obvious.
        current = getattr(settings, key, None)
        try:
            if isinstance(current, bool):
                value = str(value).lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                value = int(value)
            setattr(settings, key, value)
            applied[key] = value
        except Exception as exc:  # noqa: BLE001
            logger.warning("Config update rejected for %s: %s", key, exc)
    logger.info("UI updated settings: %s", applied)
    return {"applied": applied}


# --------------------------------------------------------------------------- #
# Repos
# --------------------------------------------------------------------------- #
class RepoIn(BaseModel):
    full_name: str          # owner/repo
    clone_url: str
    branch: str = "main"


@router.get("/api/repos")
def list_repos():
    return {"repos": _load_repos()}


@router.post("/api/repos")
def add_repo(body: RepoIn, request: Request):
    repos = _load_repos()
    name = body.full_name.split("/")[-1]
    entry = {
        "full_name": body.full_name,
        "name": name,
        "clone_url": body.clone_url,
        "branch": body.branch or "main",
    }
    repos = [r for r in repos if r.get("full_name") != body.full_name] + [entry]
    _save_repos(repos)
    webhook_url = str(request.base_url).rstrip("/") + "/github/webhook"
    return {
        "repo": entry,
        "webhook": {
            "url": webhook_url,
            "content_type": "application/json",
            "secret_hint": "Use the same value as your WEBHOOK_SECRET env var",
            "events": "Just the push event",
        },
    }


# --------------------------------------------------------------------------- #
# Manual whole-repo scan
# --------------------------------------------------------------------------- #
class ScanIn(BaseModel):
    full_name: str


def _resolve_head_sha(clone_url: str, branch: str) -> str | None:
    """Resolve the branch HEAD SHA via ``git ls-remote`` (no checkout needed)."""
    try:
        proc = subprocess.run(
            ["git", "ls-remote", clone_url, branch],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        line = (proc.stdout or "").strip().splitlines()
        if line:
            return line[0].split("\t")[0].strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("ls-remote failed for %s: %s", clone_url, exc)
    return None


@router.post("/api/scan")
def manual_scan(body: ScanIn):
    from app.workflows.scan_queue import scan_queue

    repos = _load_repos()
    repo = next((r for r in repos if r.get("full_name") == body.full_name), None)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not registered")
    if scan_queue is None:
        raise HTTPException(status_code=503, detail="Scan queue not ready")

    sha = _resolve_head_sha(repo["clone_url"], repo["branch"]) or ("manual" + "0" * 34)
    event = PushEventSchema(
        ref=f"refs/heads/{repo['branch']}",
        before="0" * 40,
        after=sha,
        repository=RepositorySchema(
            name=repo["name"], full_name=repo["full_name"], clone_url=repo["clone_url"]
        ),
        force_full_scope=True,   # whole-repo scan regardless of SECURITY_SCAN_SCOPE
    )
    setattr(event, "kind", "manual-full")
    outcome = scan_queue.submit(event)
    if outcome == "full":
        raise HTTPException(status_code=503, detail="Scan queue full; try again later")
    return {"status": outcome, "commit": sha, "repository": repo["full_name"], "scope": "full"}


# --------------------------------------------------------------------------- #
# Jobs / status
# --------------------------------------------------------------------------- #
@router.get("/api/jobs")
def list_jobs():
    from app.workflows.scan_queue import scan_queue

    if scan_queue is None:
        return {"queue": {"queued": 0, "active_keys": 0}, "jobs": []}
    return {"queue": scan_queue.stats(), "jobs": scan_queue.recent(20)}
