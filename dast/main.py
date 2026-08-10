"""Entrypoint for the standalone DAST service.

Run with ``uvicorn dast.main:app``. This is a **different** application from
``app.main:app`` — different port, different container, different queue. The two
services share code (the finding model, the subprocess helpers) but never share a
process or a worker.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.utils.logger import logger
from dast.config import dast_settings
from dast.routes import router as dast_router

app = FastAPI(
    title="DeliveryOS DAST",
    description="Dynamic application security testing against running deployments.",
    version="0.1.0",
)

app.include_router(dast_router)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info(
        "Starting DeliveryOS DAST (workers=%d, state=%s)",
        dast_settings.DAST_SCAN_WORKERS,
        dast_settings.DAST_STATE_DIR,
    )
    from dast.queue import init_dast_queue
    from dast.service import run_dast_scan

    init_dast_queue(run_dast_scan)


@app.get("/health")
def health_check() -> dict:
    """Liveness probe for the DAST service itself."""
    from dast.queue import dast_queue

    return {
        "status": "ok",
        "service": "dast",
        "queue": dast_queue.stats() if dast_queue else None,
    }
