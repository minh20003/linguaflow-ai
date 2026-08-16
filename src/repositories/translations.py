"""Atomic persistence operations for translation jobs (CP-04)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import TranslationResult

_ACTIVE_STATUSES = ("pending", "streaming")
_FINAL_STATUSES = ("completed", "fallback_completed", "failed")


@dataclass(frozen=True)
class TranslationClaim:
    """The durable row and whether this caller owns work for it."""

    translation: TranslationResult
    claimed: bool


class TranslationRepository:
    """Repository that serializes translation creation by its logical key.

    Each mutation commits its own short transaction. A successful claim is
    therefore visible to another dispatcher before the caller starts an Agent.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _insert(self):
        dialect = self._session.bind.dialect.name  # type: ignore[union-attr]
        if dialect == "postgresql":
            return postgresql_insert(TranslationResult)
        if dialect == "sqlite":
            return sqlite_insert(TranslationResult)
        raise RuntimeError(f"claim_translation is unsupported for dialect {dialect!r}")

    async def get_translation(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
    ) -> TranslationResult | None:
        return await self._session.scalar(
            select(TranslationResult).where(
                TranslationResult.message_id == message_id,
                TranslationResult.message_revision == message_revision,
                TranslationResult.target_language == target_language,
            )
        )

    async def claim_translation(
        self,
        *,
        message_id: str,
        message_revision: int,
        source_language: str,
        target_language: str,
        job_id: str | None = None,
        retry_failed: bool = False,
        retry_active: bool = False,
    ) -> TranslationClaim:
        """Create one pending row, or return the row another caller owns.

        The unique key and `ON CONFLICT DO NOTHING` make concurrent first claims
        atomic. Completed and active rows never start another Agent. A failed row
        is retried only when the caller explicitly selects that policy.
        """

        new_job_id = job_id or str(uuid4())
        insert_stmt = (
            self._insert()
            .values(
                message_id=message_id,
                message_revision=message_revision,
                source_language=source_language,
                target_language=target_language,
                current_job_id=new_job_id,
                status="pending",
                fallback_level="none",
                attempt_count=1,
            )
            .on_conflict_do_nothing(
                index_elements=("message_id", "message_revision", "target_language")
            )
            .returning(TranslationResult.id)
        )
        inserted_id = (await self._session.execute(insert_stmt)).scalar_one_or_none()
        await self._session.commit()

        if inserted_id is not None:
            translation = await self._session.get(TranslationResult, inserted_id)
            assert translation is not None
            return TranslationClaim(translation=translation, claimed=True)

        existing = await self.get_translation(
            message_id=message_id,
            message_revision=message_revision,
            target_language=target_language,
        )
        if existing is None:
            raise RuntimeError("translation conflict row was not visible after commit")

        if existing.status == "failed" and retry_failed:
            retry_stmt = (
                update(TranslationResult)
                .where(TranslationResult.id == existing.id, TranslationResult.status == "failed")
                .values(
                    current_job_id=new_job_id,
                    translated_content=None,
                    status="pending",
                    fallback_level="none",
                    provider="",
                    model="",
                    attempt_count=TranslationResult.attempt_count + 1,
                )
                .returning(TranslationResult.id)
            )
            retried_id = (await self._session.execute(retry_stmt)).scalar_one_or_none()
            await self._session.commit()
            if retried_id is not None:
                translation = await self._session.get(TranslationResult, retried_id)
                assert translation is not None
                return TranslationClaim(translation=translation, claimed=True)

        if existing.status in _ACTIVE_STATUSES and retry_active:
            previous_job_id = existing.current_job_id
            retry_stmt = (
                update(TranslationResult)
                .where(
                    TranslationResult.id == existing.id,
                    TranslationResult.status.in_(_ACTIVE_STATUSES),
                    TranslationResult.current_job_id == previous_job_id,
                )
                .values(
                    current_job_id=new_job_id,
                    translated_content=None,
                    status="pending",
                    fallback_level="none",
                    provider="",
                    model="",
                    attempt_count=TranslationResult.attempt_count + 1,
                )
                .returning(TranslationResult.id)
            )
            retried_id = (await self._session.execute(retry_stmt)).scalar_one_or_none()
            await self._session.commit()
            if retried_id is not None:
                translation = await self._session.get(TranslationResult, retried_id)
                assert translation is not None
                return TranslationClaim(translation=translation, claimed=True)

        return TranslationClaim(translation=existing, claimed=False)

    async def finalize_translation(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        content: str | None,
        status: str,
        fallback_level: str,
        provider: str,
        model: str,
        expected_job_id: str | None = None,
    ) -> TranslationResult | None:
        """Persist one authoritative terminal result for an active claim."""
        if status not in _FINAL_STATUSES:
            raise ValueError(f"terminal status required, got {status!r}")

        conditions = [
            TranslationResult.message_id == message_id,
            TranslationResult.message_revision == message_revision,
            TranslationResult.target_language == target_language,
            TranslationResult.status.in_((*_ACTIVE_STATUSES, "stale")),
        ]
        if expected_job_id is not None:
            conditions.append(TranslationResult.current_job_id == expected_job_id)

        result = await self._session.execute(
            update(TranslationResult)
            .where(*conditions)
            .values(
                current_job_id=None,
                translated_content=content,
                status=status,
                fallback_level=fallback_level,
                provider=provider,
                model=model,
            )
            .returning(TranslationResult.id)
        )
        translation_id = result.scalar_one_or_none()
        await self._session.commit()
        return await self._session.get(TranslationResult, translation_id) if translation_id else None

    async def fail_translation(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        content: str | None = None,
        expected_job_id: str | None = None,
    ) -> TranslationResult | None:
        """Mark an active claim failed without overwriting a newer attempt."""
        return await self.finalize_translation(
            message_id=message_id,
            message_revision=message_revision,
            target_language=target_language,
            content=content,
            status="failed",
            fallback_level="original",
            provider="",
            model="",
            expected_job_id=expected_job_id,
        )

    async def mark_translation_stale(
        self,
        *,
        message_id: str,
        message_revision: int,
        target_language: str,
        expected_job_id: str | None = None,
    ) -> TranslationResult | None:
        """Mark only an active claim stale; terminal rows are immutable."""
        conditions = [
            TranslationResult.message_id == message_id,
            TranslationResult.message_revision == message_revision,
            TranslationResult.target_language == target_language,
            TranslationResult.status.in_(_ACTIVE_STATUSES),
        ]
        if expected_job_id is not None:
            conditions.append(TranslationResult.current_job_id == expected_job_id)
        result = await self._session.execute(
            update(TranslationResult)
            .where(*conditions)
            .values(status="stale", current_job_id=None)
            .returning(TranslationResult.id)
        )
        translation_id = result.scalar_one_or_none()
        await self._session.commit()
        return await self._session.get(TranslationResult, translation_id) if translation_id else None
