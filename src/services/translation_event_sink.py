"""Application-level terminal translation events, independent of Agent code."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from src.database.models import TranslationResult


class RealtimeEventPublisher(Protocol):
    """Minimal transport capability required by the WebSocket event sink."""

    async def send_to_users(self, user_ids: Iterable[str], event: dict[str, Any]) -> None:
        """Fan out an already-authorized event to recipient connections."""
        ...


class TranslationEventSink(Protocol):
    """Live and terminal translation events emitted by the application layer."""

    async def translation_started(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        translation_job_id: str,
        recipient_ids: Iterable[str],
    ) -> None:
        """Publish the start of a provisional live stream."""
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
        """Publish one non-durable provisional token chunk."""
        ...

    async def translation_completed(
        self,
        translation: TranslationResult,
        recipient_ids: Iterable[str],
        translation_job_id: str,
    ) -> None:
        """Publish an authoritative successful/fallback translation."""
        ...

    async def translation_failed(
        self,
        translation: TranslationResult,
        recipient_ids: Iterable[str],
        original_content: str,
        translation_job_id: str,
    ) -> None:
        """Publish a terminal failure; original content is UI-only."""
        ...

    async def original_completed(
        self,
        *,
        message_id: str,
        message_revision: int,
        source_language: str,
        content: str,
        translation_job_id: str,
        recipient_ids: Iterable[str],
    ) -> None:
        """Publish source-equals-target as authoritative original content."""
        ...


class WebSocketTranslationEventSink:
    """Serialize terminal domain events through an injected realtime publisher.

    This class deliberately does not import `websocket.py`, `ConnectionManager`,
    Redis, or any Agent module. Application wiring supplies the publisher.
    """

    def __init__(self, publisher: RealtimeEventPublisher) -> None:
        self._publisher = publisher

    async def translation_started(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        translation_job_id: str,
        recipient_ids: Iterable[str],
    ) -> None:
        await self._publisher.send_to_users(
            recipient_ids,
            {
                "type": "translation.started",
                "event_id": f"translation:{translation_job_id}:started",
                "message_id": message_id,
                "message_revision": message_revision,
                "target_language": target_language,
                "translation_job_id": translation_job_id,
            },
        )

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
        await self._publisher.send_to_users(
            recipient_ids,
            {
                "type": "translation.chunk",
                "event_id": f"translation:{translation_job_id}:chunk:{sequence}",
                "message_id": message_id,
                "message_revision": message_revision,
                "target_language": target_language,
                "translation_job_id": translation_job_id,
                "sequence": sequence,
                "delta": content,
            },
        )

    async def translation_completed(
        self,
        translation: TranslationResult,
        recipient_ids: Iterable[str],
        translation_job_id: str,
    ) -> None:
        await self._publisher.send_to_users(
            recipient_ids,
            {
                "type": "translation.completed",
                "event_id": f"translation:{translation_job_id}:completed",
                "message_id": translation.message_id,
                "message_revision": translation.message_revision,
                "target_language": translation.target_language,
                "translation_id": translation.id,
                "translation_job_id": translation_job_id,
                "source_language": translation.source_language,
                "content": translation.translated_content,
                "status": translation.status,
                "fallback_level": translation.fallback_level,
                "replace_stream": True,
                "provider": translation.provider or "",
                "model": translation.model or "",
            },
        )

    async def translation_failed(
        self,
        translation: TranslationResult,
        recipient_ids: Iterable[str],
        original_content: str,
        translation_job_id: str,
    ) -> None:
        await self._publisher.send_to_users(
            recipient_ids,
            {
                "type": "translation.completed",
                "event_id": f"translation:{translation_job_id}:completed",
                "message_id": translation.message_id,
                "message_revision": translation.message_revision,
                "target_language": translation.target_language,
                "translation_id": translation.id,
                "translation_job_id": translation_job_id,
                "source_language": translation.source_language,
                "content": original_content,
                "status": "failed",
                "fallback_level": "original",
                "replace_stream": True,
            },
        )

    async def original_completed(
        self,
        *,
        message_id: str,
        message_revision: int,
        source_language: str,
        content: str,
        translation_job_id: str,
        recipient_ids: Iterable[str],
    ) -> None:
        """Emit a final original without pretending a translation row exists."""
        await self._publisher.send_to_users(
            recipient_ids,
            {
                "type": "translation.completed",
                "event_id": f"translation:{translation_job_id}:completed",
                "message_id": message_id,
                "message_revision": message_revision,
                "target_language": source_language,
                "translation_id": None,
                "translation_job_id": translation_job_id,
                "source_language": source_language,
                "content": content,
                "status": "completed",
                "fallback_level": "none",
                "replace_stream": True,
                "provider": "original",
                "model": "",
            },
        )
