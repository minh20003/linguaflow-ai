from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services import assistant_mentions


@pytest.mark.asyncio
async def test_explicit_assistant_mention_runs_agent_and_notifies_requester(monkeypatch):
    captured: list[tuple[str, dict]] = []

    @asynccontextmanager
    async def session_context():
        yield object()

    class Agent:
        async def extract_actions_from_message(self, **kwargs):
            assert kwargs["conversation_id"] == "conversation-1"
            assert kwargs["message_id"] == "message-1"
            assert kwargs["user_id"] == "user-1"
            return [SimpleNamespace(model_dump=lambda mode: {"id": "proposal-1"})]

    class Publisher:
        async def send_to_user(self, user_id, event):
            captured.append((user_id, event))

    monkeypatch.setattr(assistant_mentions, "get_async_session_maker", lambda: session_context)
    monkeypatch.setattr(assistant_mentions, "ConversationIntelligenceService", Agent)
    # The session here is a bare sentinel; this test is about the mention
    # plumbing, and permissions have their own tests.
    monkeypatch.setattr(assistant_mentions, "has_consent", AsyncMock(return_value=True))

    await assistant_mentions._process(
        message_id="message-1",
        conversation_id="conversation-1",
        requester_id="user-1",
        publisher=Publisher(),
    )

    assert captured == [
        ("user-1", {"type": "action_proposal_created", "proposal": {"id": "proposal-1"}})
    ]


@pytest.mark.asyncio
async def test_assistant_mention_without_read_consent_publishes_nothing(monkeypatch):
    """Tagging the assistant is an ordinary message until the user permits it."""
    captured: list[tuple[str, dict]] = []

    @asynccontextmanager
    async def session_context():
        yield object()

    class Agent:
        async def extract_actions_from_message(self, **_kwargs):
            raise AssertionError("The agent must not run without consent")

    class Publisher:
        async def send_to_user(self, user_id, event):
            captured.append((user_id, event))

    monkeypatch.setattr(assistant_mentions, "get_async_session_maker", lambda: session_context)
    monkeypatch.setattr(assistant_mentions, "ConversationIntelligenceService", Agent)
    monkeypatch.setattr(assistant_mentions, "has_consent", AsyncMock(return_value=False))

    await assistant_mentions._process(
        message_id="message-1",
        conversation_id="conversation-1",
        requester_id="user-1",
        publisher=Publisher(),
    )

    assert captured == []
