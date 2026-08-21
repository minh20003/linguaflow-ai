"""Remembering what a message meant, so context can be found by meaning.

`build_context` takes the last three to five messages. That is the right window
for resolving a pronoun and useless for a reference to something agreed forty
messages ago — the reader knows what "the migration we talked about" is, and the
model, given only the last four lines, does not.

This module writes the half that makes the other kind of retrieval possible: one
vector per message, stored beside it. Reading them back is
`DatabaseContextProvider`'s job.

Two things are deliberately true of the write path. It runs in the background,
because it is an API call and the message has already been delivered. And it
only runs when `RAG_CONTEXT_ENABLED` is on — embedding every message of every
conversation for a feature nobody has switched on would spend real quota on
nothing. The consequence, which is the honest cost of that choice: turning the
flag on starts the memory from that moment, and older messages stay invisible to
it until somebody backfills them.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.database import get_async_session_maker
from src.database.models import MessageEmbedding
from src.services.embeddings import embed, embedding_model_name

logger = logging.getLogger(__name__)

# Strong references to running tasks: asyncio keeps only a weak one and will
# garbage-collect a task nobody awaits, mid-statement.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def schedule_message_embedding(
    *,
    message_id: str,
    conversation_id: str,
    text: str,
    session_factory: Callable[[], AsyncSession] | None = None,
    settings: Settings | None = None,
) -> None:
    """Fire and forget the embedding of one message.

    Returns immediately and can fail silently. The message it describes has
    already reached its recipients; nothing here may hold that up.

    Args:
        message_id: Message to remember.
        conversation_id: Its conversation, denormalised onto the row so the
            nearest-neighbour search can be scoped without a join.
        text: The message body.
        session_factory: Session source; defaults to the application's.
        settings: Configuration to read; defaults to the process settings.
    """
    settings = settings or get_settings()
    if not settings.rag_context_enabled:
        return
    if not message_id or not conversation_id or not (text or "").strip():
        return

    task = asyncio.create_task(
        _store(
            message_id=message_id,
            conversation_id=conversation_id,
            text=text,
            session_factory=session_factory or get_async_session_maker(),
            settings=settings,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


async def _store(
    *,
    message_id: str,
    conversation_id: str,
    text: str,
    session_factory: Callable[[], AsyncSession],
    settings: Settings,
) -> None:
    """Embed the text and store it, replacing any vector already held.

    Replacing rather than skipping: a message can be edited, and a vector
    describing the wording it used to have would retrieve it for the wrong
    reasons. `embed` returns None on every failure, and None here simply means
    this message will not be found by meaning — the time-ordered window still
    covers it.
    """
    try:
        vector = await embed(text, settings=settings)
        if vector is None:
            return

        model = embedding_model_name(settings)
        async with session_factory() as session:
            row = await session.scalar(
                select(MessageEmbedding).where(
                    MessageEmbedding.message_id == message_id
                )
            )
            if row is None:
                row = MessageEmbedding(
                    message_id=message_id, conversation_id=conversation_id
                )
                session.add(row)
            row.embedding = vector
            row.embedding_model = model
            await session.commit()
    except Exception as exc:
        logger.warning("Storing the embedding for a message failed: %s", exc)


def embedding_write_is_enabled(settings: Settings | None = None) -> bool:
    """Whether messages are being remembered at all.

    Exposed so a caller can say why retrieval found nothing, rather than
    leaving "no results" to mean both "nothing matched" and "nothing stored".
    """
    return (settings or get_settings()).rag_context_enabled
