"""Read-only view of the translation attempt log (NFR-03).

A separate router rather than another block in `routes.py`, which several
branches edit at once — a new module cannot conflict with them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user
from src.database import get_db
from src.database.models import User
from src.services.metrics import summarize_attempts

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
    _current_user: User = Depends(get_current_user),
) -> dict:
    """Summarise how translation has been performing.

    Authenticated rather than public: the response exposes system-wide traffic,
    which model is serving it and how much it costs in tokens. It contains no
    message text and no per-user data, so any signed-in member may read it.
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
