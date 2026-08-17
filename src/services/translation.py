"""Translates persisted messages and fans the results out by recipient language.

This is the seam between the chat flow and the Translation Agent. It is a peer
of `chat.py` in the services layer rather than a method on `ChatService`, for a
reason worth stating: `ChatService` holds the WebSocket's connection-scoped
session, which that endpoint deliberately releases between operations. A task
that outlives the send must never touch it — `AsyncSession` is not safe for
concurrent use, and holding it would keep a transaction open across an LLM call.

The module imports nothing from `src/api/` and nothing from `fastapi`. Its only
dependency on the transport is the `EventPublisher` protocol below, which
`ConnectionManager.send_to_users` satisfies unchanged. That makes "the agent is
independent of the transport layer" checkable from the import graph rather than
merely asserted in a document.

Nothing here raises into the caller. A translation that fails leaves the message
exactly as the recipient already received it — untranslated, but delivered
(NFR-02).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import build_translation_graph
from src.agents.nodes.translation import _HAS_LETTER, _MIN_DETECT_CHARS, _detect_local
from src.agents.observability import build_runnable_config
from src.database import get_async_session_maker
from src.database.models import (
    ConversationMember,
    Message,
    TranslationAttempt,
    TranslationResult,
    User,
)
from src.schemas.chat import TranslationCompletedEvent
from src.services.context_provider import DatabaseContextProvider

logger = logging.getLogger(__name__)

# asyncio.create_task holds only a weak reference, so a task with no other
# reference can be garbage-collected mid-flight and its exception swallowed.
_BACKGROUND_TASKS: set[asyncio.Task] = set()

# This deliberately stays small and local to one process. It avoids repeat LLM
# calls for common short phrases without turning translation delivery into a
# cache dependency or changing the persistence contract.
_CACHE_MAX_SIZE = 200
_translation_cache: dict[tuple[str, str, str, str], str] = {}


def _normalize_cache_text(text: str) -> str:
    """Remove incidental outer whitespace without changing the phrase itself."""
    return text.strip()


def _is_cacheable(text: str) -> bool:
    """Limit completed-value caching to short, simple phrases."""
    normalized = _normalize_cache_text(text)
    return bool(normalized) and len(normalized) <= 30 and len(normalized.split()) <= 3


def _cache_key(
    conversation_id: str,
    text: str,
    source_language: str,
    target_language: str,
) -> tuple[str, str, str, str]:
    """Build a case-preserving key scoped to the conversation."""
    return (
        conversation_id,
        _normalize_cache_text(text),
        source_language,
        target_language,
    )


def _confirmed_cache_source(snapshot: Mapping[str, Any]) -> str | None:
    """Return a source language only when the graph's local fast path trusts it.

    ``Message.source_language`` starts as the sender's preference, not a fact
    about this particular message. Reusing it before the graph would therefore
    be unsafe unless the existing local detector independently agrees with it.
    """
    text = _normalize_cache_text(str(snapshot.get("original_text") or ""))
    declared = str(snapshot.get("source_language") or "")
    if (
        not declared
        or len(text) < _MIN_DETECT_CHARS
        or not _HAS_LETTER.search(text)
    ):
        return None

    try:
        detected = _detect_local(text)
    except Exception as exc:
        logger.warning("Local language detection for the translation cache failed: %s", exc)
        return None
    return detected if detected == declared else None


def _cache_primary_translation(
    *,
    snapshot: Mapping[str, Any],
    target_language: str,
    source_language: str,
    translated_text: str,
) -> None:
    """Best-effort insertion of a completed primary-LLM translation."""
    try:
        if not _is_cacheable(str(snapshot["original_text"])):
            return
        if len(_translation_cache) >= _CACHE_MAX_SIZE:
            for key in list(_translation_cache)[: _CACHE_MAX_SIZE // 2]:
                del _translation_cache[key]
        _translation_cache[
            _cache_key(
                str(snapshot["conversation_id"]),
                str(snapshot["original_text"]),
                source_language,
                target_language,
            )
        ] = translated_text
    except Exception as exc:
        logger.warning("Caching completed translation failed: %s", exc)


class EventPublisher(Protocol):
    """Delivers an event to a set of users. Satisfied by ConnectionManager."""

    async def send_to_users(
        self,
        user_ids: Iterable[str],
        payload: Mapping[str, Any],
    ) -> None: ...


def schedule_translations(
    *,
    message: Message,
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession] | None = None,
    graph_factory: Callable[[AsyncSession, str], Any] | None = None,
) -> None:
    """Translate a persisted message for every recipient language, in the background.

    Returns immediately. The WebSocket receive loop is never made to wait on a
    translation, which takes around 1.5 seconds.

    `session_factory` and `graph_factory` are plain parameters rather than
    FastAPI dependencies on purpose: the WebSocket test fixture builds its own
    application and can only override `get_db` and `get_connection_manager`, so
    a dependency here would be impossible to stub.

    Args:
        message: The message as persisted, already broadcast in its original form.
        publisher: Transport used to deliver the finished translations.
        session_factory: Opens a session for the background work. Defaults to
            the application session maker — never the caller's session.
        graph_factory: Builds the agent graph given a session and the id of the
            message being translated. Defaults to the real translation graph.
    """
    # Read what the task needs now, as plain values. The ORM instance belongs to
    # the caller's session and must not be touched from another task.
    snapshot = {
        "message_id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "original_text": message.original_text,
        "source_language": message.source_language,
        "edited_at": message.edited_at,
    }

    task = asyncio.create_task(
        _translate_message(
            snapshot=snapshot,
            publisher=publisher,
            session_factory=session_factory or get_async_session_maker(),
            graph_factory=graph_factory or _default_graph_factory,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    task.add_done_callback(_log_task_failure)


def _default_graph_factory(session: AsyncSession, message_id: str) -> Any:
    """Build a graph reading context from the database, excluding this message."""
    return build_translation_graph(DatabaseContextProvider(session, message_id))


def _log_task_failure(task: asyncio.Task) -> None:
    """Surface a background failure instead of letting it vanish."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception("Background translation failed", exc_info=exc)


