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
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import build_translation_graph
from src.agents.observability import build_runnable_config
from src.database import get_async_session_maker
from src.database.models import ConversationMember, Message, TranslationResult, User
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
        recipients_by_language = await _recipients_by_language(
            session, snapshot["conversation_id"]
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
) -> dict[str, list[str]]:
    """Group a conversation's members by the language each of them reads.

    One query answers both questions the fan-out needs: which languages are in
    play, and who wants each. The keys are the distinct set, so no second query.

    The sender is included deliberately. If they wrote in a language other than
    the one they read, they get a translation too — which falls out for free.
    """
    rows = await session.execute(
        select(ConversationMember.user_id, User.preferred_language)
        .join(User, User.id == ConversationMember.user_id)
        .where(ConversationMember.conversation_id == conversation_id)
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

    settings = get_settings()

    # Each language gets its own session: AsyncSession is not safe for
    # concurrent use, and these run under asyncio.gather.
    async with session_factory() as session:
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
            return
        except Exception as exc:
            logger.warning("Translation into %s failed: %s", target_language, exc)
            return

        detected_source = result.get("source_language") or snapshot["source_language"]

        # The agent's passthrough branch already skips the LLM when the message
        # is in the language this member reads. Nothing to persist or send —
        # they have the original (docs/CONTRACT.md section 4.3).
        if detected_source == target_language:
            await _store_detected_source(session, snapshot["message_id"], detected_source)
            return

        translated_text = (result.get("translated_text") or "").strip()
        if not translated_text:
            return

        await _store_detected_source(session, snapshot["message_id"], detected_source)
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

    try:
        await publisher.send_to_users(user_ids, event.model_dump(mode="json"))
    except Exception as exc:
        # The translation is persisted; an undelivered event is recovered from
        # message history on reconnect.
        logger.warning("Publishing translation into %s failed: %s", target_language, exc)


async def _store_detected_source(
    session: AsyncSession,
    message_id: str,
    detected_source: str,
) -> None:
    """Replace the provisional source_language with what detection found."""
    message = await session.get(Message, message_id)
    if message is None or message.source_language == detected_source:
        return
    message.source_language = detected_source
    await session.commit()


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
