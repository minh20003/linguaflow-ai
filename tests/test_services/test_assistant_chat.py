"""Behavioural contract tests for replies created by an ``@assistant`` mention.

These tests intentionally use a scripted LLM.  They make the data passed to a
provider inspectable and deterministic in CI, while the live end-to-end check
continues to exercise the configured model separately.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services import chat as chat_module
from src.services.chat import ChatService


class _RecentMessagesDb:
    def __init__(self, messages: list[SimpleNamespace]) -> None:
        self._messages = messages

    async def scalars(self, _statement):
        return SimpleNamespace(all=lambda: self._messages)


def _message(text: str, *, assistant_generated: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        original_text=text,
        assistant_generated=assistant_generated,
        conversation_id="conversation-1",
        sender_id="user-1",
        deleted_at=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "history", "user_request", "model_answer"),
    [
        (
            "summarizes a deadline and its owner",
            ["Linh sẽ hoàn thiện bản thảo song ngữ trước sáng thứ Hai."],
            "@assistant Tóm tắt việc cần làm và thời hạn.",
            "Linh cần hoàn thiện bản thảo song ngữ trước sáng thứ Hai.",
        ),
        (
            "resolves a pronoun using recent context",
            ["Minh gửi hợp đồng cho Lan.", "Cô ấy sẽ phản hồi vào chiều nay."],
            "@assistant Ai sẽ phản hồi và khi nào?",
            "Lan sẽ phản hồi vào chiều nay.",
        ),
        (
            "preserves an English request and answer",
            ["The customer requested the revised proposal by Friday."],
            "@assistant What is the customer's deadline?",
            "The revised proposal is due by Friday.",
        ),
        (
            "keeps an explicit constraint",
            ["Chỉ gửi bản thảo mới cho Linh, chưa gửi khách hàng."],
            "@assistant Bản thảo mới được gửi cho ai?",
            "Chỉ gửi cho Linh; chưa gửi khách hàng.",
        ),
        (
            "answers after an earlier assistant turn",
            [
                "Cuộc họp chuyển sang 9 giờ sáng mai.",
                "Mình đã tóm tắt: cuộc họp diễn ra lúc 9 giờ sáng mai.",
            ],
            "@assistant Cuộc họp diễn ra lúc mấy giờ?",
            "Cuộc họp diễn ra lúc 9 giờ sáng mai.",
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_assistant_reply_supplies_relevant_context_and_returns_model_answer(
    monkeypatch, case, history, user_request, model_answer
):
    messages = [_message(text, assistant_generated=index == len(history) - 1 and "Mình" in text)
                for index, text in enumerate(history)]
    trigger = _message(user_request)
    llm = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=model_answer)))
    monkeypatch.setattr(chat_module, "get_llm", lambda: llm)

    result = await chat_module.ChatService(_RecentMessagesDb(messages))._assistant_reply_text(trigger)

    assert result == model_answer, case
    prompt = llm.ainvoke.await_args.args[0]
    assert user_request.removeprefix("@assistant ") in prompt[1].content
    for message in history:
        assert message in prompt[1].content
    assert "không tin cậy" in prompt[0].content
    assert "Không nhắc lại tag @assistant" in prompt[0].content


@pytest.mark.asyncio
async def test_assistant_reply_strips_tag_case_insensitively(monkeypatch):
    llm = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="Đã hiểu.")))
    monkeypatch.setattr(chat_module, "get_llm", lambda: llm)
    trigger = _message("  @ASSISTANT   Hãy hỗ trợ tôi  ")

    result = await chat_module.ChatService(_RecentMessagesDb([trigger]))._assistant_reply_text(trigger)

    assert result == "Đã hiểu."
    assert "Yêu cầu cần trả lời:\nHãy hỗ trợ tôi" in llm.ainvoke.await_args.args[0][1].content


@pytest.mark.asyncio
async def test_assistant_reply_without_request_does_not_call_model(monkeypatch):
    llm = SimpleNamespace(ainvoke=AsyncMock())
    monkeypatch.setattr(chat_module, "get_llm", lambda: llm)

    result = await chat_module.ChatService(_RecentMessagesDb([]))._assistant_reply_text(
        _message("@assistant")
    )

    assert result == "Bạn muốn mình hỗ trợ điều gì trong cuộc trò chuyện này?"
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_assistant_reply_uses_safe_fallback_when_provider_fails(monkeypatch):
    llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=RuntimeError("provider unavailable")))
    monkeypatch.setattr(chat_module, "get_llm", lambda: llm)

    result = await chat_module.ChatService(_RecentMessagesDb([]))._assistant_reply_text(
        _message("@assistant Tóm tắt giúp tôi")
    )

    assert result.startswith("Mình chưa thể tạo câu trả lời đầy đủ")


@pytest.mark.asyncio
async def test_assistant_reply_is_private_while_request_remains_public(
    conversation_factory,
    monkeypatch,
    test_db,
    test_user,
    test_user_two,
):
    """The request is shared; only the assistant's generated reply is private."""
    conversation = await conversation_factory(test_user, [test_user_two])
    service = ChatService(test_db)
    result = await service.send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="private-assistant-1",
        text="@assistant Tóm tắt cuộc trao đổi này",
        mentions=[{"type": "assistant"}],
    )

    assert result.recipient_ids == (test_user_two.id,)
    assert result.message.visible_to_user_id is None
    assert [message.id for message in await service.get_message_history(
        user_id=test_user.id, conversation_id=conversation.id
    )] == [result.message.id]
    assert [message.id for message in await service.get_message_history(
        user_id=test_user_two.id, conversation_id=conversation.id
    )] == [result.message.id]

    monkeypatch.setattr(
        service,
        "_assistant_reply_text",
        AsyncMock(return_value="Tóm tắt riêng tư."),
    )
    reply = await service.create_assistant_reply(trigger_message=result.message)

    assert reply.recipient_ids == (test_user.id,)
    assert reply.message.visible_to_user_id == test_user.id
    assert reply.message.assistant_generated is True
    assert len(await service.get_message_history(
        user_id=test_user.id, conversation_id=conversation.id
    )) == 2
    assert [message.id for message in await service.get_message_history(
        user_id=test_user_two.id, conversation_id=conversation.id
    )] == [result.message.id]
