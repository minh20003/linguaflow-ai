"""Tests for the translation fan-out service (PR-6).

No LLM and no compiled graph: `graph_factory` is injected, so every case here
pins the service's own behaviour rather than the agent's. The agent has its own
76 tests.

Fixtures live in this file rather than tests/conftest.py, which is shared across
all feature areas.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from src.database.models import Message, TranslationResult
from src.services.translation import schedule_translations


class RecordingPublisher:
    """Captures what would have gone out over the socket."""

    def __init__(self) -> None:
        self.sent: list[tuple[tuple[str, ...], dict]] = []

    async def send_to_users(self, user_ids, payload) -> None:
        self.sent.append((tuple(user_ids), dict(payload)))

    def events_for(self, target_language: str) -> list[dict]:
        return [p for _, p in self.sent if p.get("target_language") == target_language]


def make_graph_factory(result_by_language: dict[str, dict]):
    """Build a graph_factory whose ainvoke returns a canned state per target."""

    def factory(_session, _message_id):
        class FakeGraph:
            async def ainvoke(self, state, config=None):
                canned = result_by_language.get(state["target_language"], {})
                return {**state, **canned}

        return FakeGraph()

    return factory


def failing_graph_factory(exc: Exception):
    def factory(_session, _message_id):
        class FakeGraph:
            async def ainvoke(self, state, config=None):
                raise exc

        return FakeGraph()

    return factory


def session_factory_for_tests():
    """The session maker conftest points at the current temp database.

    Read late — conftest reassigns it per test.
    """
    import tests.conftest as conftest_module

    return conftest_module.test_async_session_maker


async def persist_message(session, *, conversation_id, sender_id, text, source_language):
    message = Message(
        client_message_id="m1",
        conversation_id=conversation_id,
        sender_id=sender_id,
        original_text=text,
        source_language=source_language,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def run_translations(*, message, publisher, graph_factory):
    """Schedule the work and wait for the background task to settle."""
    schedule_translations(
        message=message,
        publisher=publisher,
        session_factory=session_factory_for_tests(),
        graph_factory=graph_factory,
    )
    # Let the task run to completion; it is deliberately not awaited in production.
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_translates_for_each_recipient_language(
    test_db, test_user, test_user_two, conversation_factory
):
    """test_user reads en, test_user_two reads vi — one translation each way."""
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user.id,
        text="Deploy xong chua anh?",
        source_language="vi",
    )
    publisher = RecordingPublisher()

    await run_translations(
        message=message,
        publisher=publisher,
        graph_factory=make_graph_factory(
            {
                "en": {
                    "source_language": "vi",
                    "translated_text": "Have you finished deploying?",
                    "model": "mock-model",
                    "latency_ms": 900,
                    "is_fallback": False,
                }
            }
        ),
    )

    # vi is the detected source, so the vi reader gets nothing — they have the original.
    assert publisher.events_for("vi") == []
    english = publisher.events_for("en")
    assert len(english) == 1
    assert english[0]["translated_text"] == "Have you finished deploying?"
    assert english[0]["conversation_id"] == conversation.id
    assert english[0]["is_fallback"] is False

    async with session_factory_for_tests()() as session:
        rows = (await session.scalars(select(TranslationResult))).all()
    assert [(r.target_language, r.is_fallback) for r in rows] == [("en", False)]


@pytest.mark.asyncio
async def test_sends_only_to_users_who_read_that_language(
    test_db, test_user, test_user_two, test_user_three, conversation_factory
):
    """en, vi and ja readers in one group; each event goes to its own audience."""
    conversation = await conversation_factory(
        test_user, [test_user, test_user_two, test_user_three], conversation_type="group"
    )
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user_two.id,
        text="Bọn em sẽ bàn giao trước thứ Sáu",
        source_language="vi",
    )
    publisher = RecordingPublisher()

    await run_translations(
        message=message,
        publisher=publisher,
        graph_factory=make_graph_factory(
            {
                "en": {"source_language": "vi", "translated_text": "We will deliver before Friday"},
                "ja": {"source_language": "vi", "translated_text": "金曜日までに納品します"},
            }
        ),
    )

    recipients = {p["target_language"]: users for users, p in publisher.sent}
    assert recipients["en"] == (test_user.id,)
    assert recipients["ja"] == (test_user_three.id,)
    assert "vi" not in recipients


@pytest.mark.asyncio
async def test_writes_back_the_detected_source_language(
    test_db, test_user, test_user_two, conversation_factory
):
    """The stored source_language is provisional until detection overrides it."""
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user_two.id,
        text="The API is ready for testing",
        source_language="vi",  # provisional, and wrong
    )

    await run_translations(
        message=message,
        publisher=RecordingPublisher(),
        graph_factory=make_graph_factory(
            {"vi": {"source_language": "en", "translated_text": "API đã sẵn sàng để kiểm thử"}}
        ),
    )

    async with session_factory_for_tests()() as session:
        stored = await session.get(Message, message.id)
        assert stored.source_language == "en"


@pytest.mark.asyncio
async def test_publishes_nothing_when_the_agent_fails(
    test_db, test_user, test_user_two, conversation_factory
):
    """A failed translation must leave the delivered original untouched."""
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user.id,
        text="Chào bạn nhé",
        source_language="vi",
    )
    publisher = RecordingPublisher()

    await run_translations(
        message=message,
        publisher=publisher,
        graph_factory=failing_graph_factory(RuntimeError("agent exploded")),
    )

    assert publisher.sent == []
    async with session_factory_for_tests()() as session:
        assert (await session.scalars(select(TranslationResult))).all() == []
        assert (await session.get(Message, message.id)).original_text == "Chào bạn nhé"


@pytest.mark.asyncio
async def test_publishes_nothing_when_the_translation_is_empty(
    test_db, test_user, test_user_two, conversation_factory
):
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user.id,
        text="Chào bạn nhé",
        source_language="vi",
    )
    publisher = RecordingPublisher()

    await run_translations(
        message=message,
        publisher=publisher,
        graph_factory=make_graph_factory({"en": {"source_language": "vi", "translated_text": "   "}}),
    )

    assert publisher.sent == []


@pytest.mark.asyncio
async def test_a_publisher_failure_does_not_escape_the_task(
    test_db, test_user, test_user_two, conversation_factory
):
    """The translation is persisted, so an undelivered event is recoverable."""
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user.id,
        text="Chào bạn nhé",
        source_language="vi",
    )

    class BrokenPublisher:
        async def send_to_users(self, user_ids, payload):
            raise ConnectionError("socket registry down")

    await run_translations(
        message=message,
        publisher=BrokenPublisher(),
        graph_factory=make_graph_factory(
            {"en": {"source_language": "vi", "translated_text": "Hello there"}}
        ),
    )

    async with session_factory_for_tests()() as session:
        rows = (await session.scalars(select(TranslationResult))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_rerunning_reuses_the_existing_translation_row(
    test_db, test_user, test_user_two, conversation_factory
):
    """The unique constraint keeps one translation_id per message and language."""
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    message = await persist_message(
        test_db,
        conversation_id=conversation.id,
        sender_id=test_user.id,
        text="Chào bạn nhé",
        source_language="vi",
    )
    publisher = RecordingPublisher()
    graph_factory = make_graph_factory(
        {"en": {"source_language": "vi", "translated_text": "Hello there"}}
    )

    await run_translations(message=message, publisher=publisher, graph_factory=graph_factory)
    await run_translations(message=message, publisher=publisher, graph_factory=graph_factory)

    async with session_factory_for_tests()() as session:
        rows = (await session.scalars(select(TranslationResult))).all()
    assert len(rows) == 1

    ids = {p["translation_id"] for p in publisher.events_for("en")}
    assert len(ids) == 1
