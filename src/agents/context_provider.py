"""Conversation context sources for the Translation Agent.

The agent needs the most recent messages of a conversation to resolve pronouns
and keep the translation coherent across turns (docs/CONTRACT.md section 2,
ADR-01).

The `messages` table does not exist yet (see docs/architecture_diagram.md
section 4), so the context source is abstracted behind the protocol below. Once
that table lands, add an implementation that reads from the database — no node
has to change.
"""

from __future__ import annotations

from typing import Protocol

# Fallback window size when no explicit limit is given. The configured value
# lives in Settings.agent_context_size (the PRD specifies 3-5).
DEFAULT_CONTEXT_SIZE = 5


class ContextProvider(Protocol):
    """Supplies recent conversation history to the agent."""

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        """Return up to `limit` recent messages, oldest first.

        Each item is a line already formatted for inclusion in the prompt.
        Returns an empty list when the conversation has no history.
        """
        ...


class NullContextProvider:
    """Supplies no context. Default when no real source is configured.

    Translation still works, it just loses conversation awareness.
    """

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        return []


class InMemoryContextProvider:
    """Keeps context in process memory. For tests and demos only.

    Nothing survives a restart, so this must not be used in production.
    """

    def __init__(self, messages: dict[str, list[str]] | None = None) -> None:
        self._store: dict[str, list[str]] = messages or {}

    def add_message(self, conversation_id: str, message: str) -> None:
        """Append a message to a conversation's history."""
        self._store.setdefault(conversation_id, []).append(message)

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        history = self._store.get(conversation_id, [])
        if limit <= 0:
            return []
        return history[-limit:]
