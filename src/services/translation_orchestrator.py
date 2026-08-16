"""Prepare one message once, then run isolated translations per target."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.context_provider import DEFAULT_CONTEXT_SIZE, SourceContextProvider
from src.agents.graph import build_translation_graph
from src.config import get_settings
from src.database.models import ConversationMember, Message, TranslationResult, User
from src.repositories.translations import TranslationRepository
from src.services.langgraph_translation_stream_adapter import (
    LangGraphTranslationStreamAdapter,
    TranslationStreamRequest,
)
from src.services.language_resolver import LanguageResolver
from src.services.translation_event_sink import TranslationEventSink
from src.services.translation_metrics import TranslationMetrics, get_translation_metrics


class TranslationPreparationError(Exception):
    """Raised when a message cannot safely be prepared for translation."""


@dataclass(frozen=True, slots=True)
class PreparedTranslation:
    """Transport-free, session-free input shared by every target execution."""

    message_id: str
    message_revision: int
    conversation_id: str
    sender_id: str
    content: str
    source_language: str
    source_context: list[str]
    target_languages: frozenset[str]


class TranslationOrchestrator:
    """Coordinates prepare-once and claim/run/finalize-per-target work."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        language_resolver: LanguageResolver,
        source_context_provider: SourceContextProvider,
        *,
        context_size: int = DEFAULT_CONTEXT_SIZE,
        graph_factory: Callable[[], Any] = build_translation_graph,
        provider_semaphore: asyncio.Semaphore | None = None,
        event_sink: TranslationEventSink | None = None,
        recipient_ids_for_target: Callable[[PreparedTranslation, str], Iterable[str]] | None = None,
        stream_adapter: LangGraphTranslationStreamAdapter | None = None,
        metrics: TranslationMetrics | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._language_resolver = language_resolver
        self._source_context_provider = source_context_provider
        self._context_size = context_size
        self._graph_factory = graph_factory
        self._provider_semaphore = provider_semaphore or asyncio.Semaphore(
            get_settings().translation_max_concurrency
        )
        self._event_sink = event_sink
        self._recipient_ids_for_target = recipient_ids_for_target
        self._metrics = metrics or get_translation_metrics()
        self._stream_adapter = stream_adapter or (
            LangGraphTranslationStreamAdapter(event_sink, self._metrics)
            if event_sink is not None
            else None
        )

    async def prepare_message(self, message_id: str) -> PreparedTranslation:
        """Read one durable message, resolve source/context once, then fan out."""
        async with self._session_factory() as session:
            message = await session.get(Message, message_id)
            if message is None:
                raise TranslationPreparationError("message not found")
            if message.deleted_at is not None:
                raise TranslationPreparationError("message has been recalled")

            # Copy scalar values before awaiting an external resolver/provider.
            language_hint = message.source_language or await session.scalar(
                select(User.preferred_language).where(User.id == message.sender_id)
            )
            snapshot = (
                message.id,
                message.revision,
                message.conversation_id,
                message.sender_id,
                message.original_text,
                language_hint or "en",
            )
            target_languages = frozenset(
                (
                    await session.scalars(
                        select(User.preferred_language)
                        .join(ConversationMember, ConversationMember.user_id == User.id)
                        .where(ConversationMember.conversation_id == message.conversation_id)
                    )
                ).all()
            )
            await session.commit()

        resolution = await self._language_resolver.resolve(snapshot[4], snapshot[5])
        source_context = list(
            await self._source_context_provider.get_recent_source_messages(
                snapshot[2], self._context_size
            )
        )
        async with self._session_factory() as update_session:
            current = await update_session.get(Message, snapshot[0])
            if current is None or current.deleted_at is not None:
                raise TranslationPreparationError("message has been recalled")
            if current.revision != snapshot[1]:
                raise TranslationPreparationError("message changed during preparation")
            if current.source_language != resolution.language:
                current.source_language = resolution.language
            await update_session.commit()

        return PreparedTranslation(
            message_id=snapshot[0],
            message_revision=snapshot[1],
            conversation_id=snapshot[2],
            sender_id=snapshot[3],
            content=snapshot[4],
            source_language=resolution.language,
            source_context=source_context,
            target_languages=target_languages - {resolution.language},
        )

    async def run_target(
        self,
        prepared: PreparedTranslation,
        target_language: str,
        *,
        reclaim_active: bool = False,
    ) -> TranslationResult:
        """Claim one target, execute exactly one graph, and persist its result."""
        if target_language not in prepared.target_languages:
            raise ValueError("target language is not part of the prepared snapshot")

        async with self._session_factory() as claim_session:
            claim = await TranslationRepository(claim_session).claim_translation(
                message_id=prepared.message_id,
                message_revision=prepared.message_revision,
                source_language=prepared.source_language,
                target_language=target_language,
                retry_active=reclaim_active,
            )
        if not claim.claimed:
            return claim.translation
        self._metrics.increment("translation_jobs_total")

        job_id = claim.translation.current_job_id
        if not job_id:
            raise RuntimeError("claimed translation has no job id")
        initial_state = {
            "message_id": prepared.message_id,
            "message_revision": prepared.message_revision,
            "conversation_id": prepared.conversation_id,
            "sender_id": prepared.sender_id,
            "original_text": prepared.content,
            "source_language": prepared.source_language,
            "source_language_resolved": True,
            "target_language": target_language,
            "context": prepared.source_context,
            "context_resolved": True,
        }
        recipient_ids = tuple(
            self._recipient_ids_for_target(prepared, target_language)
            if self._recipient_ids_for_target is not None
            else ()
        )
        started_at = perf_counter()
        async with self._provider_semaphore:
            graph = self._graph_factory()
            if self._stream_adapter is not None:
                result = await self._stream_adapter.run(
                    graph,
                    initial_state,
                    TranslationStreamRequest(
                        message_id=prepared.message_id,
                        message_revision=prepared.message_revision,
                        target_language=target_language,
                        translation_job_id=job_id,
                        recipient_ids=recipient_ids,
                    ),
                )
            else:
                result = await graph.ainvoke(initial_state)
        content = result.get("translated_text", prepared.content)
        model = str(result.get("model", ""))
        if not result.get("is_fallback"):
            status, fallback_level, provider = "completed", "none", "llm"
        elif model:
            status, fallback_level, provider = (
                "fallback_completed",
                "deep_translator",
                "deep_translator",
            )
        else:
            status, fallback_level, provider = "failed", "original", ""
            # The UI can render PreparedTranslation.content, but a failed path
            # must never persist that original as a successful translation.
            content = None

        async with self._session_factory() as finalize_session:
            current_message = await finalize_session.get(Message, prepared.message_id)
            if (
                current_message is None
                or current_message.deleted_at is not None
                or current_message.revision != prepared.message_revision
            ):
                persisted = await TranslationRepository(finalize_session).mark_translation_stale(
                    message_id=prepared.message_id,
                    message_revision=prepared.message_revision,
                    target_language=target_language,
                    expected_job_id=claim.translation.current_job_id,
                )
            else:
                persisted = await TranslationRepository(finalize_session).finalize_translation(
                    message_id=prepared.message_id,
                    message_revision=prepared.message_revision,
                    target_language=target_language,
                    content=content,
                    status=status,
                    fallback_level=fallback_level,
                    provider=provider,
                    model=model,
                    expected_job_id=claim.translation.current_job_id,
                )
        if persisted is None:
            raise RuntimeError("translation claim was lost before finalization")
        self._metrics.observe_seconds("translation_duration_seconds", perf_counter() - started_at)
        if persisted.status == "stale":
            self._metrics.increment("translation_stale_total")
        elif persisted.status == "failed":
            self._metrics.increment("translation_failed_total")
        else:
            self._metrics.increment("translation_completed_total")
            if persisted.status == "fallback_completed":
                self._metrics.increment("translation_fallback_total")
        if self._event_sink is not None and persisted.status != "stale":
            if persisted.status == "failed":
                await self._event_sink.translation_failed(
                    persisted,
                    recipient_ids,
                    prepared.content,
                    job_id,
                )
            else:
                await self._event_sink.translation_completed(
                    persisted,
                    recipient_ids,
                    job_id,
                )
        return persisted

    async def run_all_targets(
        self,
        prepared: PreparedTranslation,
        *,
        reclaim_active: bool = False,
    ) -> list[TranslationResult]:
        """Fan out one independently claimed graph execution per target.

        `run_target` obtains all sessions itself, so concurrent tasks never share
        the prepare session or one another's mutable AsyncSession.
        """
        return list(
            await asyncio.gather(
                *(
                    self.run_target(
                        prepared,
                        target,
                        reclaim_active=reclaim_active,
                    )
                    for target in prepared.target_languages
                )
            )
        )

    async def ensure_translation(
        self,
        message_id: str,
        target_language: str,
    ) -> TranslationResult | None:
        """Ensure one latest-revision translation exists for a requested target.

        The initial target snapshot is immutable. CP-04's logical key makes
        repeated calls idempotent. A source-equals-target entry has no durable
        TranslationResult by contract, so this method returns ``None``.
        """
        prepared = await self.prepare_message(message_id)
        if target_language == prepared.source_language:
            return None
        return await self.run_target(
            replace(prepared, target_languages=frozenset({target_language})),
            target_language,
        )
