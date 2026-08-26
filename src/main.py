"""FastAPI application entry point.

Wires the CORS middleware, the REST router and the WebSocket router — both under
`/api/v1` — and exposes `/health` for deployment probes. The translation agent is
reached through the chat flow, not from here; see `src/agents/graph.py`.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.observability import verify_tracing_credentials
from src.api.admin import router as admin_router
from src.api.metrics import router as metrics_router
from src.api.routes import router
from src.api.websocket import router as websocket_router
from src.config import configure_logging, get_settings
from src.database import get_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    configure_logging(settings)
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)

    # Blocking, so it runs once here rather than on any request path.
    verify_tracing_credentials()

    # The schema is not created here. Alembic owns it (ADR-06), and the
    # container runs `alembic upgrade head` before this process starts, so an
    # application that also created tables would let the two disagree in silence
    # — `create_all` adds missing tables but never alters an existing one.
    yield

    logger.info("Shutting down")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

_SENSITIVE_FIELD_NAMES = frozenset({
    "password",
    "new_password",
    "otp",
    "token",
    "access_token",
    "refresh_token",
    "jwt_secret",
    "secret",
})


def _sanitize_sensitive_data(val: Any) -> Any:
    """Recursively redact values of sensitive keys at arbitrary depth."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_FIELD_NAMES:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(val, (list, tuple)):
        return [_sanitize_sensitive_data(item) for item in val]
    return val


def _redact_validation_errors(errors: list[dict]) -> list[dict]:
    """Redact raw values of sensitive fields and nested sensitive keys from validation error details."""
    cleaned = []
    for err in errors:
        item = dict(err)
        loc = item.get("loc", ())
        is_loc_sensitive = any(
            isinstance(k, str) and k.lower() in _SENSITIVE_FIELD_NAMES for k in loc
        )
        if is_loc_sensitive and "input" in item:
            item["input"] = "[REDACTED]"
        elif "input" in item:
            item["input"] = _sanitize_sensitive_data(item["input"])
        cleaned.append(item)
    return cleaned


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 422 with redacted sensitive fields to prevent secret echoing."""
    encoded_errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": _redact_validation_errors(encoded_errors)},
    )

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")


def _base_health_payload() -> dict[str, Any]:
    """Return stable service metadata shared by all deployment probes."""
    return {
        "status": "ok",
        "service": "LinguaFlow API",
        "version": app.version,
        "env": settings.app_env,
    }


@app.get("/health/live")
async def liveness() -> dict[str, Any]:
    """Prove that the API process is running without calling dependencies."""
    return {**_base_health_payload(), "checks": {"api": "ok"}}


async def _readiness_response(db: AsyncSession) -> dict[str, Any] | JSONResponse:
    """Confirm the API can serve requests that depend on PostgreSQL."""
    payload = _base_health_payload()
    try:
        # A deployment probe must fail within a bounded time, while still
        # allowing a cold managed-PostgreSQL TLS/pooler handshake to complete.
        async with asyncio.timeout(settings.database_readiness_timeout_seconds):
            await db.execute(select(1))
    except Exception as exc:
        await db.rollback()
        logger.error("Database readiness check failed (%s): %s", type(exc).__name__, exc)
        payload.update({
            "status": "unavailable",
            "checks": {"api": "ok", "database": "unavailable"},
        })
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    payload["checks"] = {"api": "ok", "database": "ok"}
    return payload


@app.get("/health", response_model=None)
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, Any] | JSONResponse:
    """Production readiness probe retained at Render's existing path."""
    return await _readiness_response(db)


@app.get("/health/ready", response_model=None)
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, Any] | JSONResponse:
    """Explicit readiness alias for infrastructure that separates probes."""
    return await _readiness_response(db)
