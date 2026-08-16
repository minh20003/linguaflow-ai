"""Phase 3 orchestration tests: prepare once, run one isolated job per target."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

import tests.conftest as test_fixtures
from src.agents.context_provider import InMemorySourceContextProvider
from src.database.models import Conversation, ConversationMember, Message, TranslationResult, User
from src.services.language_resolver import LanguageResolution
from src.services.translation_metrics import TranslationMetrics
from src.services.translation_orchestrator import TranslationOrchestrator


class CountingResolver:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, text: str, language_hint: str) -> LanguageResolution:
        self.calls += 1
        return LanguageResolution("vi")


class CountingContextProvider(InMemorySourceContextProvider):
    def __init__(self) -> None:
        super().__init__({"c1": ["Tin nhắn gốc trước đó"]})
        self.calls = 0

    async def get_recent_source_messages(self, conversation_id: str, limit: int = 5):
        self.calls += 1
        return await super().get_recent_source_messages(conversation_id, limit)


class FakeGraph:
    async def ainvoke(self, state):
        await asyncio.sleep(0)
        return {
            "translated_text": f"{state['target_language']} translation",
            "is_fallback": False,
            "model": "fake-model",
        }


class ConcurrentGraph:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def ainvoke(self, state):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return {
                "translated_text": f"{state['target_language']} translation",
                "is_fallback": False,
                "model": "fake-model",
            }
        finally:
            self.active -= 1


class EditBeforeFinalizeGraph:
    def __init__(self, edit_message) -> None:
        self._edit_message = edit_message

    async def ainvoke(self, state):
        await self._edit_message()
        return {"translated_text": "Old result", "is_fallback": False, "model": "fake"}


class RecallBeforeFinalizeGraph:
    def __init__(self, recall_message) -> None:
        self._recall_message = recall_message

    async def ainvoke(self, state):
        await self._recall_message()
        return {"translated_text": "Late result", "is_fallback": False, "model": "fake"}


class InvalidStreamThenFallbackGraph:
    """Represents a graph where validation rejects streamed LLM output."""

    async def astream(self, state, *, stream_mode):
        assert stream_mode == ["messages", "values"]
        yield "values", state
        yield "messages", (FakeChunk("I can't help"), {"langgraph_node": "translate"})
        yield "messages", (FakeChunk(" with that."), {"langgraph_node": "translate"})
        # The graph's validation/fallback path replaces the streamed refusal.
        yield "values", {
            **state,
            "translated_text": "Hello everyone",
            "is_fallback": True,
            "model": "google",
        }


class FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class RecordingEventSink:
    def __init__(self) -> None:
        self.events = []

    async def translation_started(self, **event) -> None:
        self.events.append(("started", event))

    async def translation_chunk(self, **event) -> None:
        self.events.append(("chunk", event))

    async def translation_completed(self, translation, recipient_ids, translation_job_id) -> None:
        self.events.append(
            (
                "completed",
                {
                    "content": translation.translated_content,
                    "status": translation.status,
                    "fallback_level": translation.fallback_level,
                    "replace_stream": True,
                    "translation_job_id": translation_job_id,
                    "recipient_ids": tuple(recipient_ids),
                },
            )
        )

    async def translation_failed(self, translation, recipient_ids, original_content, translation_job_id) -> None:
        raise AssertionError("deep-translator fallback should complete successfully")


class TrackingSessionFactory:
    def __init__(self) -> None:
        self.sessions = []

    def __call__(self):
        assert test_fixtures.test_async_session_maker is not None
        session = test_fixtures.test_async_session_maker()
        self.sessions.append(session)
        return session


@pytest.mark.asyncio
async def test_prepare_once_and_fan_out_with_isolated_sessions(test_db):
    """30 EN, 20 JA, 10 KO members produce three targets and isolated jobs."""
    users = [
        User(
            email=f"member-{language}-{index}@example.com",
            password_hash="hash",
            preferred_language=language,
        )
        for language, amount in (("en", 30), ("ja", 20), ("ko", 10))
        for index in range(amount)
    ]
    sender = User(email="sender@example.com", password_hash="hash", preferred_language="vi")
    test_db.add_all([sender, *users])
    await test_db.flush()
    conversation = Conversation(type="group", created_by=sender.id)
    test_db.add(conversation)
    await test_db.flush()
    test_db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=user.id)
            for user in [sender, *users]
        ]
    )
    message = Message(
        client_message_id="m1",
        conversation_id=conversation.id,
        sender_id=sender.id,
        original_text="Xin chào mọi người",
        source_language="vi",
    )
    test_db.add(message)
    await test_db.commit()

    resolver = CountingResolver()
    context_provider = CountingContextProvider()
    context_provider.add_message(conversation.id, "Tin nhắn gốc trước đó")
    sessions = TrackingSessionFactory()
    graph = ConcurrentGraph()
    orchestrator = TranslationOrchestrator(
        sessions,
        resolver,
        context_provider,
        graph_factory=lambda: graph,
        provider_semaphore=asyncio.Semaphore(1),
    )

    prepared = await orchestrator.prepare_message(message.id)

    assert resolver.calls == 1
    assert context_provider.calls == 1
    assert prepared.target_languages == frozenset({"en", "ja", "ko"})

    results = await orchestrator.run_all_targets(prepared)

    assert {result.target_language for result in results} == {"en", "ja", "ko"}
    assert all(result.status == "completed" for result in results)
    assert graph.max_active == 1
    # Snapshot and source update use separate short sessions; every target has
    # its own claim/finalize sessions. References prevent id reuse here.
    assert len(sessions.sessions) == 8
    assert len({id(session) for session in sessions.sessions}) == 8


@pytest.mark.asyncio
async def test_old_revision_is_marked_stale_and_not_completed(test_db):
    """An edit that wins the race fences a late result from the old revision."""
    sender = User(email="race-sender@example.com", password_hash="hash", preferred_language="vi")
    recipient = User(email="race-recipient@example.com", password_hash="hash", preferred_language="en")
    test_db.add_all([sender, recipient])
    await test_db.flush()
    conversation = Conversation(type="direct", created_by=sender.id)
    test_db.add(conversation)
    await test_db.flush()
    test_db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=sender.id),
            ConversationMember(conversation_id=conversation.id, user_id=recipient.id),
        ]
    )
    message = Message(
        client_message_id="race-m1",
        conversation_id=conversation.id,
        sender_id=sender.id,
        original_text="Họp lúc 3 giờ",
        source_language="vi",
    )
    test_db.add(message)
    await test_db.commit()

    sessions = TrackingSessionFactory()

    async def edit_before_finalize() -> None:
        async with sessions() as session:
            current = await session.get(Message, message.id)
            assert current is not None
            current.original_text = "Họp lúc 4 giờ"
            current.revision += 1
            current.source_language = None
            await session.commit()

    orchestrator = TranslationOrchestrator(
        sessions,
        CountingResolver(),
        CountingContextProvider(),
        graph_factory=lambda: EditBeforeFinalizeGraph(edit_before_finalize),
    )
    prepared = await orchestrator.prepare_message(message.id)
    result = await orchestrator.run_target(prepared, "en")

    assert result.status == "stale"
    assert result.translated_content is None


@pytest.mark.asyncio
async def test_recalled_message_fences_late_job_as_stale(test_db):
    """Recall before finalization prevents a terminal translation result."""
    sender = User(email="recall-sender@example.com", password_hash="hash", preferred_language="vi")
    recipient = User(email="recall-recipient@example.com", password_hash="hash", preferred_language="en")
    test_db.add_all([sender, recipient])
    await test_db.flush()
    conversation = Conversation(type="direct", created_by=sender.id)
    test_db.add(conversation)
    await test_db.flush()
    test_db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=sender.id),
            ConversationMember(conversation_id=conversation.id, user_id=recipient.id),
        ]
    )
    message = Message(
        client_message_id="recall-m1",
        conversation_id=conversation.id,
        sender_id=sender.id,
        original_text="Xin chào",
        source_language="vi",
    )
    test_db.add(message)
    await test_db.commit()

    sessions = TrackingSessionFactory()

    async def recall_before_finalize() -> None:
        async with sessions() as session:
            current = await session.get(Message, message.id)
            assert current is not None
            current.deleted_at = datetime.now(UTC)
            current.original_text = ""
            await session.commit()

    orchestrator = TranslationOrchestrator(
        sessions,
        CountingResolver(),
        CountingContextProvider(),
        graph_factory=lambda: RecallBeforeFinalizeGraph(recall_before_finalize),
    )
    prepared = await orchestrator.prepare_message(message.id)
    result = await orchestrator.run_target(prepared, "en")

    assert result.status == "stale"
    assert result.translated_content is None


@pytest.mark.asyncio
async def test_ten_ensure_calls_create_one_logical_latest_revision_target(test_db):
    """A new KO reader can request one idempotent translation ten times."""
    sender = User(email="ensure-sender@example.com", password_hash="hash", preferred_language="vi")
    reader = User(email="ensure-reader@example.com", password_hash="hash", preferred_language="ja")
    test_db.add_all([sender, reader])
    await test_db.flush()
    conversation = Conversation(type="direct", created_by=sender.id)
    test_db.add(conversation)
    await test_db.flush()
    test_db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=sender.id),
            ConversationMember(conversation_id=conversation.id, user_id=reader.id),
        ]
    )
    message = Message(
        client_message_id="ensure-m1",
        conversation_id=conversation.id,
        sender_id=sender.id,
        original_text="Xin chào",
        source_language="vi",
    )
    test_db.add(message)
    await test_db.commit()

    orchestrator = TranslationOrchestrator(
        TrackingSessionFactory(),
        CountingResolver(),
        CountingContextProvider(),
        graph_factory=FakeGraph,
    )
    results = await asyncio.gather(
        *(orchestrator.ensure_translation(message.id, "ko") for _ in range(10))
    )

    assert len({result.id for result in results if result is not None}) == 1
    count = await test_db.scalar(
        select(func.count()).select_from(TranslationResult).where(
            TranslationResult.message_id == message.id,
            TranslationResult.message_revision == 1,
            TranslationResult.target_language == "ko",
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_streamed_invalid_llm_output_is_replaced_by_fallback_completion(test_db):
    """Chunks may be invalid; completed must contain the validated fallback text."""
    sender = User(email="stream-sender@example.com", password_hash="hash", preferred_language="vi")
    recipient = User(email="stream-recipient@example.com", password_hash="hash", preferred_language="en")
    test_db.add_all([sender, recipient])
    await test_db.flush()
    conversation = Conversation(type="direct", created_by=sender.id)
    test_db.add(conversation)
    await test_db.flush()
    test_db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=sender.id),
            ConversationMember(conversation_id=conversation.id, user_id=recipient.id),
        ]
    )
    message = Message(
        client_message_id="stream-m1",
        conversation_id=conversation.id,
        sender_id=sender.id,
        original_text="Xin chào mọi người",
        source_language="vi",
    )
    test_db.add(message)
    await test_db.commit()

    sink = RecordingEventSink()
    metrics = TranslationMetrics()
    orchestrator = TranslationOrchestrator(
        TrackingSessionFactory(),
        CountingResolver(),
        CountingContextProvider(),
        graph_factory=InvalidStreamThenFallbackGraph,
        event_sink=sink,
        recipient_ids_for_target=lambda _prepared, _target: (recipient.id,),
        metrics=metrics,
    )

    prepared = await orchestrator.prepare_message(message.id)
    result = await orchestrator.run_target(prepared, "en")

    assert result.status == "fallback_completed"
    assert [event_type for event_type, _ in sink.events] == [
        "started",
        "chunk",
        "chunk",
        "completed",
    ]
    assert [event["content"] for event_type, event in sink.events if event_type == "chunk"] == [
        "I can't help",
        " with that.",
    ]
    completed = sink.events[-1][1]
    assert completed["content"] == "Hello everyone"
    assert completed["status"] == "fallback_completed"
    assert completed["fallback_level"] == "deep_translator"
    assert completed["replace_stream"] is True
    assert metrics.snapshot()["translation_jobs_total"] == 1
    assert metrics.snapshot()["translation_completed_total"] == 1
    assert metrics.snapshot()["translation_fallback_total"] == 1
    assert metrics.snapshot()["translation_duration_seconds_count"] == 1
