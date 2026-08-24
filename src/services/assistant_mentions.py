"""Run the conversation-intelligence agent for an explicit ``@assistant`` mention."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.database import get_async_session_maker
from src.services.conversation_intelligence import ConversationIntelligenceService

logger = logging.getLogger(__name__)
_TASKS: set[asyncio.Task[Any]] = set()


def schedule_assistant_mention(
    *, message_id: str, conversation_id: str, requester_id: str, publisher: Any
) -> None:
    """Start explicit assistant work after the triggering message is delivered.

    The extraction agent may call an LLM, so it must never hold up the chat
    WebSocket. Its output remains a pending proposal: the user still confirms
    or rejects it through the existing human-in-the-loop endpoints.
    """
    task = asyncio.create_task(
        _process(
            message_id=message_id,
            conversation_id=conversation_id,
            requester_id=requester_id,
            publisher=publisher,
        )
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    task.add_done_callback(_log_failure)


def _log_failure(task: asyncio.Task[Any]) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.warning("Assistant mention processing failed", exc_info=task.exception())


async def _process(
    *, message_id: str, conversation_id: str, requester_id: str, publisher: Any
) -> None:
    """Persist agent proposals and notify only their authenticated owner."""
    async with get_async_session_maker()() as session:
        proposals = await ConversationIntelligenceService().extract_actions_from_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=requester_id,
            db=session,
        )

    for proposal in proposals:
        try:
            await publisher.send_to_user(
                requester_id,
                {
                    "type": "action_proposal_created",
                    "proposal": proposal.model_dump(mode="json"),
                },
            )
        except Exception:
            logger.warning("Assistant proposal event publish failed", exc_info=True)
