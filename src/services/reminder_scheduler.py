"""Deliver reminders when they come due.

APScheduler is the clock; PostgreSQL is the queue. The job store APScheduler
offers is deliberately unused, and the difference matters. A scheduler holding
the jobs has to be told about every reminder as it is created, has to be told
again when one is cancelled, and knows nothing about the ones that came due
while the process was down. A table holding them needs none of that: the scan
is a single conditional UPDATE, so it is idempotent under a retry, it catches up
on everything it slept through, and a reminder created by any code path at all
is picked up without that path knowing the scheduler exists.

The claim is `UPDATE ... WHERE remind_at <= now() AND delivered_at IS NULL
RETURNING ...`, which is what makes double delivery impossible rather than
unlikely: two overlapping scans cannot both claim the same row, because the
second one's WHERE no longer matches.

This is the second hard reason the deployment must stay single-instance, on top
of `ConnectionManager` keeping sockets in process memory (ADR-18). Two replicas
would each run this loop; the conditional UPDATE stops the same reminder being
*delivered* twice, but only one of them holds the recipient's socket, so the
other would claim reminders it cannot deliver and mark them done (ADR-33).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session_maker
from src.database.models import CalendarEvent, Reminder

logger = logging.getLogger(__name__)

# How often to look. Sixty seconds is the resolution a reminder is worth: a
# person told about a meeting 15 minutes ahead cannot tell whether the message
# arrived at 14:45:00 or 14:45:40, and a tighter loop is a query per second
# against a table that is almost always empty.
DEFAULT_SCAN_SECONDS = 60


async def scan_due_reminders(
    publisher: Any,
    *,
    session_factory: Callable[[], AsyncSession] | None = None,
    now: datetime | None = None,
) -> int:
    """Claim every reminder that has come due and push it to its owner.

    Args:
        publisher: Anything with ``async send_to_user(user_id, event)``. The
            same duck type the translation and proposal workers use, so tests
            substitute a recorder and production passes `ConnectionManager`.
        session_factory: Session source; defaults to the application's.
        now: The moment to treat as current. Injected so a test can place a
            reminder in the past without sleeping.

    Returns:
        How many reminders were claimed. Zero is the ordinary case.

    Never raises. A failure here must not stop the scheduler: the next scan is
    sixty seconds away and the rows it could not claim are still due.
    """
    factory = session_factory or get_async_session_maker()
    moment = now or datetime.now(UTC)

    try:
        async with factory() as session:
            claimed = (
                await session.execute(
                    update(Reminder)
                    .where(
                        Reminder.remind_at <= moment,
                        Reminder.delivered_at.is_(None),
                        Reminder.dismissed_at.is_(None),
                    )
                    .values(delivered_at=moment)
                    .returning(Reminder.id, Reminder.user_id, Reminder.calendar_event_id)
                )
            ).all()
            # Committed before anything is sent. A socket that fails must not
            # roll back the claim and hand the same reminder to the next scan;
            # a missed notification is better than a loop that repeats one every
            # minute forever.
            await session.commit()

            if not claimed:
                return 0

            events = {
                event.id: event
                for event in (
                    await session.scalars(
                        select(CalendarEvent).where(
                            CalendarEvent.id.in_([row.calendar_event_id for row in claimed])
                        )
                    )
                ).all()
            }
    except Exception:
        logger.warning("Reminder scan failed", exc_info=True)
        return 0

    for row in claimed:
        event = events.get(row.calendar_event_id)
        if event is None or event.status != "active":
            # Cancelled between the claim and the send. Already marked
            # delivered, which is right: nothing is owed for it any more.
            continue
        try:
            await publisher.send_to_user(
                row.user_id,
                {
                    "type": "reminder_due",
                    "reminder": {
                        "id": row.id,
                        "calendar_event_id": event.id,
                        "title": event.title,
                        "starts_at": event.starts_at.isoformat(),
                        "location": event.location,
                    },
                },
            )
        except Exception:
            logger.warning("Reminder delivery failed for user %s", row.user_id, exc_info=True)

    return len(claimed)


def start_reminder_scheduler(*, publisher: Any, settings: Any = None) -> Any | None:
    """Start the periodic scan, or don't, and say which by the return value.

    Returns ``None`` when the scheduler is switched off in configuration or
    APScheduler is not installed. Neither is an error: the reminder rows are
    still written and still correct, they simply are not being delivered, which
    is the right behaviour for a test run and for a deployment that has chosen
    to run the scan elsewhere.

    Args:
        publisher: Where due reminders are sent. `ConnectionManager` in
            production.
        settings: Configuration; defaults to the process settings.
    """
    from src.config import get_settings

    effective = settings or get_settings()
    if not effective.reminder_scheduler_enabled:
        logger.info("Reminder scheduler is disabled by configuration")
        return None

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("APScheduler is not installed; reminders will not be delivered")
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scan_due_reminders,
        "interval",
        seconds=effective.reminder_scan_interval_seconds,
        args=[publisher],
        id="reminder_scan",
        # One at a time. A scan that outlives its interval must not have a
        # second copy start beside it, both claiming from the same table.
        max_instances=1,
        # Missing a tick is normal under load; running the skipped ones back to
        # back afterwards would achieve nothing the next scan does not.
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Reminder scheduler started, scanning every %ss",
        effective.reminder_scan_interval_seconds,
    )
    return scheduler
