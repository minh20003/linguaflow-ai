"""Focused B-10 detached-worker and private-event tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services import commitment_detection


@pytest.mark.asyncio
async def test_worker_opens_its_own_session_and_sends_only_to_owner(monkeypatch):
    entered_sessions: list[object] = []
    fresh_session = object()

    class SessionContext:
        async def __aenter__(self):
            entered_sessions.append(fresh_session)
            return fresh_session

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(commitment_detection, "get_async_session_maker", lambda: SessionContext)
    proposal = SimpleNamespace(model_dump=lambda **_kwargs: {"id": "proposal-1"})
    detector = AsyncMock(return_value=[proposal])
    monkeypatch.setattr(
        commitment_detection.ConversationIntelligenceService,
        "detect_self_commitments_from_message",
        detector,
    )
    publisher = MagicMock()
    publisher.send_to_user = AsyncMock()

    await commitment_detection._detect("message-1", "conversation-1", "owner-1", publisher)

    assert entered_sessions == [fresh_session]
    assert detector.await_args.kwargs == {
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "user_id": "owner-1",
        "db": fresh_session,
    }
    publisher.send_to_user.assert_awaited_once_with(
        "owner-1",
        {"type": "action_proposal_created", "proposal": {"id": "proposal-1"}},
    )


@pytest.mark.asyncio
async def test_owner_event_publish_failure_does_not_fail_persisted_detection(monkeypatch):
    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(commitment_detection, "get_async_session_maker", lambda: SessionContext)
    proposal = SimpleNamespace(model_dump=lambda **_kwargs: {"id": "proposal-2"})
    monkeypatch.setattr(
        commitment_detection.ConversationIntelligenceService,
        "detect_self_commitments_from_message",
        AsyncMock(return_value=[proposal]),
    )
    publisher = MagicMock()
    publisher.send_to_user = AsyncMock(side_effect=RuntimeError("offline websocket"))

    await commitment_detection._detect("message-2", "conversation-1", "owner-1", publisher)
    publisher.send_to_user.assert_awaited_once()
