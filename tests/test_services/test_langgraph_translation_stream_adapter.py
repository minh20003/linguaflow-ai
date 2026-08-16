"""LangGraph message-stream adapter tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.services.langgraph_translation_stream_adapter import (
    LangGraphTranslationStreamAdapter,
    TranslationStreamRequest,
)
from src.services.translation_metrics import TranslationMetrics


@dataclass
class MessageChunk:
    content: str


class StreamingGraph:
    async def astream(self, state, *, stream_mode):
        assert stream_mode == ["messages", "values"]
        yield "values", {**state, "translated_text": ""}
        yield "messages", (MessageChunk("detect token"), {"langgraph_node": "detect_language"})
        yield "messages", (MessageChunk("Hello"), {"langgraph_node": "translate"})
        yield "messages", (MessageChunk(" world"), {"langgraph_node": "translate"})
        yield "messages", (MessageChunk("fallback"), {"langgraph_node": "fallback_translate"})
        yield "values", {**state, "translated_text": "Hello world", "is_valid": True}


class RecordingSink:
    def __init__(self) -> None:
        self.started = []
        self.chunks = []

    async def translation_started(self, **event) -> None:
        self.started.append(event)

    async def translation_chunk(self, **event) -> None:
        self.chunks.append(event)


@pytest.mark.asyncio
async def test_forwards_only_translate_node_tokens_in_order():
    sink = RecordingSink()
    metrics = TranslationMetrics()
    adapter = LangGraphTranslationStreamAdapter(sink, metrics)

    result = await adapter.run(
        StreamingGraph(),
        {"original_text": "Xin chào"},
        TranslationStreamRequest(
            message_id="m1",
            message_revision=2,
            target_language="en",
            translation_job_id="job-1",
            recipient_ids=("u1", "u2"),
        ),
    )

    assert sink.started == [
        {
            "message_id": "m1",
            "message_revision": 2,
            "target_language": "en",
            "translation_job_id": "job-1",
            "recipient_ids": ("u1", "u2"),
        }
    ]
    assert [(chunk["sequence"], chunk["content"]) for chunk in sink.chunks] == [
        (1, "Hello"),
        (2, " world"),
    ]
    assert result["translated_text"] == "Hello world"
    assert metrics.snapshot()["translation_first_token_seconds_count"] == 1
