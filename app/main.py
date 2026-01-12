"""
Shopify Price Manager - Main Application
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .dependencies import init_dependencies, close_dependencies
from .routes import auth_router, stores_router, logs_router, sync_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Shopify Price Manager...")
    await init_dependencies()
    logger.info("Application ready")
    yield
    logger.info("Shutting down...")
    await close_dependencies()


# Create app
app = FastAPI(
    title="Shopify Price Manager",
    description="Automatically manage compare_at_price across Shopify stores",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(auth_router)
app.include_router(stores_router)
app.include_router(logs_router)
app.include_router(sync_router)


@app.get("/")
async def root():
    """Redirect root to stores page."""
    return RedirectResponse(url="/stores", status_code=303)


@app.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
