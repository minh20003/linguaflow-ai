"""Bounded durable backlog processing for translation outbox events."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database.models import OutboxEvent
from src.services.translation_metrics import TranslationMetrics, get_translation_metrics


class TranslationOutboxWorker:
    """Claim only work that can enter the configured provider capacity.

    Rows not claimed remain `pending` in the database. The worker therefore has
    no unbounded in-memory task queue.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        *,
        max_concurrency: int | None = None,
        batch_size: int | None = None,
        lease_seconds: int | None = None,
        metrics: TranslationMetrics | None = None,
    ) -> None:
        settings = get_settings()
        self._session_factory = session_factory
        self._max_concurrency = max_concurrency or settings.translation_max_concurrency
        self._batch_size = batch_size or settings.translation_outbox_batch_size
        self._lease_seconds = lease_seconds or settings.translation_outbox_lease_seconds
        self._metrics = metrics or get_translation_metrics()
        self._active_jobs = 0
        self._active_lock = asyncio.Lock()

    @property
    def active_jobs(self) -> int:
        return self._active_jobs

    @property
    def lease_seconds(self) -> int:
        return self._lease_seconds

    async def claim_available(self) -> list[OutboxEvent]:
        """Atomically mark at most available capacity rows as processing."""
        async with self._active_lock:
            available_slots = max(0, self._max_concurrency - self._active_jobs)
            claim_limit = min(available_slots, self._batch_size)
            if claim_limit == 0:
                return []

            async with self._session_factory() as session:
                now = datetime.now(UTC)
                query = (
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.event_type == "translation.requested",
                        or_(
                            OutboxEvent.status == "pending",
                            OutboxEvent.status == "processing",
                        ),
                        OutboxEvent.available_at <= now,
                    )
                    .order_by(OutboxEvent.available_at, OutboxEvent.created_at, OutboxEvent.id)
                    .limit(claim_limit)
                )
                if session.bind is not None and session.bind.dialect.name == "postgresql":
                    query = query.with_for_update(skip_locked=True)
                events = list((await session.scalars(query)).all())
                for event in events:
                    if event.attempts:
                        self._metrics.increment("outbox_retry_total")
                    event.status = "processing"
                    event.attempts += 1
                    event.available_at = now + timedelta(seconds=self._lease_seconds)
                await session.commit()
                self._active_jobs += len(events)
                self._metrics.set_gauge("translation_active_jobs", self._active_jobs)
                pending_count = await session.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(OutboxEvent.status == "pending")
                )
                self._metrics.set_gauge("translation_queue_depth", pending_count or 0)
                self._metrics.set_gauge("outbox_pending_total", pending_count or 0)
                return events

    async def mark_processed(self, event_id: str, *, expected_attempt: int) -> bool:
        """Mark a claimed event durable-complete and free one worker slot."""
        return await self._finish(event_id, "processed", expected_attempt)

    async def mark_failed(self, event_id: str, *, expected_attempt: int) -> bool:
        """Mark a claimed event failed and free one worker slot."""
        return await self._finish(event_id, "failed", expected_attempt)

    async def release_for_retry(
        self,
        event_id: str,
        *,
        expected_attempt: int,
        delay_seconds: int = 1,
    ) -> bool:
        """Return a failed delivery to the durable backlog after a short delay."""
        async with self._session_factory() as session:
            result = await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.attempts == expected_attempt,
                )
                .values(
                    status="pending",
                    available_at=datetime.now(UTC) + timedelta(seconds=delay_seconds),
                    processed_at=None,
                )
            )
            await session.commit()
        await self._release_local_slot()
        return bool(result.rowcount)

    async def extend_lease(self, event_id: str, *, expected_attempt: int) -> bool:
        """Heartbeat one owned lease without allowing an old attempt to revive it."""
        async with self._session_factory() as session:
            result = await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.attempts == expected_attempt,
                )
                .values(
                    available_at=datetime.now(UTC)
                    + timedelta(seconds=self._lease_seconds)
                )
            )
            await session.commit()
        return bool(result.rowcount)

    async def _finish(self, event_id: str, status: str, expected_attempt: int) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.attempts == expected_attempt,
                )
                .values(status=status, processed_at=datetime.now(UTC))
            )
            await session.commit()
        await self._release_local_slot()
        return bool(result.rowcount)

    async def _release_local_slot(self) -> None:
        """Free this process's slot even if a newer lease fenced its DB write."""
        async with self._active_lock:
            self._active_jobs = max(0, self._active_jobs - 1)
            self._metrics.set_gauge("translation_active_jobs", self._active_jobs)
