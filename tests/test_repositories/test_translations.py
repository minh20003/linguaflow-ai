"""Concurrency tests for CP-04 translation claiming."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

import tests.conftest as test_fixtures
from src.database.models import TranslationResult
from src.repositories.translations import TranslationRepository


@pytest.mark.asyncio
async def test_concurrent_claims_create_one_logical_translation(test_db):
    """Two dispatchers for one key produce exactly one Agent owner."""
    assert test_fixtures.test_async_session_maker is not None

    async def claim_once():
        async with test_fixtures.test_async_session_maker() as session:
            return await TranslationRepository(session).claim_translation(
                message_id="m1",
                message_revision=1,
                source_language="vi",
                target_language="en",
            )

    first, second = await asyncio.gather(claim_once(), claim_once())

    assert sum(claim.claimed for claim in (first, second)) == 1
    assert first.translation.id == second.translation.id

    count = await test_db.scalar(select(func.count()).select_from(TranslationResult))
    assert count == 1


@pytest.mark.asyncio
async def test_failed_translation_does_not_persist_original_content(test_db):
    """The UI fallback text is not stored as translated_content."""
    repository = TranslationRepository(test_db)
    claim = await repository.claim_translation(
        message_id="m2",
        message_revision=1,
        source_language="vi",
        target_language="en",
    )

    failed = await repository.fail_translation(
        message_id="m2",
        message_revision=1,
        target_language="en",
        content=None,
        expected_job_id=claim.translation.current_job_id,
    )

    assert failed is not None
    assert failed.status == "failed"
    assert failed.fallback_level == "original"
    assert failed.translated_content is None


@pytest.mark.asyncio
async def test_retry_fences_late_completion_from_the_previous_job(test_db):
    """A previous attempt cannot overwrite the active retry's final result."""
    repository = TranslationRepository(test_db)
    first = await repository.claim_translation(
        message_id="m3",
        message_revision=1,
        source_language="vi",
        target_language="en",
    )
    first_job_id = first.translation.current_job_id
    assert first_job_id is not None
    failed = await repository.fail_translation(
        message_id="m3",
        message_revision=1,
        target_language="en",
        expected_job_id=first_job_id,
    )
    assert failed is not None

    retried = await repository.claim_translation(
        message_id="m3",
        message_revision=1,
        source_language="vi",
        target_language="en",
        retry_failed=True,
    )
    second_job_id = retried.translation.current_job_id
    assert retried.claimed is True
    assert second_job_id is not None
    assert second_job_id != first_job_id
    assert retried.translation.attempt_count == 2

    late_old_completion = await repository.finalize_translation(
        message_id="m3",
        message_revision=1,
        target_language="en",
        content="old execution output",
        status="completed",
        fallback_level="none",
        provider="llm",
        model="old-model",
        expected_job_id=first_job_id,
    )
    assert late_old_completion is None

    final = await repository.finalize_translation(
        message_id="m3",
        message_revision=1,
        target_language="en",
        content="new execution output",
        status="completed",
        fallback_level="none",
        provider="llm",
        model="new-model",
        expected_job_id=second_job_id,
    )
    assert final is not None
    assert final.translated_content == "new execution output"


@pytest.mark.asyncio
async def test_reclaimed_outbox_attempt_can_replace_orphaned_active_job(test_db):
    repository = TranslationRepository(test_db)
    abandoned = await repository.claim_translation(
        message_id="m4",
        message_revision=1,
        source_language="vi",
        target_language="en",
    )
    abandoned_job_id = abandoned.translation.current_job_id

    reclaimed = await repository.claim_translation(
        message_id="m4",
        message_revision=1,
        source_language="vi",
        target_language="en",
        retry_active=True,
    )

    assert reclaimed.claimed is True
    assert reclaimed.translation.id == abandoned.translation.id
    assert reclaimed.translation.current_job_id != abandoned_job_id
    assert reclaimed.translation.attempt_count == 2
    assert await repository.finalize_translation(
        message_id="m4",
        message_revision=1,
        target_language="en",
        content="late abandoned output",
        status="completed",
        fallback_level="none",
        provider="llm",
        model="old",
        expected_job_id=abandoned_job_id,
    ) is None
