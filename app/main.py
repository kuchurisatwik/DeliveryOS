from fastapi import FastAPI
from app.github.routes import router as github_router
from app.frontend.routes import router as frontend_router
from app.utils.logger import logger

app = FastAPI(
    title="AI Software Delivery Engineer (AI-SDE)",
    description="AI-powered autonomous software delivery platform.",
    version="0.1.0"
)

# Mount routers
app.include_router(github_router)
app.include_router(frontend_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI-SDE Application")
    # Initialise the in-process scan queue (bounded workers + dedupe) so the
    # webhook enqueues instead of running multi-minute scans inline.
    from app.workflows.scan_queue import init_scan_queue
    from app.github.routes import run_ai_sde_workflow

    init_scan_queue(run_ai_sde_workflow, key_fn=lambda ev: getattr(ev, "after", ""))

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