async def _translate_message(
    *,
    snapshot: Mapping[str, Any],
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession],
    graph_factory: Callable[[AsyncSession, str], Any],
) -> None:
    """Translate one message into every language its recipients read."""
    async with session_factory() as session:
        recipients_by_language = await _recipients_by_language(
            session, snapshot["conversation_id"], snapshot["sender_id"]
        )

    if not recipients_by_language:
        return

    await asyncio.gather(
        *(
            _translate_into(
                snapshot=snapshot,
                target_language=language,
                user_ids=user_ids,
                publisher=publisher,
                session_factory=session_factory,
                graph_factory=graph_factory,
            )
            for language, user_ids in recipients_by_language.items()
        )
    )


async def _recipients_by_language(
    session: AsyncSession,
    conversation_id: str,
    sender_id: str,
) -> dict[str, list[str]]:
    """Group message recipients, excluding the sender, by reading language.

    The sender's bubble always shows the original text. Excluding them here
    prevents unnecessary LLM work and ensures no translation event or result is
    created solely for the author of a message.
    """
    rows = await session.execute(
        select(ConversationMember.user_id, User.preferred_language)
        .join(User, User.id == ConversationMember.user_id)
        .where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id != sender_id,
        )
    )

    grouped: dict[str, list[str]] = {}
    for user_id, language in rows:
        grouped.setdefault(language, []).append(user_id)
    return grouped


