"""Render stored content in the language of the screen it is about to appear on.

A proposal's title and a calendar event's title are stored in the owner's
*translation* language, because that is the language of the chat message they
came from and of the card that sits beside it. The task inbox and the personal
calendar are chrome, and their chrome follows the *interface* language, so a
title arriving from the other setting leaves those screens reading in two
languages at once.

Two rules this module exists to keep, both learned the hard way:

* **The stored value is never replaced, only accompanied.** An earlier version
  rewrote `title` in the response. The client sends `title` back when the owner
  approves a proposal or drags a task, so approving without touching the field
  persisted the machine translation over what the person had actually said, and
  every later edit compounded it. The rendered string goes in `display_title`,
  which nothing writes back.
* **A request does not wait on an unbounded number of translations.** The
  provider is an unofficial endpoint with a five-second timeout, and the
  calendar page asks for every event it has. Serialised, a full calendar was
  minutes of hung request on a single-instance deployment (ADR-18). Rows are
  translated concurrently and capped; past the cap the stored value stands,
  which is the same graceful degradation a failed call already gets.

Usually the two settings agree, and then none of this runs at all.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Sequence

# Above this many rows in one response, the rest keep their stored wording. A
# person scrolling a year of calendar is not reading the four-hundredth entry,
# and the alternative is four hundred sequential HTTP calls inside a request.
MAX_ROWS = 60
# How many at once. Enough to make a screenful quick, small enough not to look
# like a burst to a provider that throttles.
CONCURRENCY = 8

_MAX_ENTRIES = 2048
_cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()


def _cached(key: tuple[str, str, str]) -> str | None:
    value = _cache.get(key)
    if value is not None:
        _cache.move_to_end(key)
    return value


def _remember(key: tuple[str, str, str], value: str) -> None:
    _cache[key] = value
    if len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)


async def render(
    text: str | None, *, stored_language: str | None, interface_language: str | None
) -> str | None:
    """`text` as the interface should show it, or `None` when it needs no change.

    `None` rather than the original, so a caller can tell "no rendering needed"
    from "here is a rendering" and leave `display_title` unset in the first case.
    """
    if not text or not interface_language or not stored_language:
        return None
    if interface_language == stored_language:
        return None

    key = (text, stored_language, interface_language)
    hit = _cached(key)
    if hit is not None:
        return hit if hit != text else None

    from src.services.fallback_translator import translate_with_secondary_provider

    rendered = (
        await translate_with_secondary_provider(text, interface_language, stored_language)
        or text
    )
    _remember(key, rendered)
    return rendered if rendered != text else None


async def render_many(
    texts: Sequence[str | None],
    *,
    stored_language: str | None,
    interface_language: str | None,
) -> list[str | None]:
    """Render a response's worth of strings, concurrently and bounded.

    Never raises: `render` already swallows provider failure, and anything it
    still lets through becomes `None`, which the caller reads as "show what is
    stored".
    """
    if not interface_language or interface_language == stored_language:
        return [None] * len(texts)

    limit = asyncio.Semaphore(CONCURRENCY)

    async def one(text: str | None, index: int) -> str | None:
        if index >= MAX_ROWS:
            return None
        async with limit:
            return await render(
                text,
                stored_language=stored_language,
                interface_language=interface_language,
            )

    results = await asyncio.gather(
        *(one(text, index) for index, text in enumerate(texts)),
        return_exceptions=True,
    )
    return [None if isinstance(item, BaseException) else item for item in results]
