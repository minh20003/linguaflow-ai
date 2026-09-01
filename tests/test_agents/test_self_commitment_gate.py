"""Which messages are worth a model call, now that a time counts as a signal."""

from __future__ import annotations

import pytest

from src.agents.conversation_intelligence.self_commitment import _worth_examining


@pytest.mark.parametrize(
    "text",
    [
        # Settled without a single word from the old keyword list. This is the
        # shape that used to be thrown away before anything read it.
        "Ok 6h chiều mai nhé",
        "Vậy trưa thứ 5 lúc 12h nha",
        "Thôi 9h sáng thứ 2 tuần sau đi",
        "Mai 7h30 ở cổng trường nhé",
        # A past reference inside a sentence that settles a future meeting. The
        # old negative list dropped this on the words "hôm qua".
        "Hôm qua mình chưa chốt, mai 6h gặp nhé",
        # Still caught by the words themselves.
        "Tôi sẽ gửi báo cáo trước cuối tuần",
        "Ok chốt nhé, 3h chiều thứ Sáu họp ở phòng A",
        "Let's meet Friday at 3pm",
    ],
)
def test_gate_lets_through_a_message_that_is_arranging_something(text):
    assert _worth_examining(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Chào buổi sáng mọi người!",
        "Cho mình xin 5 phút nhé",
        "Giá là 200k thôi",
        "File nặng 20 mb",
        "",
    ],
)
def test_gate_keeps_ordinary_chat_from_costing_a_model_call(text):
    assert _worth_examining(text) is False


def test_a_number_that_is_not_a_clock_does_not_look_like_an_appointment():
    """A day word plus a quantity is not a time: "5 quyển" is not five o'clock."""
    assert _worth_examining("Mai bạn mang 5 quyển sách nhé") is False
    # The same sentence with a clock in it is worth reading.
    assert _worth_examining("Mai bạn mang sách lúc 5h nhé") is True


def test_a_hedge_still_blocks_a_sentence_that_settles_nothing():
    """"If I have time I'll check it" is a conditional, not a commitment."""
    assert _worth_examining("If I have time I'll check it.") is False
    assert _worth_examining("Maybe we'll meet tomorrow.") is False


def test_a_stated_day_and_clock_outrank_a_hedge_in_the_same_sentence():
    """Naming both is the point at which somebody has stopped speculating."""
    assert _worth_examining("Nếu rảnh thì mai 6h mình gặp ở quán cà phê nhé") is True


def test_a_clock_without_a_day_still_needs_a_word_that_arranges_something():
    """"lúc 9h" alone could be reporting, not arranging; the model isn't called."""
    assert _worth_examining("Nó chạy xong lúc 9h") is False
    assert _worth_examining("Hẹn lúc 9h") is True
