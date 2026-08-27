"""Detached, race-safe voice transcription and post-transcript handoff.

Audio stops at the Phase 2 transcription service. Once the full transcript is
durable, Phase 4 hands the reloaded canonical ``Message`` to the same shared
post-text scheduler used by ordinary WebSocket messages.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session_maker
from src.database.models import Attachment, ConversationMember, Message
from src.schemas.chat import (
    VoiceTranscriptionCompletedEvent,
    VoiceTranscriptionFailedEvent,
)
from src.services.attachment_storage import (
    AttachmentStorageError,
    AttachmentStorageNotFoundError,
)
from src.services.message_postprocessing import schedule_text_dependent_work
from src.services.transcription import (
    BlankTranscriptError,
    InvalidAudioError,
    TranscriptionConfigurationError,
    TranscriptionError,
    TranscriptionProviderError,
    TranscriptionService,
    TranscriptionTimeoutError,
    get_transcription_service,
)

logger = logging.getLogger(__name__)

_BACKGROUND_TASKS: set[asyncio.Task] = set()


class EventPublisher(Protocol):
    """Transport capability used after a lifecycle state is durable."""

    async def send_to_users(
        self,
        user_ids: Iterable[str],
        event: Mapping[str, Any],
    ) -> None: ...


class PostprocessingScheduler(Protocol):
    """Schedules existing text-dependent work for a persisted message."""

    def __call__(self, *, message: Message, publisher: EventPublisher) -> None: ...


def schedule_voice_transcription(
    *,
    message_id: str,
    conversation_id: str,
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession] | None = None,
    transcription_service_factory: Callable[[], TranscriptionService] | None = None,
    postprocessing_scheduler: PostprocessingScheduler | None = None,
) -> None:
    """Launch STT with primitive IDs and sessions independent of the socket."""
    task = asyncio.create_task(
        transcribe_voice_message(
            message_id=message_id,
            conversation_id=conversation_id,
            publisher=publisher,
            session_factory=session_factory or get_async_session_maker(),
            transcription_service_factory=(transcription_service_factory or get_transcription_service),
            postprocessing_scheduler=postprocessing_scheduler,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    task.add_done_callback(_log_task_failure)


def _log_task_failure(task: asyncio.Task) -> None:
    """Surface an unexpected task escape without logging sensitive payloads."""
    if not task.cancelled() and task.exception() is not None:
        logger.error("Background voice transcription task failed")


async def transcribe_voice_message(
    *,
    message_id: str,
    conversation_id: str,
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession],
    transcription_service_factory: Callable[[], TranscriptionService],
    postprocessing_scheduler: PostprocessingScheduler | None = None,
) -> None:
    """Transcribe one authoritative pending voice message and transition it once."""
    attachment: Attachment | None = None
    async with session_factory() as session:
        message = await session.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
                Message.message_type == "voice",
                Message.transcription_status == "pending",
                Message.deleted_at.is_(None),
            )
        )
        if message is None:
            return
        attachment = await session.scalar(
            select(Attachment).where(
                Attachment.message_id == message_id,
                Attachment.conversation_id == conversation_id,
            )
        )

    if attachment is None:
        await _transition_to_failed(
            message_id=message_id,
            conversation_id=conversation_id,
            retryable=False,
            publisher=publisher,
            session_factory=session_factory,
        )
        return

    try:
        service = transcription_service_factory()
        transcription = await service.transcribe_attachment(attachment)
        transcript = transcription.text.strip()
        if not transcript:
            raise BlankTranscriptError("STT provider returned a blank transcript")
    except (AttachmentStorageError, TranscriptionError) as exc:
        await _transition_to_failed(
            message_id=message_id,
            conversation_id=conversation_id,
            retryable=_failure_is_retryable(exc),
            publisher=publisher,
            session_factory=session_factory,
        )
        return
    except Exception:  # noqa: BLE001 - provider details must never reach logs/events
        logger.error("Voice transcription failed unexpectedly")
        await _transition_to_failed(
            message_id=message_id,
            conversation_id=conversation_id,
            retryable=False,
            publisher=publisher,
            session_factory=session_factory,
        )
        return

    await _transition_to_completed(
        message_id=message_id,
        conversation_id=conversation_id,
        transcript=transcript,
        publisher=publisher,
        session_factory=session_factory,
        postprocessing_scheduler=(postprocessing_scheduler or schedule_text_dependent_work),
    )


def _failure_is_retryable(exc: Exception) -> bool:
    """Return a conservative client retry hint without exposing provider detail."""
    if isinstance(
        exc,
        (
            AttachmentStorageNotFoundError,
            InvalidAudioError,
            BlankTranscriptError,
            TranscriptionConfigurationError,
        ),
    ):
        return False
    return isinstance(
        exc,
        (
            AttachmentStorageError,
            TranscriptionTimeoutError,
            TranscriptionProviderError,
        ),
    )


async def _current_member_ids(
    session: AsyncSession,
    conversation_id: str,
) -> tuple[str, ...]:
    return tuple(
        (
            await session.scalars(
                select(ConversationMember.user_id).where(ConversationMember.conversation_id == conversation_id)
            )
        ).all()
    )


async def _transition_to_completed(
    *,
    message_id: str,
    conversation_id: str,
    transcript: str,
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession],
    postprocessing_scheduler: PostprocessingScheduler,
) -> None:
    """Commit completion, publish it, then schedule existing post-text work."""
    async with session_factory() as session:
        row = (
            await session.execute(
                update(Message)
                .where(
                    Message.id == message_id,
                    Message.conversation_id == conversation_id,
                    Message.message_type == "voice",
                    Message.transcription_status == "pending",
                    Message.deleted_at.is_(None),
                )
                .values(
                    original_text=transcript,
                    transcription_status="completed",
                )
                .returning(Message.source_language)
            )
        ).one_or_none()
        if row is None:
            await session.rollback()
            return
        member_ids = await _current_member_ids(session, conversation_id)
        source_language = row.source_language
        await session.commit()

    await publisher.send_to_users(
        member_ids,
        VoiceTranscriptionCompletedEvent(
            message_id=message_id,
            conversation_id=conversation_id,
            original_text=transcript,
            source_language=source_language,
        ).model_dump(mode="json"),
    )

    # Reload after the completion commit and event. This persisted Message is
    # the sole source passed to translation and every other text-dependent
    # service; the transient STT result is not a parallel content channel.
    async with session_factory() as session:
        completed_message = await session.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
                Message.message_type == "voice",
                Message.transcription_status == "completed",
                Message.original_text != "",
                Message.deleted_at.is_(None),
            )
        )
    if completed_message is None:
        return
    postprocessing_scheduler(message=completed_message, publisher=publisher)


async def _transition_to_failed(
    *,
    message_id: str,
    conversation_id: str,
    retryable: bool,
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession],
) -> None:
    """Atomically claim the pending state, commit, then publish safe failure."""
    async with session_factory() as session:
        transitioned = (
            await session.execute(
                update(Message)
                .where(
                    Message.id == message_id,
                    Message.conversation_id == conversation_id,
                    Message.message_type == "voice",
                    Message.transcription_status == "pending",
                    Message.deleted_at.is_(None),
                )
                .values(original_text="", transcription_status="failed")
                .returning(Message.id)
            )
        ).one_or_none()
        if transitioned is None:
            await session.rollback()
            return
        member_ids = await _current_member_ids(session, conversation_id)
        await session.commit()

    await publisher.send_to_users(
        member_ids,
        VoiceTranscriptionFailedEvent(
            message_id=message_id,
            conversation_id=conversation_id,
            retryable=retryable,
        ).model_dump(mode="json"),
    )
