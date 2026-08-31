"""Where the assistant is allowed to look, decided by where it was spoken to.

Two scopes, and the request's origin picks one -- never the question's wording,
because a question cannot be trusted to widen its own permissions.

`personal` is the private assistant thread. Somebody in their own chat with the
assistant is asking about their own account, and the things they ask about --
"liệt kê tất cả các cuộc hẹn sắp tới" -- were arranged in the threads where the
arranging happened. An assistant confined to the thread it is standing in can
only see that thread, which contains none of them, so the honest answer would
always be "I found nothing" no matter how much the account holds.

`conversation` is an `@assistant` tag or a reply inside a real thread. There the
assistant reads that conversation and nothing else. The person framed the
question locally, and the answer is produced in a room other people are in.

This is a different rule from the one about who may *read* the reply. An
in-conversation answer is a `private` message visible only to the person who
asked (ADR-31); that governs the answer's audience, while this governs the
assistant's reading. Both hold at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Conversation, ConversationMember

ScopeKind = Literal["personal", "conversation"]

# The title `ChatService` gives the one-member thread it creates per account.
# Matching on it rather than on "a group with one member" because that shape is
# reachable by ordinary means -- somebody leaving a group leaves one behind --
# and a group that happens to have emptied out must not silently become a
# window onto every conversation its last member is in.
PERSONAL_THREAD_TITLE = "__linguachat_assistant__"


@dataclass(frozen=True, slots=True)
class AssistantScope:
    """What one assistant request may read."""

    kind: ScopeKind
    user_id: str
    origin_conversation_id: str

    @property
    def is_personal(self) -> bool:
        return self.kind == "personal"

    async def conversation_ids(self, db: AsyncSession) -> tuple[str, ...]:
        """The conversations this request may search, origin first.

        Origin first so the thread the person is actually looking at leads the
        results when scores tie, and so a personal scope degrades to exactly the
        old behaviour if the membership query returns nothing.

        Every conversation the account belongs to, in the personal case. There
        is no per-message filtering to add here: `assistant_chunks` is built
        from public messages only, so a chunk cannot carry text its conversation
        does not already share with all of its members -- and membership is what
        this query checks.
        """
        if not self.is_personal:
            return (self.origin_conversation_id,)
        rows = await db.scalars(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == self.user_id
            )
        )
        others = [cid for cid in rows.all() if cid != self.origin_conversation_id]
        return (self.origin_conversation_id, *others)


async def scope_for(
    db: AsyncSession, *, conversation_id: str, user_id: str
) -> AssistantScope:
    """Decide the scope from the conversation the request arrived in.

    Read from the row rather than passed in by the caller: the socket, the
    mention handler and the background paths would each have had to reach the
    same conclusion, and a scope that widens when one of them gets it wrong is
    the wrong thing to make easy to get wrong.
    """
    # Without a session there is no way to establish that this is the personal
    # thread, and "cannot tell" has to resolve to the narrower scope. Widening
    # on a missing dependency is how a permission check becomes decorative.
    title = (
        await db.scalar(
            select(Conversation.title).where(Conversation.id == conversation_id)
        )
        if db is not None
        else None
    )
    kind: ScopeKind = "personal" if title == PERSONAL_THREAD_TITLE else "conversation"
    return AssistantScope(
        kind=kind, user_id=user_id, origin_conversation_id=conversation_id
    )
