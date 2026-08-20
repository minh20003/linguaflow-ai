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
from src.services.glossary import lookup_terms

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

        The glossary lookup is wrapped separately from the profile read so a
        glossary problem costs only the terms: a conversation keeps its inferred
        audience even when no term can be resolved.

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

        domain = row.domain if row is not None else ""
        audience = row.audience if row is not None else ""

        # Looked up after the profile, and with it: which rendering of a term
        # applies depends on who is reading, so "UI" resolves one way for an
        # internal audience and another for a client (ADR-26).
        try:
            terms = await lookup_terms(
                self._session,
                text=original_text,
                source_language=source_language,
                target_language=target_language,
                domain=domain,
                audience=audience,
            )
        except Exception as exc:
            logger.warning("Looking up glossary terms failed: %s", exc)
            terms = ()

        return Customization(domain=domain, audience=audience, glossary_terms=terms)
