"""Render stored content in the language of the screen it is about to appear on.

A proposal's title and a calendar event's title are stored in the owner's
*translation* language, because that is the language of the chat message they
came from and of the card that sits beside it. The task inbox and the personal
calendar are chrome, and their chrome follows the *interface* language, so a
title arriving from the other setting leaves those screens reading in two
languages at once.

Usually the two settings agree, and then this does nothing at all -- no call, no
cost, the stored string straight through. It only works when a person has
deliberately set them apart, which is exactly when the mismatch would show.

Cached in process because the inbox is polled: the same dozen titles are asked
for over and over, and the answer cannot change between requests without the
title itself changing. Bounded, because an unbounded cache keyed by user text is
a slow memory leak.
"""

from __future__ import annotations

from collections import OrderedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.services.fallback_translator import translate_with_secondary_provider

# Enough for a busy inbox several times over; small enough to be invisible.
_MAX_ENTRIES = 2048
_cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()


async def reading_languages(db: AsyncSession, user_id: str) -> tuple[str | None, str | None]:
    """The account's (interface, translation) languages, in one query."""
    row = (
        await db.execute(
            select(User.interface_language, User.preferred_language).where(
                User.id == user_id
            )
        )
    ).first()
    return (row[0], row[1]) if row else (None, None)


async def in_interface_language(
    text: str | None, *, stored_language: str | None, interface_language: str | None
) -> str | None:
    """`text` as the interface should show it, or unchanged.

    Returns the original on any failure. A screen showing the stored wording is
    a smaller problem than a screen showing nothing, and the caller has no
    better string to fall back to.
    """
    if not text or not interface_language or not stored_language:
        return text
    if interface_language == stored_language:
        return text

    key = (text, stored_language, interface_language)
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached

    rendered = (
        await translate_with_secondary_provider(text, interface_language, stored_language)
        or text
    )
    _cache[key] = rendered
    if len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)
    return rendered
