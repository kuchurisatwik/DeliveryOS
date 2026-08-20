"""HTTP surface of the DAST service.

Small on purpose: something finishes a deploy and POSTs a target here; everything
else is read-only reporting.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.utils.logger import logger
from dast import queue as dast_queue_module
from dast import storage
from dast.models import ScanRecord, ScanRequest

router = APIRouter()

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@router.post("/scan", status_code=202)
def submit_scan(request: ScanRequest) -> JSONResponse:
    """Queue a scan of a running target.

    Returns ``202`` when queued, ``409`` when the same target is already being
    scanned (two scanners on one app produce results neither can be trusted), and
    ``503`` when the queue is full.
    """
    if request.profile not in ("fast", "deep"):
        raise HTTPException(400, "profile must be 'fast' or 'deep'")
    if not request.target_url.startswith(("http://", "https://")):
        raise HTTPException(400, "target_url must be an absolute http(s) URL")

    record = ScanRecord(
        scan_id=storage.new_scan_id(),
        target_url=request.target_url.rstrip("/"),
        commit_sha=request.commit_sha,
        profile=request.profile,
        kind=request.kind,
        source_root=request.source_root,
    )

    queue = dast_queue_module.dast_queue
    if queue is None:  # pragma: no cover - only if startup failed
        raise HTTPException(503, "scan queue is not running")

    storage.save(record)
    outcome = queue.submit(record)
    logger.info(
        "Scan request for %s (%s): %s", record.target_url, record.profile, outcome
    )

    if outcome == "duplicate":
        return JSONResponse(
            status_code=409,
            content={"status": "duplicate", "detail": "this target is already being scanned"},
        )
    if outcome == "full":
        return JSONResponse(
            status_code=503,
            content={"status": "full", "detail": "scan queue is at capacity; retry later"},
        )
    return JSONResponse(
        status_code=202, content={"status": "accepted", "scan_id": record.scan_id}
    )


@router.get("/internal/openapi/{scan_id}", include_in_schema=False)
def internal_openapi(scan_id: str) -> FileResponse:
    """Serve the synthesised OpenAPI spec for a scan back to the ZAP sidecar.

    When a target publishes no spec of its own, the service synthesises one from
    the source-extracted endpoint inventory and points ZAP's importer at this URL
    (see :func:`dast.service._assemble_scope`). ZAP fetches the spec here and seeds
    its site tree against the real target via a host override, so the endpoint
    inventory reaches ZAP exactly as it reaches Schemathesis. This is an internal
    seam on the compose network, not a public API.
    """
    from dast.service import synth_spec_path

    path = synth_spec_path(scan_id)
    if not os.path.isfile(path):
        raise HTTPException(404, "no synthesised spec for this scan")
    return FileResponse(path, media_type="application/json")


@router.get("/api/scans")
def list_scans(limit: int = 25) -> dict:
    """Recent scans, newest first — summaries only, no finding payloads."""
    queue = dast_queue_module.dast_queue
    return {
        "queue": queue.stats() if queue else {"queued": 0, "active_keys": 0},
        "scans": [record.summary() for record in storage.list_recent(limit)],
    }


@router.get("/api/scans/{scan_id}")
def get_scan(scan_id: str) -> dict:
    """One scan in full: findings, per-tool coverage, and the preflight result."""
    record = storage.load(scan_id)
    if record is None:
        raise HTTPException(404, "no such scan")
    return {
        **record.summary(),
        "preflight": record.preflight,
        "coverage": record.coverage,
        "baseline": record.baseline,
        "findings": record.findings,
    }


@router.get("/", include_in_schema=False)
def index():
    """The one-page status view."""
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
