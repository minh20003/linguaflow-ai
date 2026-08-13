"""FastAPI application entry point.

Wires the CORS middleware, the REST router and the WebSocket router — both under
`/api/v1` — and exposes `/health` for deployment probes. The translation agent is
reached through the chat flow, not from here; see `src/agents/graph.py`.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.observability import verify_langfuse_credentials
from src.api.metrics import router as metrics_router
from src.api.routes import router
from src.api.websocket import router as websocket_router
from src.config import configure_logging, get_settings
from src.database import create_tables

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    configure_logging(settings)
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)

    # Blocking, so it runs once here rather than on any request path.
    verify_langfuse_credentials()

    # create_all adds missing tables but never alters existing ones — a schema
    # change needs the database recreated (see ADR-06, `make reset-db`).
    await create_tables()
    logger.info("Database tables ready")

    yield

    logger.info("Shutting down")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return application health and environment status."""
    return {"status": "ok", "env": settings.app_env}
