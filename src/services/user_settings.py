"""Persistence helpers for caller-owned settings.

The UI consumes complete canonical settings objects.  Keeping lazy creation in
one service means every route and background reader applies exactly the same
defaults to accounts created before this feature existed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import UserSettings


async def get_or_create_user_settings(db: AsyncSession, user_id: str) -> UserSettings:
    """Return settings for ``user_id``, atomically tolerating first-use races."""
    settings = await db.get(UserSettings, user_id)
    if settings is not None:
        return settings

    settings = UserSettings(user_id=user_id)
    db.add(settings)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        settings = await db.get(UserSettings, user_id)
        if settings is None:
            raise
        return settings
    await db.refresh(settings)
    return settings


async def update_user_settings(
    db: AsyncSession,
    user_id: str,
    changes: dict[str, object],
) -> UserSettings:
    """Apply explicit fields to the caller's one settings row in one commit."""
    settings = await get_or_create_user_settings(db, user_id)
    for name, value in changes.items():
        setattr(settings, name, value)
    settings.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(settings)
    return settings
