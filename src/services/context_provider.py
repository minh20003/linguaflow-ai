"""Database-backed conversation context for the Translation Agent (ADR-01).

Lives in the services layer, not in `src/agents/`, so the agent package never
imports `src/database/`. This class satisfies the `ContextProvider` protocol
structurally — the agent depends on the shape, not on this module.

Context lines are read from `messages.original_text`. Per ADR-01 the `messages`
table is the single source of context; there is no separate store to fall out of
sync with it.

Withdrawn messages are excluded. `original_text` survives a withdrawal in the
database, and the API blanks it out on the way to the client
(`src/api/routes.py`, `src/services/chat.py`); the agent has to honour the same
boundary, or a sender who withdrew a message would still see its wording reach
the model — and, through the model, a recipient.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.context_provider import DEFAULT_CONTEXT_SIZE
from src.database.models import Message

logger = logging.getLogger(__name__)


class DatabaseContextProvider:
    """Reads the most recent messages of a conversation from the database.

    Args:
        session: Session to read through. The caller owns its lifetime; this
            class never commits.
        before_message_id: The message currently being translated. It is
            excluded from its own context — without this the model sees the
            sentence twice and tends to treat the repetition as emphasis.
    """

    def __init__(
        self,
        session: AsyncSession,
        before_message_id: str | None = None,
    ) -> None:
        self._session = session
        self._before_message_id = before_message_id

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        """Return up to `limit` recent messages, oldest first.

        Args:
            conversation_id: Conversation whose history to read.
            limit: Maximum number of messages to return.

        Returns:
            Lines formatted as ``U01: text``, oldest first. Withdrawn and
            text-free messages are left out. Empty when the conversation has no
            other messages, or on any read failure — missing context degrades
            the translation but must not block it.
        """
        if not conversation_id or limit <= 0:
            return []

        # Newest-first with a limit, then reversed: the index on
        # (conversation_id, created_at, id) makes this a range scan rather than
        # a sort over the whole conversation.
        query = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                # Withdrawn: nobody can read it in the app any more, so nothing
                # of it may reach the model either.
                Message.deleted_at.is_(None),
                # Attachment-only messages carry no text; an empty line would
                # cost tokens and tell the model nothing.
                Message.original_text != "",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        if self._before_message_id is not None:
            query = query.where(Message.id != self._before_message_id)

        try:
            rows = (await self._session.scalars(query)).all()
        except Exception as exc:
            logger.warning("Reading conversation context failed: %s", exc)
            return []

        return _format_context_lines(reversed(rows))


def _format_context_lines(messages) -> list[str]:
    """Label each line with a per-conversation speaker alias.

    Speakers are numbered ``U01``, ``U02``, … in order of first appearance
    rather than named. Two reasons: the sender's row is not loaded here, so a
    name would cost a join per line; and the agent is meant to infer register
    and pronouns from what was said, not from who is labelled how. The same
    convention is used in `eval/golden_set.jsonl`, so what the evaluation
    measures is what production sends.
    """
    aliases: dict[str, str] = {}
    lines = []
    for message in messages:
        alias = aliases.get(message.sender_id)
        if alias is None:
            alias = f"U{len(aliases) + 1:02d}"
            aliases[message.sender_id] = alias
        lines.append(f"{alias}: {message.original_text}")
    return lines