async def _translate_into(
    *,
    snapshot: Mapping[str, Any],
    target_language: str,
    user_ids: list[str],
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession],
    graph_factory: Callable[[AsyncSession, str], Any],
) -> None:
    """Run the agent for one target language, then persist and publish."""
    from src.config import get_settings

    cacheable = _is_cacheable(str(snapshot["original_text"]))
    confirmed_source = _confirmed_cache_source(snapshot) if cacheable else None
    if confirmed_source:
        try:
            cached_text = _translation_cache.get(
                _cache_key(
                    str(snapshot["conversation_id"]),
                    str(snapshot["original_text"]),
                    confirmed_source,
                    target_language,
                )
            )
        except Exception as exc:
            logger.warning("Reading the translation cache failed: %s", exc)
            cached_text = None

        if cached_text is not None:
            if await _serve_cached_translation(
                snapshot=snapshot,
                target_language=target_language,
                source_language=confirmed_source,
                translated_text=cached_text,
                user_ids=user_ids,
                publisher=publisher,
                session_factory=session_factory,
            ):
                return

    settings = get_settings()

    # Minted before the run so the same value identifies this attempt in the
    # database and in the Langfuse trace. A trace found in the UI leads to a row,
    # and a row leads back to its trace, without depending on SDK internals.
    attempt_id = str(uuid.uuid4())
    started = time.perf_counter()

    # Each language gets its own session: AsyncSession is not safe for
    # concurrent use, and these run under asyncio.gather.
    async with session_factory() as session:

        async def record(outcome: str, *, result: Mapping[str, Any] | None = None,
                         translation_id: str | None = None) -> None:
            """Log this attempt, whatever became of it."""
            await record_attempt(
                session,
                attempt_id=attempt_id,
                snapshot=snapshot,
                target_language=target_language,
                outcome=outcome,
                telemetry=(result or {}).get("telemetry") or {},
                source_language=(result or {}).get("source_language") or "",
                total_ms=int((time.perf_counter() - started) * 1000),
                translation_id=translation_id,
                settings=settings,
            )

        graph = graph_factory(session, snapshot["message_id"])
        state = {
            "conversation_id": snapshot["conversation_id"],
            "message_id": snapshot["message_id"],
            "sender_id": snapshot["sender_id"],
            "original_text": snapshot["original_text"],
            "source_language": snapshot["source_language"],
            "target_language": target_language,
        }

        try:
            result = await asyncio.wait_for(
                graph.ainvoke(
                    state,
                    config=build_runnable_config(
                        conversation_id=snapshot["conversation_id"],
                        message_id=snapshot["message_id"],
                        target_language=target_language,
                        attempt_id=attempt_id,
                        # One of the three keys Langfuse promotes to a
                        # first-class attribute; as ordinary metadata the
                        # conversation id cannot group traces in the UI.
                        langfuse_session_id=snapshot["conversation_id"],
                    ),
                ),
                timeout=settings.translation_timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Translation into %s timed out after %ss",
                target_language,
                settings.translation_timeout_seconds,
            )
            await record("timeout")
            return
        except Exception as exc:
            logger.warning("Translation into %s failed: %s", target_language, exc)
            await record("error")
            return

        detected_source = result.get("source_language") or snapshot["source_language"]

        # The agent's passthrough branch already skips the LLM when the message
        # is in the language this member reads. Nothing to persist or send —
        # they have the original (docs/CONTRACT.md section 4.3).
        if detected_source == target_language:
            await _store_detected_source(session, snapshot["message_id"], detected_source)
            await record("passthrough", result=result)
            return

        translated_text = (result.get("translated_text") or "").strip()
        if not translated_text:
            # Reached only if the graph returned nothing at all, which its own
            # fallback path is supposed to prevent. Silent until now.
            logger.warning("Translation into %s produced no text", target_language)
            await record("empty", result=result)
            return

        message = await _store_detected_source(
            session, snapshot["message_id"], detected_source
        )

        # Between the graph starting and finishing — around 1.5 seconds — the
        # sender may have edited or withdrawn the message. Persisting now would
        # store a translation of text that no longer exists, and because the
        # unique constraint makes the retranslation's insert lose to this row,
        # that stale text would be what every recipient reads (F-06).
        superseded = (
            message is None
            or message.deleted_at is not None
            or message.original_text != snapshot["original_text"]
        )
        if superseded:
            # The attempt is still recorded under its real outcome — the model
            # ran and the tokens were spent, and ADR-16 counts that — but the
            # text is neither stored nor delivered. Reusing the real outcome
            # avoids adding a value to the `outcome` check constraint, which
            # could not be changed without rebuilding the database.
            await record(str(result.get("telemetry", {}).get("outcome") or "llm"), result=result)
            return

        translation = await _persist_translation(
            session,
            message_id=snapshot["message_id"],
            target_language=target_language,
            translated_text=translated_text,
            model=str(result.get("model") or ""),
            latency_ms=int(result.get("latency_ms") or 0),
            is_fallback=bool(result.get("is_fallback")),
        )
        if translation is None:
            return

        telemetry = result.get("telemetry", {})
        if (
            not bool(result.get("is_fallback"))
            and telemetry.get("outcome") == "llm"
            and result.get("source_language")
            and telemetry.get("detect_method") == "langdetect"
        ):
            _cache_primary_translation(
                snapshot=snapshot,
                target_language=target_language,
                source_language=str(result["source_language"]),
                translated_text=translated_text,
            )

        # Built before the attempt is recorded, and deliberately so. Recording
        # rolls back on failure, and a rollback expires every instance in the
        # session — reading `translation.translated_text` afterwards would go
        # back to the database from a context that cannot await, and cost the
        # recipient a translation that had already been committed.
        event = TranslationCompletedEvent(
            message_id=snapshot["message_id"],
            conversation_id=snapshot["conversation_id"],
            translation_id=translation.id,
            source_language=detected_source,
            target_language=target_language,
            translated_text=translation.translated_text,
            model=translation.model,
            latency_ms=translation.latency_ms,
            is_fallback=translation.is_fallback,
        )

        await record(
            str(result.get("telemetry", {}).get("outcome") or "llm"),
            result=result,
            translation_id=event.translation_id,
        )

    try:
        await publisher.send_to_users(user_ids, event.model_dump(mode="json"))
    except Exception as exc:
        # The translation is persisted; an undelivered event is recovered from
        # message history on reconnect.
        logger.warning("Publishing translation into %s failed: %s", target_language, exc)


