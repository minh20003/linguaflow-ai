"""Transactional outbox tests for durable message dispatch intent."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

import tests.conftest as test_fixtures
from src.agents.context_provider import InMemorySourceContextProvider
from src.database.models import Message, OutboxEvent, TranslationResult
from src.services.chat import ChatService
from src.services.language_resolver import LanguageResolution
from src.services.outbox_dispatcher import OutboxDispatcher, dispatch_message_broadcast
from src.services.translation_outbox_worker import TranslationOutboxWorker


@pytest.mark.asyncio
async def test_message_and_two_outbox_intents_commit_atomically(
    test_db, test_user, test_user_two, conversation_factory
):
    conversation = await conversation_factory(test_user, [test_user_two])

    result = await ChatService(test_db).send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="outbox-m1",
        text="Xin chào",
    )

    events = list(
        (
            await test_db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.aggregate_id == result.message.id)
                .order_by(OutboxEvent.event_type)
            )
        ).all()
    )
    assert [event.event_type for event in events] == [
        "message.broadcast_requested",
        "translation.requested",
    ]
    assert all(event.status == "pending" for event in events)
    assert all(event.aggregate_revision == result.message.revision for event in events)
    requested = next(event for event in events if event.event_type == "translation.requested")
    assert set(requested.payload["target_languages"]) == {"en", "vi"}
    assert requested.payload["target_recipient_ids"] == {
        "en": [test_user.id],
        "vi": [test_user_two.id],
    }


@pytest.mark.asyncio
async def test_idempotent_resend_does_not_add_duplicate_outbox_events(
    test_db, test_user, test_user_two, conversation_factory
):
    conversation = await conversation_factory(test_user, [test_user_two])
    service = ChatService(test_db)
    first = await service.send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="outbox-idempotent",
        text="Xin chào",
    )
    second = await service.send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="outbox-idempotent",
        text="Xin chào",
    )

    assert first.created is True
    assert second.created is False
    events = list(
        (
            await test_db.scalars(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == first.message.id)
            )
        ).all()
    )
    assert len(events) == 2


@pytest.mark.asyncio
async def test_crash_before_commit_persists_neither_message_nor_outbox_intent(
    test_db, test_user, test_user_two, conversation_factory
):
    """The message INSERT and both outbox INSERTs are one atomic transaction."""
    assert test_fixtures.test_async_session_maker is not None
    conversation = await conversation_factory(test_user, [test_user_two])

    with patch.object(test_db, "commit", AsyncMock(side_effect=RuntimeError("process crashed"))):
        with pytest.raises(RuntimeError, match="process crashed"):
            await ChatService(test_db).send_message(
                sender_id=test_user.id,
                conversation_id=conversation.id,
                client_message_id="crash-before-commit",
                text="Durable or nothing",
            )
    await test_db.rollback()

    async with test_fixtures.test_async_session_maker() as check_session:
        message_count = await check_session.scalar(
            select(func.count()).select_from(Message).where(
                Message.client_message_id == "crash-before-commit"
            )
        )
        outbox_count = await check_session.scalar(
            select(func.count()).select_from(OutboxEvent)
        )

    assert message_count == 0
    # No message id was committed, therefore no related outbox event can exist.
    assert outbox_count == 0


class _Resolver:
    async def resolve(self, text: str, language_hint: str) -> LanguageResolution:
        return LanguageResolution("vi")


class _Chunk:
    def __init__(self, content: str) -> None:
        self.content = content


class _StreamingGraph:
    async def astream(self, state, *, stream_mode):
        assert stream_mode == ["messages", "values"]
        yield "messages", (_Chunk("Hello"), {"langgraph_node": "translate"})
        yield "values", {
            **state,
            "translated_text": "Hello",
            "is_fallback": False,
            "model": "test-model",
        }


class _SlowStreamingGraph(_StreamingGraph):
    async def astream(self, state, *, stream_mode):
        await asyncio.sleep(1.25)
        async for item in super().astream(state, stream_mode=stream_mode):
            yield item


class _Publisher:
    def __init__(self) -> None:
        self.events: list[tuple[tuple[str, ...], dict]] = []

    async def send_to_users(self, user_ids, event) -> None:
        self.events.append((tuple(user_ids), event))


class _CrashAfterPublishPublisher(_Publisher):
    async def send_to_users(self, user_ids, event) -> None:
        await super().send_to_users(user_ids, event)
        if event["type"] == "message_received":
            raise RuntimeError("process crashed after transport accepted the event")


@pytest.mark.asyncio
async def test_broadcast_retry_preserves_dedup_key_after_publish_then_crash(
    test_db, test_user, test_user_two, conversation_factory
):
    conversation = await conversation_factory(test_user, [test_user_two])
    result = await ChatService(test_db).send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="at-least-once",
        text="Deliver me",
    )
    message_id = result.message.id
    crashed_publisher = _CrashAfterPublishPublisher()
    with pytest.raises(RuntimeError, match="process crashed"):
        await dispatch_message_broadcast(
            test_db, crashed_publisher, message_id
        )

    event = await test_db.scalar(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == message_id,
            OutboxEvent.event_type == "message.broadcast_requested",
        )
    )
    assert event is not None
    assert event.status == "pending"
    event.available_at = datetime.now(UTC) - timedelta(seconds=1)
    await test_db.commit()

    retry_publisher = _Publisher()
    assert await dispatch_message_broadcast(
        test_db, retry_publisher, message_id
    ) is True
    first_delivery = next(
        payload
        for _, payload in crashed_publisher.events
        if payload["type"] == "message_received"
    )
    retry_delivery = next(
        payload
        for _, payload in retry_publisher.events
        if payload["type"] == "message_received"
    )
    assert first_delivery["message"]["id"] == retry_delivery["message"]["id"]


@pytest.mark.asyncio
async def test_runtime_dispatcher_consumes_broadcast_and_translation_intents(
    test_db, test_user, test_user_two, conversation_factory
):
    """The committed outbox is executable, not merely persisted component state."""
    assert test_fixtures.test_async_session_maker is not None
    conversation = await conversation_factory(test_user, [test_user_two])
    result = await ChatService(test_db).send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="runtime-slice",
        text="Xin chao",
    )
    publisher = _Publisher()
    dispatcher = OutboxDispatcher(
        test_fixtures.test_async_session_maker,
        publisher,
        language_resolver=_Resolver(),
        source_context_provider=InMemorySourceContextProvider(),
        graph_factory=_StreamingGraph,
    )

    assert await dispatcher.run_once() is True

    async with test_fixtures.test_async_session_maker() as session:
        statuses = list(
            (
                await session.scalars(
                    select(OutboxEvent.status)
                    .where(OutboxEvent.aggregate_id == result.message.id)
                    .order_by(OutboxEvent.event_type)
                )
            ).all()
        )
        translation = await session.scalar(
            select(TranslationResult).where(
                TranslationResult.message_id == result.message.id,
                TranslationResult.target_language == "en",
            )
        )

    assert statuses == ["processed", "processed"]
    assert translation is not None
    assert translation.translated_content == "Hello"
    assert translation.status == "completed"
    event_types = [event["type"] for _, event in publisher.events]
    assert "message_received" in event_types
    assert "message_created" in event_types
    assert event_types.count("translation.started") == 2
    assert event_types.count("translation.completed") == 2
    original_final = next(
        event
        for recipients, event in publisher.events
        if recipients == (test_user_two.id,)
        and event["type"] == "translation.completed"
    )
    assert original_final["content"] == "Xin chao"
    assert original_final["translation_id"] is None


@pytest.mark.asyncio
async def test_runtime_dispatcher_does_not_translate_an_edited_away_revision(
    test_db, test_user, test_user_two, conversation_factory
):
    assert test_fixtures.test_async_session_maker is not None
    conversation = await conversation_factory(test_user, [test_user_two])
    result = await ChatService(test_db).send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="stale-runtime-slice",
        text="Revision one",
    )
    result.message.original_text = "Revision two"
    result.message.revision += 1
    result.message.source_language = None
    await test_db.commit()

    publisher = _Publisher()
    dispatcher = OutboxDispatcher(
        test_fixtures.test_async_session_maker,
        publisher,
        language_resolver=_Resolver(),
        source_context_provider=InMemorySourceContextProvider(),
        graph_factory=_StreamingGraph,
    )
    assert await dispatcher.run_once() is True

    async with test_fixtures.test_async_session_maker() as session:
        translation_count = await session.scalar(
            select(func.count()).select_from(TranslationResult)
        )
        translation_outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == result.message.id,
                OutboxEvent.event_type == "translation.requested",
            )
        )
    assert translation_count == 0
    assert translation_outbox is not None
    assert translation_outbox.status == "processed"
    assert not any(event["type"].startswith("translation.") for _, event in publisher.events)


@pytest.mark.asyncio
async def test_dispatcher_heartbeats_a_translation_longer_than_its_lease(
    test_db, test_user, test_user_two, conversation_factory
):
    assert test_fixtures.test_async_session_maker is not None
    conversation = await conversation_factory(test_user, [test_user_two])
    await ChatService(test_db).send_message(
        sender_id=test_user.id,
        conversation_id=conversation.id,
        client_message_id="heartbeat-runtime-slice",
        text="Xin chao",
    )
    dispatcher = OutboxDispatcher(
        test_fixtures.test_async_session_maker,
        _Publisher(),
        language_resolver=_Resolver(),
        source_context_provider=InMemorySourceContextProvider(),
        graph_factory=_SlowStreamingGraph,
        lease_seconds=1,
    )
    dispatch_task = asyncio.create_task(dispatcher.run_once())
    await asyncio.sleep(1.05)

    replacement = TranslationOutboxWorker(
        test_fixtures.test_async_session_maker,
        max_concurrency=1,
        batch_size=1,
        lease_seconds=1,
    )
    assert await replacement.claim_available() == []
    assert await dispatch_task is True
