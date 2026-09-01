"""The relative-time grammar: how much of "chiều thứ Sáu tuần sau" the server resolves itself.

Deliberately small and deliberately literal. Everything here is a *stated*
thing being turned into an instant -- a day the speaker named, a clock they
read out, a part of the day they said. Nothing is inferred, and an expression
this module does not fully understand resolves to `None`, which reaches the
owner as a question rather than as a booking.

That refusal is the whole point of resolving here instead of trusting the
model's datetime. A model asked to normalize "thứ Sáu tuần sau" answers with a
confident ISO timestamp whether or not it counted the weeks correctly, and a
wrong instant looks exactly like a right one. Counting days is arithmetic, so
the server does the arithmetic; the model is left the job it is actually good
at, which is spotting that an appointment was made at all.

No database, no I/O, no settings -- so the detector and the proposal service can
both use it, and so every rule in it is testable as a plain function.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Ordered longest-first. "ngày mai" must be tried before "mai", and "ngày kia"
# before either, or a two-day expression silently becomes a one-day one.
_DAY_OFFSETS: tuple[tuple[str, int], ...] = (
    ("day after tomorrow", 2),
    ("ngày kìa", 3),
    ("ngày kia", 2),
    ("ngày mốt", 2),
    ("ngày mai", 1),
    ("hôm nay", 0),
    ("tomorrow", 1),
    ("today", 0),
    ("mốt", 2),
    ("mai", 1),
    ("nay", 0),
)

_WEEKDAYS: tuple[tuple[str, int], ...] = (
    ("thứ hai", 0), ("thứ 2", 0), ("monday", 0),
    ("thứ ba", 1), ("thứ 3", 1), ("tuesday", 1),
    ("thứ tư", 2), ("thứ 4", 2), ("wednesday", 2),
    ("thứ năm", 3), ("thứ 5", 3), ("thursday", 3),
    ("thứ sáu", 4), ("thứ 6", 4), ("friday", 4),
    ("thứ bảy", 5), ("thứ bẩy", 5), ("thứ 7", 5), ("saturday", 5),
    ("chủ nhật", 6), ("sunday", 6),
)

# "tuần sau" shifts a weekday into the following week; on its own it means the
# same weekday seven days out.
_NEXT_WEEK = re.compile(r"\b(?:tuần sau|tuần tới|next week)\b", re.IGNORECASE)
_THIS_WEEK = re.compile(r"\b(?:tuần này|this week)\b", re.IGNORECASE)

# What a part of the day means when no clock is given, and which hours it pulls
# into the afternoon or evening when one is. These are conventions, not
# guesses: somebody who says "chiều" has excluded the morning.
_PARTS_OF_DAY: dict[str, tuple[int, range]] = {
    # name: (hour to use when no clock was stated, hours that mean PM)
    "sáng": (9, range(0, 0)),
    "morning": (9, range(0, 0)),
    "trưa": (12, range(1, 3)),
    "noon": (12, range(1, 3)),
    "chiều": (14, range(1, 7)),
    "afternoon": (14, range(1, 7)),
    "tối": (19, range(5, 12)),
    "evening": (19, range(5, 12)),
    "đêm": (21, range(9, 12)),
    "night": (21, range(9, 12)),
}
_PART_OF_DAY = re.compile(
    r"\b(?P<part>" + "|".join(sorted(_PARTS_OF_DAY, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# A clock the speaker read out: "6h", "6h30", "6:30", "18 giờ", "6 giờ 30",
# "6 giờ rưỡi", "6pm". The bare-number case ("hẹn lúc 6") is deliberately not
# here -- a lone digit in chat is far more often a quantity than a time.
_CLOCK = re.compile(
    r"\b(?P<hour>\d{1,2})\s*"
    r"(?:"
    r"(?P<sep>:|h|g(?!iờ)|giờ)\s*(?:(?P<minute>[0-5]?\d)\b|(?P<half>rưỡi))?"
    r"|(?=\s*(?P<meridiem_ahead>am|pm)\b)"
    r")",
    re.IGNORECASE,
)
# No leading `\b`: in "3pm" there is no boundary between the digit and the "p",
# so requiring one left the hour at 03:00 and booked the morning. The lookbehind
# still keeps "am" out of the middle of a word such as "program".
_MERIDIEM = re.compile(r"(?<![a-z])(?P<meridiem>am|pm)\b", re.IGNORECASE)


def _find_day(text: str) -> tuple[int | None, int | None, str]:
    """Locate the day the speaker named.

    Returns a plain day offset, a weekday index, and the text with the matched
    words removed. Removal is not tidiness: "thứ 6" would otherwise be read a
    second time as six o'clock, and the appointment would come out at 06:00 on
    a day nobody named.
    """
    for token, weekday in _WEEKDAYS:
        index = text.find(token)
        if index != -1:
            return None, weekday, text[:index] + " " + text[index + len(token):]
    for token, offset in _DAY_OFFSETS:
        match = re.search(rf"\b{re.escape(token)}\b", text)
        if match:
            return offset, None, text[: match.start()] + " " + text[match.end():]
    if _NEXT_WEEK.search(text):
        return 7, None, _NEXT_WEEK.sub(" ", text)
    return None, None, text


def _find_clock(text: str) -> tuple[int, int] | None:
    """Read the hour and minute out of what is left after the day was removed."""
    match = _CLOCK.search(text)
    if match is None:
        return None
    hour = int(match.group("hour"))
    if match.group("half"):
        minute = 30
    else:
        minute = int(match.group("minute") or 0)
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _apply_daylight(hour: int, text: str) -> int | None:
    """Push a stated hour into the afternoon when the speaker said so.

    "6h chiều" is 18:00 and "6h sáng" is 06:00; the number alone says neither.
    An hour that already contradicts the part of day -- "18h sáng" -- is refused
    rather than repaired, because there is no reading of it that is safe to book.
    """
    meridiem = _MERIDIEM.search(text)
    if meridiem:
        if meridiem.group("meridiem").lower() == "pm":
            return hour + 12 if hour < 12 else hour
        return 0 if hour == 12 else hour

    part = _PART_OF_DAY.search(text)
    if part is None:
        return hour
    name = part.group("part").lower()
    _, pm_hours = _PARTS_OF_DAY[name]
    if hour in pm_hours:
        return hour + 12
    if name in ("sáng", "morning") and hour == 12:
        return 0
    if name in ("sáng", "morning") and hour > 12:
        return None
    if name in ("chiều", "afternoon", "tối", "evening") and hour < 12 and hour not in pm_hours:
        # "11h chiều" and the like: the words disagree with the number, and
        # guessing which one the speaker meant is exactly what must not happen.
        return None
    return hour


def _target_date(
    reference_local: datetime,
    day_offset: int | None,
    weekday: int | None,
    text: str,
) -> datetime | None:
    if weekday is not None:
        ahead = (weekday - reference_local.weekday()) % 7
        if _NEXT_WEEK.search(text):
            # The same weekday one full week on from the coming one. "thứ Sáu
            # tuần sau" said on a Thursday means eight days out, not one.
            ahead = ahead + 7 if ahead else 7
        elif _THIS_WEEK.search(text):
            if ahead == 0:
                ahead = 0
        elif ahead == 0:
            # A bare weekday naming today is the coming one, a week out. Chat
            # says "thứ Sáu" about a Friday that has not happened yet.
            ahead = 7
        return reference_local + timedelta(days=ahead)
    if day_offset is not None:
        return reference_local + timedelta(days=day_offset)
    return None


def mentions_relative_time(value: str | None) -> bool:
    """Whether the expression names a day relative to when it was said.

    This is what decides that the model's own datetime must not be trusted, so
    it answers about the *day*, not the clock: "9h" alone is not relative to
    anything, while "thứ Sáu" is meaningless without knowing when it was said.
    """
    if not value:
        return False
    day_offset, weekday, _ = _find_day(value.casefold())
    return day_offset is not None or weekday is not None


def resolve_relative_time(value: str, reference: datetime, timezone: ZoneInfo) -> datetime | None:
    """Turn a stated relative expression into an instant, or refuse.

    `reference` is when the message was sent; it is read on `timezone`'s clock
    first, because "mai" counts from the speaker's date and not from UTC's.

    `None` means the expression was not understood well enough to book, and the
    owner is asked instead. A resolved moment that has already passed is also
    refused -- nobody schedules a meeting into the past, so an expression that
    resolves that way has been misread.
    """
    text = value.casefold()
    local_reference = reference.astimezone(timezone)
    day_offset, weekday, remainder = _find_day(text)

    target = _target_date(local_reference, day_offset, weekday, text)
    if target is None:
        return None

    clock = _find_clock(remainder)
    if clock is None:
        part = _PART_OF_DAY.search(text)
        if part is None:
            # A day with no time at all. Better asked than filled in with an
            # office hour the speaker never said.
            return None
        hour, minute = _PARTS_OF_DAY[part.group("part").lower()][0], 0
    else:
        hour, minute = clock
        adjusted = _apply_daylight(hour, text)
        if adjusted is None:
            return None
        hour = adjusted

    if hour > 23:
        return None
    resolved = datetime.combine(target.date(), time(hour=hour, minute=minute), timezone)
    if resolved <= local_reference:
        return None
    return resolved.astimezone(UTC)