async def _serve_cached_translation(
    *,
    snapshot: Mapping[str, Any],
    target_language: str,
    source_language: str,
    translated_text: str,
    user_ids: list[str],
    publisher: EventPublisher,
    session_factory: Callable[[], AsyncSession],
) -> bool:
    """Persist and publish a completed cache value without creating an attempt.

    ``True`` means the cache path handled the request, including a message that
    became stale before the read. A persistence/cache error returns ``False`` so
    the caller can use the unchanged graph path instead.
    """
    try:
        async with session_factory() as session:
            message = await session.get(Message, snapshot["message_id"])
            superseded = (
                message is None
                or message.deleted_at is not None
                or message.original_text != snapshot["original_text"]
                or message.edited_at != snapshot.get("edited_at")
            )
            if superseded:
                return True

            translation = await _persist_translation(
                session,
                message_id=snapshot["message_id"],
                target_language=target_language,
                translated_text=translated_text,
                model="cache",
                latency_ms=0,
                is_fallback=False,
            )
            if translation is None:
                return False

            event = TranslationCompletedEvent(
                message_id=snapshot["message_id"],
                conversation_id=snapshot["conversation_id"],
                translation_id=translation.id,
                source_language=source_language,
                target_language=target_language,
                translated_text=translation.translated_text,
                model=translation.model,
                latency_ms=translation.latency_ms,
                is_fallback=translation.is_fallback,
            )
    except Exception as exc:
        logger.warning("Serving cached translation into %s failed: %s", target_language, exc)
        return False

    try:
        await publisher.send_to_users(user_ids, event.model_dump(mode="json"))
    except Exception as exc:
        # Match the normal path: persistence is enough for reconnect recovery.
        logger.warning("Publishing cached translation into %s failed: %s", target_language, exc)
    return True


