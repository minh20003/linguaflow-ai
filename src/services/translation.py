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
from src.agents.observability import build_runnable_config
from src.database import get_async_session_maker
from src.database.models import (
    Conversation,
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
        conversation_type, recipients_by_language = await _recipients_by_language(
            session, snapshot["conversation_id"]
        )

    if not recipients_by_language:
        return

    recipients_by_language = _include_direct_sender(
        conversation_type=conversation_type,
        sender_id=snapshot["sender_id"],
        recipients_by_language=recipients_by_language,
    )

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
) -> tuple[str | None, dict[str, list[str]]]:
    """Group a conversation's members by the language each of them reads.

    One query answers everything the fan-out needs: which languages are in play,
    who wants each, and whether this is a one-to-one conversation. The
    conversation type rides along on the same join rather than costing a second
    round trip — this runs in a background task that can be abandoned when the
    caller goes away, and every extra await inside the session block is another
    point where that leaves a connection checked out.

    The sender is included deliberately. If they wrote in a language other than
    the one they read, they get a translation too — which falls out for free.

    Returns:
        The conversation's type (None when it has no members), and the members
        grouped by the language each of them reads.
    """
    rows = await session.execute(
        select(ConversationMember.user_id, User.preferred_language, Conversation.type)
        .join(User, User.id == ConversationMember.user_id)
        .join(Conversation, Conversation.id == ConversationMember.conversation_id)
        .where(ConversationMember.conversation_id == conversation_id)
    )

    conversation_type: str | None = None
    grouped: dict[str, list[str]] = {}
    for user_id, language, row_type in rows:
        conversation_type = row_type
        grouped.setdefault(language, []).append(user_id)
    return conversation_type, grouped


def _include_direct_sender(
    *,
    conversation_type: str | None,
    sender_id: str,
    recipients_by_language: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Let a one-to-one sender receive the translation of their own message.

    Grouping by reading language puts the sender in the bucket for the language
    *they* read, so the translation going to the other person never reaches
    them. That is what the controls under their own bubble need: the toggle,
    the rating and the edit box all describe a translation the sender otherwise
    only sees after a reload (docs/CONTRACT.md §4.4 rule 3).

    Limited to `direct` conversations because that is where the controls exist
    (§3.10). A group message has several translations and no single one belongs
    to the bubble, so the sender is shown nothing and needs nothing sent.

    Takes no session on purpose: the type it needs already arrived with the
    grouping, so this stays a plain function outside the session block.

    Args:
        conversation_type: `direct` or `group`, as read alongside the members.
        sender_id: Account that sent the message.
        recipients_by_language: Grouping to extend, left untouched.

    Returns:
        The same grouping, with the sender added to every language in a direct
        conversation.
    """
    if conversation_type != "direct":
        return recipients_by_language

    return {
        language: user_ids if sender_id in user_ids else [*user_ids, sender_id]
        for language, user_ids in recipients_by_language.items()
    }


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
