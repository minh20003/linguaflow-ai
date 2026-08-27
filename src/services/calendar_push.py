"""Push one calendar entry to Google as soon as it changes.

The periodic cycle (ADR-36) would carry the change anyway, but up to five
minutes later. That gap is fine for a change made *in* Google — nobody is
watching this app for it — and wrong for a change made *here*: the user just
pressed save, and a calendar on their phone that still shows the old time makes
them press save again.

So this is a latency improvement layered on the periodic sync, not a
replacement for it, and the division of labour matters if either is ever
changed. This runs once and gives up on failure. The periodic cycle is what
retries — it picks up anything still `local_only` or `pending_push`, so a push
that fails here is late rather than lost.

Detached like every other background job in this codebase: it takes primitive
ids, opens its own session, and swallows everything. A calendar entry the user
successfully created must not be reported as failed because Google was
unreachable.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session_maker
from src.database.models import CalendarEvent, CalendarLink

logger = logging.getLogger(__name__)

# Strong references, for the reason `schedule_translations` documents: asyncio
# holds only a weak one and will collect a task nobody awaits, mid-statement.
_TASKS: set[asyncio.Task[Any]] = set()


def schedule_calendar_push(
    *,
    event_id: str,
    user_id: str,
    session_factory: Callable[[], AsyncSession] | None = None,
) -> None:
    """Fire and forget a push of one entry to Google.

    Returns immediately. The entry is already saved and already answered to the
    caller; nothing here may hold that up or fail it.

    Args:
        event_id: Entry to push.
        user_id: Its owner, whose link and consent are checked inside.
        session_factory: Session source; defaults to the application's.
    """
    if not event_id or not user_id:
        return

    task = asyncio.create_task(
        _push(
            event_id=event_id,
            user_id=user_id,
            session_factory=session_factory or get_async_session_maker(),
        )
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


async def _push(
    *,
    event_id: str,
    user_id: str,
    session_factory: Callable[[], AsyncSession],
) -> None:
    """Send one entry to Google, if everything needed is in place."""
    from src.services.agent_consent import has_consent
    from src.services.google_calendar import (
        GoogleCalendarError,
        is_configured_for_calendar,
        push_event,
    )

    if not is_configured_for_calendar():
        return

    try:
        async with session_factory() as session:
            # `calendar_write` is a separate permission from `calendar_read` on
            # purpose: reading somebody's calendar into this app and writing
            # into their real one are different asks, and a user may reasonably
            # allow the first without the second.
            if not await has_consent(session, user_id, "calendar_write"):
                return

            link = await session.get(CalendarLink, user_id)
            if link is None or not link.sync_enabled:
                return

            event = await session.get(CalendarEvent, event_id)
            if event is None or event.user_id != user_id:
                return
            if event.source == "google" or event.sync_state == "remote_only":
                # Came from Google. Pushing it back is the echo the etag check
                # exists to prevent, arriving by a different route.
                return

            try:
                await push_event(session, link, event)
            except GoogleCalendarError:
                # Left for the periodic cycle to retry. Marking it explicitly
                # rather than relying on the state it already had, because a
                # previously `synced` entry that failed to update would
                # otherwise look up to date.
                logger.warning("Immediate calendar push failed for %s", event_id, exc_info=True)
                event.sync_state = "pending_push"
                await session.commit()
    except Exception:
        logger.warning("Calendar push task failed for %s", event_id, exc_info=True)
