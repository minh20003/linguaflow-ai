"""Read-only view of the translation attempt log (NFR-03).

A separate router rather than another block in `routes.py`, which several
branches edit at once — a new module cannot conflict with them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_admin_user
from src.database import get_db
from src.database.models import TranslationAttempt, User
from src.services.llm_pricing import (
    PRICE_PER_MILLION_TOKENS_USD,
    estimate_cost_usd,
    get_model_price,
)
from src.services.metrics import summarize_attempt_time_series, summarize_attempts

router = APIRouter()

# Clamped so one request cannot ask the database to summarise an unbounded
# history; a year is far more than this project will accumulate.
MAX_WINDOW_DAYS = 365


@router.get("/stats")
async def read_stats(
    days: int | None = Query(
        default=None,
        ge=1,
        le=MAX_WINDOW_DAYS,
        description="Only count attempts from the last N days. Omit for all time.",
    ),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
) -> dict:
    """Summarise how translation has been performing.

    Administrator-only: the response exposes system-wide traffic, which model
    is serving it and how much it costs in tokens. It contains no message text
    or per-user data, but it is operational information rather than member UI.
    """
    since = datetime.now(UTC) - timedelta(days=days) if days else None
    summary = await summarize_attempts(session, since=since)

    return {
        "window_days": days,
        "total_attempts": summary.total,
        "outcomes": summary.outcomes,
        "fallback_rate": round(summary.fallback_rate, 4),
        "detect_methods": summary.detect_methods,
        "fallback_reasons": summary.fallback_reasons,
        "models_served": summary.models_served,
        "language_pairs": {
            pair: {
                "count": stats.count,
                "p50_ms": round(stats.p50_ms),
                "p95_ms": round(stats.p95_ms),
            }
            for pair, stats in summary.language_pairs.items()
        },
        "input_tokens": summary.input_tokens,
        "output_tokens": summary.output_tokens,
        "total_ms_p50": round(summary.total_ms_p50),
        "total_ms_p95": round(summary.total_ms_p95),
    }


@router.get("/stats/attempts")
async def read_recent_attempts(
    days: int | None = Query(default=None, ge=1, le=MAX_WINDOW_DAYS),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
) -> list[dict]:
    """Return recent operational translation attempts without message content."""
    query = select(TranslationAttempt).order_by(desc(TranslationAttempt.created_at)).limit(limit)
    if days:
        since = datetime.now(UTC) - timedelta(days=days)
        query = query.where(TranslationAttempt.created_at >= since)

    attempts = (await session.scalars(query)).all()
    return [
        {
            "id": attempt.id,
            "created_at": attempt.created_at,
            "source_language": attempt.source_language_detected or attempt.source_language_declared,
            "target_language": attempt.target_language,
            "model": attempt.model_served or attempt.model_configured or "(none)",
            "outcome": attempt.outcome,
            "fallback_reason": attempt.fallback_reason,
            "total_ms": attempt.total_ms,
            "input_tokens": attempt.input_tokens,
            "output_tokens": attempt.output_tokens,
        }
        for attempt in attempts
    ]


@router.get("/stats/timeseries")
async def read_attempt_time_series(
    days: int | None = Query(default=None, ge=1, le=MAX_WINDOW_DAYS),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
) -> list[dict[str, int | str]]:
    """Return real attempts in hourly, daily, or all-time monthly buckets."""
    return await summarize_attempt_time_series(session, days=days)
