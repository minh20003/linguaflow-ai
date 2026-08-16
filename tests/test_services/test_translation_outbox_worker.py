"""Tests for bounded durable translation outbox claiming."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

import tests.conftest as test_fixtures
from src.database.models import OutboxEvent
from src.services.translation_metrics import TranslationMetrics
from src.services.translation_outbox_worker import TranslationOutboxWorker


def session_factory():
    assert test_fixtures.test_async_session_maker is not None
    return test_fixtures.test_async_session_maker()


@pytest.mark.asyncio
async def test_claims_only_available_capacity_and_leaves_backlog_in_database(test_db):
    """A worker never materializes more work than its available provider slots."""
    events = [
        OutboxEvent(
            event_type="translation.requested",
            aggregate_id=f"message-{index}",
            aggregate_revision=1,
            payload={"message_id": f"message-{index}"},
        )
        for index in range(5)
    ]
    test_db.add_all(events)
    await test_db.commit()

    metrics = TranslationMetrics()
    worker = TranslationOutboxWorker(
        session_factory,
        max_concurrency=2,
        batch_size=4,
        metrics=metrics,
    )

    claimed = await worker.claim_available()

    assert len(claimed) == 2
    assert worker.active_jobs == 2
    pending_count = await test_db.scalar(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "pending")
    )
    assert pending_count == 3
    assert await worker.claim_available() == []

    await worker.mark_processed(
        claimed[0].id, expected_attempt=claimed[0].attempts
    )
    next_claim = await worker.claim_available()

    assert len(next_claim) == 1
    assert worker.active_jobs == 2
    pending_count = await test_db.scalar(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "pending")
    )
    assert pending_count == 2
    assert metrics.snapshot()["translation_active_jobs"] == 2
    assert metrics.snapshot()["translation_queue_depth"] == 2


@pytest.mark.asyncio
async def test_recovers_expired_processing_event_after_worker_crash(test_db):
    """A replacement worker can reclaim work abandoned by a crashed process."""
    abandoned = OutboxEvent(
        event_type="translation.requested",
        aggregate_id="message-crashed",
        aggregate_revision=1,
        payload={"message_id": "message-crashed"},
        status="processing",
        attempts=1,
        available_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    test_db.add(abandoned)
    await test_db.commit()

    replacement_worker = TranslationOutboxWorker(
        session_factory,
        max_concurrency=1,
        batch_size=1,
        lease_seconds=30,
    )
    claimed = await replacement_worker.claim_available()

    assert [event.id for event in claimed] == [abandoned.id]
    assert claimed[0].attempts == 2
    assert claimed[0].status == "processing"


@pytest.mark.asyncio
async def test_old_attempt_cannot_finish_a_reclaimed_lease(test_db):
    event = OutboxEvent(
        event_type="translation.requested",
        aggregate_id="message-fenced",
        aggregate_revision=1,
        payload={"message_id": "message-fenced"},
    )
    test_db.add(event)
    await test_db.commit()

    old_worker = TranslationOutboxWorker(session_factory, max_concurrency=1, batch_size=1)
    old_claim = (await old_worker.claim_available())[0]
    old_attempt = old_claim.attempts
    async with session_factory() as session:
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event.id)
            .values(available_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    new_worker = TranslationOutboxWorker(session_factory, max_concurrency=1, batch_size=1)
    new_claim = (await new_worker.claim_available())[0]
    assert new_claim.attempts == old_attempt + 1

    assert await old_worker.mark_processed(
        event.id, expected_attempt=old_attempt
    ) is False
    assert old_worker.active_jobs == 0
    async with session_factory() as session:
        current = await session.get(OutboxEvent, event.id)
        assert current is not None
        assert current.status == "processing"
        assert current.attempts == new_claim.attempts

    assert await new_worker.mark_processed(
        event.id, expected_attempt=new_claim.attempts
    ) is True


@pytest.mark.asyncio
async def test_heartbeat_prevents_live_job_lease_reclaim(test_db):
    event = OutboxEvent(
        event_type="translation.requested",
        aggregate_id="message-heartbeat",
        aggregate_revision=1,
        payload={"message_id": "message-heartbeat"},
    )
    test_db.add(event)
    await test_db.commit()
    owner = TranslationOutboxWorker(
        session_factory,
        max_concurrency=1,
        batch_size=1,
        lease_seconds=1,
    )
    claim = (await owner.claim_available())[0]
    await asyncio.sleep(0.7)
    assert await owner.extend_lease(
        event.id, expected_attempt=claim.attempts
    ) is True
    await asyncio.sleep(0.5)

    replacement = TranslationOutboxWorker(
        session_factory,
        max_concurrency=1,
        batch_size=1,
        lease_seconds=1,
    )
    assert await replacement.claim_available() == []
    await owner.mark_processed(event.id, expected_attempt=claim.attempts)


@pytest.mark.asyncio
async def test_load_claim_keeps_300_target_jobs_durable_and_bounded(test_db):
    """100 messages x 3 targets never expands into 300 active asyncio jobs."""
    # Each row represents one logical target job after an outbox request's
    # language snapshot has been expanded by the dispatcher.
    target_jobs = [
        OutboxEvent(
            event_type="translation.requested",
            aggregate_id=f"message-{message_index}",
            aggregate_revision=1,
            payload={"target_language": target_language},
        )
        for message_index in range(100)
        for target_language in ("en", "ja", "ko")
    ]
    test_db.add_all(target_jobs)
    await test_db.commit()

    worker = TranslationOutboxWorker(
        session_factory,
        max_concurrency=3,
        batch_size=100,
        lease_seconds=30,
    )
    claimed = await worker.claim_available()

    assert len(target_jobs) == 300
    assert len(claimed) == 3
    assert worker.active_jobs <= 3
    active_llm_calls = 0
    max_active_llm_calls = 0
    provider_semaphore = asyncio.Semaphore(3)

    async def run_claimed_target() -> None:
        nonlocal active_llm_calls, max_active_llm_calls
        async with provider_semaphore:
            active_llm_calls += 1
            max_active_llm_calls = max(max_active_llm_calls, active_llm_calls)
            try:
                await asyncio.sleep(0)
            finally:
                active_llm_calls -= 1

    # Only the bounded claim is materialized into tasks; the other 297 jobs
    # never enter asyncio until a future worker poll finds free capacity.
    await asyncio.gather(*(run_claimed_target() for _ in claimed))
    assert max_active_llm_calls <= 3
    pending_count = await test_db.scalar(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "pending")
    )
    assert pending_count == 297
