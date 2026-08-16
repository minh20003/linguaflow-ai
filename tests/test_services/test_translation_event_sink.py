"""Terminal event sink tests for the non-streaming vertical slice."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.database.models import TranslationResult
from src.services.translation_event_sink import WebSocketTranslationEventSink


@dataclass
class FakePublisher:
    deliveries: list[tuple[list[str], dict]] = field(default_factory=list)

    async def send_to_users(self, user_ids, event):
        self.deliveries.append((list(user_ids), event))


@pytest.mark.asyncio
async def test_live_events_include_job_sequence_and_pending_status():
    publisher = FakePublisher()
    sink = WebSocketTranslationEventSink(publisher)

    await sink.translation_started(
        message_id="m1",
        message_revision=1,
        target_language="en",
        translation_job_id="job-1",
        recipient_ids=["user-1"],
    )
    await sink.translation_chunk(
        message_id="m1",
        message_revision=1,
        target_language="en",
        translation_job_id="job-1",
        sequence=2,
        content="Hello",
        recipient_ids=["user-1"],
    )

    assert publisher.deliveries == [
        (
            ["user-1"],
            {
                "type": "translation.started",
                "event_id": "translation:job-1:started",
                "message_id": "m1",
                "message_revision": 1,
                "target_language": "en",
                "translation_job_id": "job-1",
            },
        ),
        (
            ["user-1"],
            {
                "type": "translation.chunk",
                "event_id": "translation:job-1:chunk:2",
                "message_id": "m1",
                "message_revision": 1,
                "target_language": "en",
                "translation_job_id": "job-1",
                "sequence": 2,
                "delta": "Hello",
            },
        ),
    ]


@pytest.mark.asyncio
async def test_failed_event_renders_original_without_persisting_it():
    publisher = FakePublisher()
    sink = WebSocketTranslationEventSink(publisher)
    translation = TranslationResult(
        id="t1",
        message_id="m1",
        message_revision=1,
        source_language="vi",
        target_language="en",
        status="failed",
        fallback_level="original",
        translated_content=None,
    )

    await sink.translation_failed(translation, ["user-1"], "Xin chào", "job-1")

    recipients, event = publisher.deliveries[0]
    assert recipients == ["user-1"]
    assert event["type"] == "translation.completed"
    assert event["content"] == "Xin chào"
    assert translation.translated_content is None


@pytest.mark.asyncio
async def test_completed_event_uses_full_final_content_and_job_id():
    publisher = FakePublisher()
    sink = WebSocketTranslationEventSink(publisher)
    translation = TranslationResult(
        id="t1",
        message_id="m1",
        message_revision=2,
        source_language="vi",
        target_language="en",
        status="completed",
        fallback_level="none",
        translated_content="Hello everyone",
    )

    await sink.translation_completed(translation, ["user-1"], "job-1")

    assert publisher.deliveries[0][1] == {
        "type": "translation.completed",
        "event_id": "translation:job-1:completed",
        "message_id": "m1",
        "message_revision": 2,
        "target_language": "en",
        "translation_id": "t1",
        "translation_job_id": "job-1",
        "source_language": "vi",
        "content": "Hello everyone",
        "status": "completed",
        "fallback_level": "none",
        "replace_stream": True,
        "provider": "",
        "model": "",
    }
