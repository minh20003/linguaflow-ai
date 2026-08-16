"""Adapt LangGraph's in-process message stream to translation domain events."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from src.services.translation_metrics import TranslationMetrics, get_translation_metrics


class TranslationStreamEventSink(Protocol):
    """Transport-independent live translation events."""

    async def translation_started(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        translation_job_id: str,
        recipient_ids: Iterable[str],
    ) -> None:
        """Publish that a translation is now producing provisional content."""
        ...

    async def translation_chunk(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        translation_job_id: str,
        sequence: int,
        content: str,
        recipient_ids: Iterable[str],
    ) -> None:
        """Publish one best-effort provisional token chunk."""
        ...


@dataclass(frozen=True, slots=True)
class TranslationStreamRequest:
    """Metadata required to turn one graph stream into domain events."""

    message_id: str
    message_revision: int
    target_language: str
    translation_job_id: str
    recipient_ids: tuple[str, ...]


class LangGraphTranslationStreamAdapter:
    """Forward only tokens produced by LangGraph's ``translate`` node.

    ``messages`` is the source of token events. ``values`` is requested in the
    same graph invocation solely to recover the graph's final state without a
    second LLM invocation. No replay buffer is retained: chunks are emitted
    once and are intentionally best effort.
    """

    def __init__(
        self,
        event_sink: TranslationStreamEventSink,
        metrics: TranslationMetrics | None = None,
    ) -> None:
        self._event_sink = event_sink
        self._metrics = metrics or get_translation_metrics()

    async def run(
        self,
        graph: Any,
        initial_state: Mapping[str, Any],
        request: TranslationStreamRequest,
    ) -> dict[str, Any]:
        """Run a graph once and emit only provisional translate-node tokens."""
        await self._event_sink.translation_started(
            message_id=request.message_id,
            message_revision=request.message_revision,
            target_language=request.target_language,
            translation_job_id=request.translation_job_id,
            recipient_ids=request.recipient_ids,
        )

        final_state: dict[str, Any] = {}
        sequence = 0
        started_at = perf_counter()
        async for mode, data in self._tagged_stream(graph, initial_state):
            if mode == "values" and isinstance(data, Mapping):
                final_state = dict(data)
                continue

            if mode != "messages":
                continue
            message, metadata = data
            if metadata.get("langgraph_node") != "translate":
                continue
            content = _message_content(message)
            if not content:
                continue
            sequence += 1
            if sequence == 1:
                self._metrics.observe_seconds(
                    "translation_first_token_seconds", perf_counter() - started_at
                )
            await self._event_sink.translation_chunk(
                message_id=request.message_id,
                message_revision=request.message_revision,
                target_language=request.target_language,
                translation_job_id=request.translation_job_id,
                sequence=sequence,
                content=content,
                recipient_ids=request.recipient_ids,
            )

        return final_state

    async def _tagged_stream(
        self,
        graph: Any,
        initial_state: Mapping[str, Any],
    ) -> AsyncIterator[tuple[str, Any]]:
        """Normalize LangGraph's multi-mode stream shape used by this version."""
        stream = graph.astream(initial_state, stream_mode=["messages", "values"])
        async for item in stream:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            mode, data = item
            if mode in {"messages", "values"}:
                yield mode, data


def _message_content(message: Any) -> str:
    """Extract text from an AI message chunk without stripping token spacing."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""
