"""What the relative-time grammar accepts, and what it refuses to guess at."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.services.relative_time import mentions_relative_time, resolve_relative_time

HANOI = ZoneInfo("Asia/Ho_Chi_Minh")
# Monday 31 August 2026, 09:00 in Hanoi. A Monday so "thứ 2" can be tested as
# both today and next week, and mid-morning so an earlier hour today is past.
MONDAY_9AM = datetime(2026, 8, 31, 9, 0, tzinfo=HANOI)


def resolved(raw: str, reference: datetime = MONDAY_9AM) -> str | None:
    """The instant the grammar produces, read back on the speaker's own clock."""
    instant = resolve_relative_time(raw, reference, HANOI)
    return None if instant is None else f"{instant.astimezone(HANOI):%d/%m %H:%M}"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Day words.
        ("mai 6h", "01/09 06:00"),
        ("ngày mai 18h30", "01/09 18:30"),
        ("ngày kia 9h", "02/09 09:00"),
        ("mốt 14h", "02/09 14:00"),
        ("ngày mốt 8h sáng", "02/09 08:00"),
        ("hôm nay 8h tối", "31/08 20:00"),
        ("tối nay 8h", "31/08 20:00"),
        ("tomorrow 9am", "01/09 09:00"),
        ("day after tomorrow 10h", "02/09 10:00"),
        # Weekdays, and the week they belong to.
        ("thứ 6 3h chiều", "04/09 15:00"),
        ("thứ sáu tuần sau 15h", "11/09 15:00"),
        ("thứ 5 tuần này 8h", "03/09 08:00"),
        ("chủ nhật 10h", "06/09 10:00"),
        ("friday 3pm", "04/09 15:00"),
        ("next week 8pm", "07/09 20:00"),
        # Clock shapes people actually type.
        ("mai 6 giờ rưỡi", "01/09 06:30"),
        ("mai 6g30", "01/09 06:30"),
        ("mai 6:30", "01/09 06:30"),
        ("mai 18 giờ", "01/09 18:00"),
        # A part of the day carries its own conventional hour.
        ("sáng mai", "01/09 09:00"),
        ("trưa mai", "01/09 12:00"),
        ("chiều mai", "01/09 14:00"),
        ("tối mai", "01/09 19:00"),
        ("đêm mai", "01/09 21:00"),
        # ... and moves a stated hour into the afternoon.
        ("mai 6h chiều", "01/09 18:00"),
        ("mai 6h sáng", "01/09 06:00"),
        ("6h tối mai", "01/09 18:00"),
        ("mai 1h trưa", "01/09 13:00"),
    ],
)
def test_grammar_resolves_the_day_and_clock_the_speaker_actually_named(raw, expected):
    assert resolved(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        # A day with no time at all: better asked than filled in with an office
        # hour nobody said.
        "mai",
        "thứ 6",
        "tuần sau",
        # Words and numbers that contradict each other. There is no reading of
        # these that is safe to book.
        "18h sáng mai",
        "11h chiều mai",
        # Nothing relative in them; an absolute date is somebody else's job.
        "cuối tháng",
        "lúc nào đó",
        "25/12 9h",
        "",
    ],
)
def test_grammar_refuses_rather_than_guesses(raw):
    assert resolved(raw) is None


def test_grammar_refuses_a_time_that_has_already_passed_when_it_was_said():
    """Nobody schedules a meeting into the past, so this reading is wrong."""
    assert resolved("hôm nay 8h sáng") is None
    assert resolved("hôm nay 11h sáng") == "31/08 11:00"


def test_a_bare_weekday_naming_today_means_the_one_a_week_out():
    """Said on a Monday, "thứ 2 9h" is next Monday -- this one is half over."""
    assert resolved("thứ 2 9h") == "07/09 09:00"


def test_weekday_digits_are_not_read_a_second_time_as_an_hour():
    """"thứ 6" is Friday. Reading the 6 again would book 06:00 on a wrong day."""
    assert resolved("thứ 6 lúc 15h") == "04/09 15:00"


def test_a_clock_alone_is_not_relative_so_the_model_keeps_its_own_datetime():
    # `mentions_relative_time` gates whether the model's datetime is refused.
    # "9h" is not relative to anything; "thứ Sáu" is meaningless without a date.
    assert mentions_relative_time("9h") is False
    assert mentions_relative_time("thứ sáu") is True
    assert mentions_relative_time("mai 9h") is True
    assert mentions_relative_time(None) is False


def test_the_day_is_counted_on_the_speakers_date_not_on_the_utc_one():
    """01:00 in Hanoi is still the previous day in UTC; "mai" must not slip."""
    just_after_midnight = datetime(2026, 9, 1, 1, 0, tzinfo=HANOI)

    assert just_after_midnight.astimezone(ZoneInfo("UTC")).day == 31
    assert resolved("mai 6h", just_after_midnight) == "02/09 06:00"
