"""Runtime bridge from durable outbox intents to realtime and translation work."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.agents.context_provider import DatabaseSourceContextProvider, SourceContextProvider
from src.agents.graph import build_translation_graph
from src.agents.nodes.translation import build_default_language_resolver
from src.config import get_settings
from src.database.models import Message, OutboxEvent
from src.schemas.chat import MessageCreatedEvent, MessageReceivedEvent, RealtimeMessage
from src.services.language_resolver import LanguageResolver
from src.services.translation_event_sink import (
    RealtimeEventPublisher,
    WebSocketTranslationEventSink,
)
from src.services.translation_orchestrator import (
    TranslationOrchestrator,
    TranslationPreparationError,
)
from src.services.translation_outbox_worker import TranslationOutboxWorker

logger = logging.getLogger(__name__)


async def _load_message(session: AsyncSession, message_id: str) -> Message | None:
    return await session.scalar(
        select(Message)
        .options(selectinload(Message.attachment))
        .where(Message.id == message_id)
    )


async def get_message_created_event_id(
    session: AsyncSession,
    message_id: str,
) -> str | None:
    """Recover the stable sender-ACK identity for an idempotent resend."""
    outbox_id = await session.scalar(
        select(OutboxEvent.id).where(
            OutboxEvent.event_type == "message.broadcast_requested",
            OutboxEvent.aggregate_id == message_id,
        )
    )
    return f"outbox:{outbox_id}:created" if outbox_id else None


async def dispatch_message_broadcast(
    session: AsyncSession,
    publisher: RealtimeEventPublisher,
    message_id: str,
    *,
    lease_seconds: int = 60,
) -> bool:
    """Claim and publish one message broadcast intent, if it is still pending."""
    now = datetime.now(UTC)
    query = (
        select(OutboxEvent)
        .where(
            OutboxEvent.event_type == "message.broadcast_requested",
            OutboxEvent.aggregate_id == message_id,
            or_(
                OutboxEvent.status == "pending",
                OutboxEvent.status == "processing",
            ),
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(1)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    event = await session.scalar(query)
    if event is None:
        return False
    claimed_event_id = event.id
    event.status = "processing"
    event.attempts += 1
    claimed_attempt = event.attempts
    event.available_at = now + timedelta(seconds=lease_seconds)
    await session.commit()

    try:
        message = await _load_message(session, event.aggregate_id)
        if message is None or message.revision != event.aggregate_revision:
            await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == claimed_event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.attempts == claimed_attempt,
                )
                .values(status="processed", processed_at=datetime.now(UTC))
            )
            await session.commit()
            return True

        payload = event.payload
        recipients = tuple(payload.get("recipient_ids", ()))
        realtime = RealtimeMessage.from_message(message)
        await publisher.send_to_users(
            (user_id for user_id in recipients if user_id != message.sender_id),
            {
                **MessageReceivedEvent(message=realtime).model_dump(mode="json"),
                "event_id": f"outbox:{claimed_event_id}:received",
            },
        )
        finished = await session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == claimed_event_id,
                OutboxEvent.status == "processing",
                OutboxEvent.attempts == claimed_attempt,
            )
            .values(status="processed", processed_at=datetime.now(UTC))
        )
        await session.commit()
        if not finished.rowcount:
            return True
        # ACK is deliberately last. Once the sender observes it, no database
        # work remains that a prompt socket close could cancel halfway through.
        # A lost ACK is recovered by the idempotent resend path.
        await publisher.send_to_users(
            (message.sender_id,),
            MessageCreatedEvent(
                client_message_id=message.client_message_id,
                message=realtime,
            ).model_dump(mode="json")
            | {"event_id": f"outbox:{claimed_event_id}:created"},
        )
        return True
    except Exception:
        await session.rollback()
        await session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == claimed_event_id,
                OutboxEvent.status == "processing",
                OutboxEvent.attempts == claimed_attempt,
            )
            .values(status="pending", available_at=datetime.now(UTC) + timedelta(seconds=1))
        )
        await session.commit()
        raise


class OutboxDispatcher:
    """Poll a bounded durable backlog and execute its application intents."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        publisher: RealtimeEventPublisher,
        *,
        language_resolver: LanguageResolver | None = None,
        source_context_provider: SourceContextProvider | None = None,
        graph_factory: Callable[[], Any] = build_translation_graph,
        poll_interval_seconds: float = 0.25,
        lease_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self._session_factory = session_factory
        self._publisher = publisher
        self._language_resolver = language_resolver or build_default_language_resolver()
        self._source_context_provider = source_context_provider or DatabaseSourceContextProvider(
            session_factory
        )
        self._graph_factory = graph_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._provider_semaphore = asyncio.Semaphore(settings.translation_max_concurrency)
        self._translation_worker = TranslationOutboxWorker(
            session_factory,
            max_concurrency=settings.translation_max_concurrency,
            batch_size=settings.translation_outbox_batch_size,
            lease_seconds=lease_seconds or settings.translation_outbox_lease_seconds,
        )
        self._event_sink = WebSocketTranslationEventSink(publisher)
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start one polling task; repeated calls are harmless."""
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="outbox-dispatcher")

    async def close(self) -> None:
        """Stop polling and wait for the bounded in-flight batch."""
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = await self.run_once()
            except Exception:
                logger.exception("Outbox dispatch cycle failed")
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._poll_interval_seconds
                    )
                except TimeoutError:
                    pass

    async def run_once(self) -> bool:
        """Dispatch one broadcast and one capacity-bounded translation batch."""
        broadcast = await self._next_broadcast_message_id()
        broadcast_worked = False
        if broadcast is not None:
            async with self._session_factory() as session:
                broadcast_worked = await dispatch_message_broadcast(
                    session, self._publisher, broadcast
                )

        translation_events = await self._translation_worker.claim_available()
        if translation_events:
            await asyncio.gather(*(self._process_translation(event) for event in translation_events))
        return broadcast_worked or bool(translation_events)

    async def _next_broadcast_message_id(self) -> str | None:
        async with self._session_factory() as session:
            return await session.scalar(
                select(OutboxEvent.aggregate_id)
                .where(
                    OutboxEvent.event_type == "message.broadcast_requested",
                    or_(
                        OutboxEvent.status == "pending",
                        OutboxEvent.status == "processing",
                    ),
                    OutboxEvent.available_at <= datetime.now(UTC),
                )
                .order_by(OutboxEvent.available_at, OutboxEvent.created_at, OutboxEvent.id)
                .limit(1)
            )

    async def _process_translation(self, event: OutboxEvent) -> None:
        heartbeat_stop = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat_translation(event, heartbeat_stop),
            name=f"translation-heartbeat:{event.id}",
        )
        try:
            recipients_by_language = {
                language: tuple(user_ids)
                for language, user_ids in event.payload.get(
                    "target_recipient_ids", {}
                ).items()
            }
            orchestrator = TranslationOrchestrator(
                self._session_factory,
                self._language_resolver,
                self._source_context_provider,
                graph_factory=self._graph_factory,
                provider_semaphore=self._provider_semaphore,
                event_sink=self._event_sink,
                recipient_ids_for_target=lambda _prepared, target: recipients_by_language.get(
                    target, ()
                ),
            )
            prepared = await orchestrator.prepare_message(event.aggregate_id)
            if prepared.message_revision != event.aggregate_revision:
                # The event belongs to an edited-away revision. A newer intent
                # or lazy ensure owns the current revision; this one must not
                # translate it with an old preferred-language snapshot.
                await self._translation_worker.mark_processed(
                    event.id, expected_attempt=event.attempts
                )
                return
            snapshot_targets = frozenset(event.payload.get("target_languages", ()))
            translated_targets = snapshot_targets - {prepared.source_language}
            prepared = replace(prepared, target_languages=translated_targets)

            source_recipients: Iterable[str] = recipients_by_language.get(
                prepared.source_language, ()
            )
            if source_recipients:
                job_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"translation-outbox:{event.id}:{prepared.source_language}",
                    )
                )
                await self._event_sink.translation_started(
                    message_id=prepared.message_id,
                    message_revision=prepared.message_revision,
                    target_language=prepared.source_language,
                    translation_job_id=job_id,
                    recipient_ids=source_recipients,
                )
                await self._event_sink.original_completed(
                    message_id=prepared.message_id,
                    message_revision=prepared.message_revision,
                    source_language=prepared.source_language,
                    content=prepared.content,
                    translation_job_id=job_id,
                    recipient_ids=source_recipients,
                )
            await orchestrator.run_all_targets(
                prepared,
                reclaim_active=event.attempts > 1,
            )
        except TranslationPreparationError:
            # Missing/recalled/changed messages make this immutable intent
            # permanently obsolete. Retrying cannot make its revision current.
            await self._translation_worker.mark_processed(
                event.id, expected_attempt=event.attempts
            )
        except Exception:
            logger.exception("Translation outbox event %s failed", event.id)
            await self._translation_worker.release_for_retry(
                event.id, expected_attempt=event.attempts
            )
        else:
            await self._translation_worker.mark_processed(
                event.id, expected_attempt=event.attempts
            )
        finally:
            heartbeat_stop.set()
            await heartbeat

    async def _heartbeat_translation(
        self,
        event: OutboxEvent,
        stop: asyncio.Event,
    ) -> None:
        interval = max(0.25, self._translation_worker.lease_seconds / 3)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            try:
                owned = await self._translation_worker.extend_lease(
                    event.id, expected_attempt=event.attempts
                )
            except Exception:
                logger.exception("Could not heartbeat translation outbox event %s", event.id)
                continue
            if not owned:
                logger.warning("Translation outbox lease %s is no longer owned", event.id)
                return
