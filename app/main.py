from fastapi import FastAPI
from app.github.routes import router as github_router
from app.utils.logger import logger

app = FastAPI(
    title="AI Software Delivery Engineer (AI-SDE)",
    description="AI-powered autonomous software delivery platform.",
    version="0.1.0"
)

# Mount routers
app.include_router(github_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI-SDE Application")

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
