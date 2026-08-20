"""Database-backed source of the audience facts a translation is shaped by.

Satisfies `src/agents/customization.py`'s Protocol structurally rather than by
inheritance, the same arrangement `DatabaseContextProvider` uses: the agent
depends on the shape, this module depends on the schema, and neither imports
the other. That is what keeps the agent runnable against a different store, and
what lets the evaluation harness supply its own without a database at all.

Reads only. The rows come from the background inference that fills
`conversation_profiles`, and this sits on the request path where an extra model
call is not affordable.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.customization import Customization
from src.database.models import ConversationProfile

logger = logging.getLogger(__name__)


class DatabaseCustomizationProvider:
    """Looks up what a conversation is about and who it is with."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind one open session.

        Built per request, like `DatabaseContextProvider`: an AsyncSession is
        not safe for concurrent use, and the buckets of one message run under
        `asyncio.gather`.
        """
        self._session = session

    async def get_customization(
        self,
        conversation_id: str,
        *,
        original_text: str,
        source_language: str,
        target_language: str,
    ) -> Customization:
        """Return the conversation's inferred subject area and audience.

        `original_text` and `source_language` are accepted and unused; the
        glossary lookup that will need them comes later, and widening the
        Protocol afterwards would mean editing every implementation.

        Any failure returns the empty customization rather than raising. The
        caller is a graph node that must not fail a translation, and an absent
        profile is in any case indistinguishable from one that has not been
        inferred yet — which is every conversation for its first few messages.
        """
        if not conversation_id:
            return Customization()

        try:
            row = await self._session.scalar(
                select(ConversationProfile).where(
                    ConversationProfile.conversation_id == conversation_id
                )
            )
        except Exception as exc:
            logger.warning("Reading the conversation profile failed: %s", exc)
            return Customization()

        if row is None:
            return Customization()
        return Customization(domain=row.domain, audience=row.audience)
