"""What clock the detector shows the model (`_local_reference`)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from src.agents.conversation_intelligence.self_commitment import _local_reference

HANOI = ZoneInfo("Asia/Ho_Chi_Minh")


def test_reference_time_carries_the_senders_date_not_the_utc_one():
    # 01:00 on 1 September in Hanoi is still 31 August in UTC. A model told only
    # the UTC instant resolves "mai" to 1 September -- the sender's today.
    sent_at = datetime(2026, 9, 1, 1, 0, tzinfo=HANOI).astimezone(UTC)
    assert sent_at.strftime("%d") == "31"

    described = _local_reference(sent_at, "Asia/Ho_Chi_Minh")

    assert described.startswith("2026-09-01T01:00:00+07:00")
    assert "Asia/Ho_Chi_Minh" in described


def test_reference_time_falls_back_to_utc_and_says_the_timezone_is_unknown():
    sent_at = datetime(2026, 9, 1, 1, 0, tzinfo=UTC)

    described = _local_reference(sent_at, None)

    assert described.startswith("2026-09-01T01:00:00+00:00")
    assert "unknown" in described


def test_reference_time_treats_an_unrecognised_timezone_name_as_unknown():
    """A name no zone database knows must not be echoed back as if it resolved."""
    sent_at = datetime(2026, 9, 1, 1, 0, tzinfo=UTC)

    described = _local_reference(sent_at, "Mars/Olympus_Mons")

    assert "unknown" in described
    assert "Mars" not in described