async def record_attempt(
    session: AsyncSession,
    *,
    attempt_id: str,
    snapshot: Mapping[str, Any],
    target_language: str,
    outcome: str,
    telemetry: Mapping[str, Any],
    source_language: str,
    total_ms: int,
    translation_id: str | None,
    settings: Any,
) -> None:
    """Write one row describing how this translation attempt ended.

    Called at every exit of `_translate_into`, including the four that produce
    no translation at all. Those four are the reason the table exists: a
    fallback rate computed only over attempts that succeeded is not a rate.

    Failures here are logged and swallowed. Measurement must never be able to
    fail a translation, and a message already delivered must not be held up by
    a bookkeeping error (NFR-02).
    """
    try:
        # `source_language` on the result is the declared value passed straight
        # through when detection was skipped or failed. Recording that as
        # "detected" would make the two columns agree by construction and hide
        # exactly the disagreements ADR-11's second tier exists to catch.
        detect_method = str(telemetry.get("detect_method") or "")
        detected = source_language if detect_method in {"langdetect", "llm"} else None

        session.add(
            TranslationAttempt(
                id=attempt_id,
                message_id=snapshot["message_id"],
                target_language=target_language,
                source_language_declared=snapshot["source_language"],
                source_language_detected=detected,
                outcome=outcome,
                provider=settings.llm_provider,
                model_configured=settings.llm_model,
                model_served=str(telemetry.get("model_served") or ""),
                detect_method=detect_method,
                llm_calls=int(telemetry.get("llm_calls") or 0),
                input_tokens=int(telemetry.get("input_tokens") or 0),
                output_tokens=int(telemetry.get("output_tokens") or 0),
                finish_reason=str(telemetry.get("finish_reason") or ""),
                detect_ms=int(telemetry.get("detect_ms") or 0),
                context_ms=int(telemetry.get("context_ms") or 0),
                translate_ms=int(telemetry.get("translate_ms") or 0),
                fallback_ms=int(telemetry.get("fallback_ms") or 0),
                total_ms=total_ms,
                context_lines=int(telemetry.get("context_lines") or 0),
                fallback_reason=str(telemetry.get("fallback_reason") or ""),
                translation_id=translation_id,
            )
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.warning("Recording the %s attempt failed: %s", outcome, exc)


async def _store_detected_source(
    session: AsyncSession,
    message_id: str,
    detected_source: str,
) -> Message | None:
    """Replace the provisional source_language with what detection found.

    Returns the message so the caller can tell whether it still says what this
    translation was made from, without paying for a second read of the same row.
    """
    message = await session.get(Message, message_id)
    if message is None or message.source_language == detected_source:
        return message
    message.source_language = detected_source
    await session.commit()
    return message


async def _persist_translation(
    session: AsyncSession,
    *,
    message_id: str,
    target_language: str,
    translated_text: str,
    model: str,
    latency_ms: int,
    is_fallback: bool,
) -> TranslationResult | None:
    """Store one translation, or return the existing row if it is already there.

    The unique constraint on (message_id, target_language) means a retry cannot
    create a second row, so members sharing a language keep sharing one
    `translation_id` (docs/CONTRACT.md section 4.4).
    """
    translation = TranslationResult(
        message_id=message_id,
        target_language=target_language,
        translated_text=translated_text,
        model=model,
        latency_ms=latency_ms,
        is_fallback=is_fallback,
    )
    session.add(translation)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(TranslationResult).where(
                TranslationResult.message_id == message_id,
                TranslationResult.target_language == target_language,
            )
        )
        return existing

    await session.refresh(translation)
    return translation
