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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


# What the reminder says, per language. It lands in the person's chat thread
# beside the appointment it is about, and `calendar_events.title` is already
# stored in that person's translation language -- so a Vietnamese sentence
# wrapped around an English title, which is what this was for every account,
# read as two voices. English rather than Vietnamese is the last resort, as
# everywhere else.
_REMINDER_PHRASES: dict[str, tuple[str, str]] = {
    "en": ("Reminder: \"{title}\" starts at {when}.", " Location: {location}."),
    "vi": ("Nhắc bạn: \"{title}\" bắt đầu lúc {when}.", " Địa điểm: {location}."),
    "ja": ("リマインダー：「{title}」は {when} に始まります。", " 場所: {location}。"),
    "ko": ("알림: \"{title}\" 일정이 {when}에 시작합니다.", " 장소: {location}."),
    "zh": ("提醒：“{title}” 将于 {when} 开始。", " 地点：{location}。"),
    "es": ("Recordatorio: \"{title}\" empieza a las {when}.", " Lugar: {location}."),
    "fr": ("Rappel : « {title} » commence à {when}.", " Lieu : {location}."),
    "de": ("Erinnerung: \"{title}\" beginnt um {when}.", " Ort: {location}."),
    "th": ("เตือนความจำ: \"{title}\" เริ่มเวลา {when}", " สถานที่: {location}"),
    "id": ("Pengingat: \"{title}\" dimulai pukul {when}.", " Lokasi: {location}."),
    "pt": ("Lembrete: \"{title}\" começa às {when}.", " Local: {location}."),
    "ru": ("Напоминание: «{title}» начнётся в {when}.", " Место: {location}."),
    "ar": ("تذكير: \"{title}\" يبدأ في {when}.", " المكان: {location}."),
    "hi": ("रिमाइंडर: \"{title}\" {when} बजे शुरू होगा।", " स्थान: {location}।"),
}


def _reminder_zone(event: Any, account_timezone: str | None) -> ZoneInfo:
    """Whose clock the reminder should quote.

    The event's own timezone first: `calendar_events.timezone` holds the one the
    person actually said, which is the answer even after they have travelled.
    Then the account's. UTC only when neither is known, and then the sentence is
    at least honest about being a stored instant rather than quietly two hours
    out.
    """
    for name in (getattr(event, "timezone", None), account_timezone):
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return UTC


def _reminder_text(
    event: Any, language: str | None = None, account_timezone: str | None = None
) -> str:
    """The sentence the assistant says when a reminder falls due.

    Plain text with no Markdown, for the reason the answering prompt gives: the
    chat shows it verbatim.

    `starts_at` is a UTC instant. Formatting it directly told a Hanoi reader
    their 09:00 appointment started at 02:00 -- a number that looks like a
    working reminder and is wrong by the offset, in every one of the fourteen
    sentences below.
    """
    when = event.starts_at.astimezone(_reminder_zone(event, account_timezone)).strftime(
        "%H:%M %d/%m/%Y"
    )
    sentence, place = _REMINDER_PHRASES.get(
        (language or "").lower(), _REMINDER_PHRASES["en"]
    )
    line = sentence.format(title=event.title, when=when)
    if event.location:
        line += place.format(location=event.location)
    return line


async def _post_reminder_message(
    *,
    user_id: str,
    reminder_id: str,
    event: Any,
    publisher: Any,
    factory: Callable[[], Any],
) -> None:
    """Write the due reminder into the person's thread with the assistant.

    Imported inside the function: `chat.py` is a large module that pulls in much
    of the service layer, and importing it at module scope would drag all of it
    into every process that merely starts the scheduler.

    Never raises. A reminder already counts as delivered by the time this runs
    -- the row was claimed before anything was sent -- so a failure here costs
    one message in a thread, and must not take down the scan behind it.
    """
    from sqlalchemy import select

    from src.database.models import User
    from src.schemas.chat import MessageReceivedEvent, RealtimeMessage
    from src.services.chat import ChatService

    try:
        async with factory() as session:
            # The reader's translation language, because this lands in their
            # chat thread beside the appointment, and `event.title` is already
            # stored in it.
            language = await session.scalar(
                select(User.preferred_language).where(User.id == user_id)
            )
            account_timezone = await session.scalar(
                select(User.timezone).where(User.id == user_id)
            )
            posted = await ChatService(session).post_assistant_notice(
                user_id=user_id,
                text=_reminder_text(event, language, account_timezone),
                idempotency_key=f"reminder:{reminder_id}",
            )
            if posted is None:
                return
            realtime = RealtimeMessage.model_validate(posted.message)
            realtime.assistant_generated = True
            payload = MessageReceivedEvent(message=realtime).model_dump(mode="json")
        await publisher.send_to_users((user_id,), payload)
    except Exception:
        logger.warning(
            "Posting the reminder message failed for user %s", user_id, exc_info=True
        )


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

        # And leave it in the person's thread with the assistant. The event
        # above only reaches a socket that happens to be open right now; the
        # message is what they find when they come back, and what tells them
        # afterwards that they were reminded at all.
        await _post_reminder_message(
            user_id=row.user_id,
            reminder_id=row.id,
            event=event,
            publisher=publisher,
            factory=factory,
        )

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
    # The Google Calendar pull, on its own much slower interval. Minutes rather
    # than the reminder loop's seconds because each cycle costs a Google API
    # call per linked account, and a calendar edited on a phone is not urgent to
    # mirror. Registered only when Calendar is actually configured, so a
    # deployment without Google credentials does not run a job that can only
    # fail (ADR-36).
    from src.services.google_calendar import is_configured_for_calendar, sync_all_enabled_links

    if is_configured_for_calendar(effective):
        scheduler.add_job(
            sync_all_enabled_links,
            "interval",
            seconds=effective.calendar_sync_interval_seconds,
            id="calendar_sync",
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Google Calendar sync started, pulling every %ss",
            effective.calendar_sync_interval_seconds,
        )

    scheduler.start()
    logger.info(
        "Reminder scheduler started, scanning every %ss",
        effective.reminder_scan_interval_seconds,
    )
    return scheduler
