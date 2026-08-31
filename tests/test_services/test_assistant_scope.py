"""How far the assistant may read, and what decides it."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_password_hash
from src.database.models import Conversation, ConversationMember, User
from src.services.assistant_scope import (
    PERSONAL_THREAD_TITLE,
    AssistantScope,
    scope_for,
)


@pytest_asyncio.fixture
async def scope_setup(test_db: AsyncSession):
    """One person in three places: their own assistant thread, a DM and a group."""
    owner = User(
        email="scope_owner@example.com",
        username="scope_owner",
        display_name="Scope Owner",
        password_hash=get_password_hash("pass123"),
        role="member",
        preferred_language="vi",
    )
    colleague = User(
        email="scope_colleague@example.com",
        username="scope_colleague",
        display_name="Scope Colleague",
        password_hash=get_password_hash("pass123"),
        role="member",
        preferred_language="vi",
    )
    stranger = User(
        email="scope_stranger@example.com",
        username="scope_stranger",
        display_name="Scope Stranger",
        password_hash=get_password_hash("pass123"),
        role="member",
        preferred_language="vi",
    )
    test_db.add_all([owner, colleague, stranger])
    await test_db.flush()

    personal = Conversation(
        type="group", title=PERSONAL_THREAD_TITLE, created_by=owner.id
    )
    direct = Conversation(type="direct", created_by=owner.id)
    group = Conversation(type="group", title="Dự án", created_by=owner.id)
    # A conversation the owner is not in. Nothing may ever reach it.
    elsewhere = Conversation(type="group", title="Phòng khác", created_by=stranger.id)
    test_db.add_all([personal, direct, group, elsewhere])
    await test_db.flush()

    test_db.add_all(
        [
            ConversationMember(conversation_id=personal.id, user_id=owner.id),
            ConversationMember(conversation_id=direct.id, user_id=owner.id),
            ConversationMember(conversation_id=direct.id, user_id=colleague.id),
            ConversationMember(conversation_id=group.id, user_id=owner.id),
            ConversationMember(conversation_id=group.id, user_id=colleague.id),
            ConversationMember(conversation_id=elsewhere.id, user_id=stranger.id),
        ]
    )
    await test_db.commit()

    return {
        "owner": owner,
        "personal": personal,
        "direct": direct,
        "group": group,
        "elsewhere": elsewhere,
    }


@pytest.mark.asyncio
async def test_the_private_assistant_thread_reads_every_conversation_the_person_is_in(
    test_db: AsyncSession, scope_setup
):
    scope = await scope_for(
        test_db,
        conversation_id=scope_setup["personal"].id,
        user_id=scope_setup["owner"].id,
    )

    assert scope.is_personal
    reachable = await scope.conversation_ids(test_db)
    assert set(reachable) == {
        scope_setup["personal"].id,
        scope_setup["direct"].id,
        scope_setup["group"].id,
    }
    # Origin first, so the thread being looked at leads on a tie.
    assert reachable[0] == scope_setup["personal"].id


@pytest.mark.asyncio
async def test_a_mention_inside_a_conversation_reads_that_conversation_only(
    test_db: AsyncSession, scope_setup
):
    scope = await scope_for(
        test_db,
        conversation_id=scope_setup["group"].id,
        user_id=scope_setup["owner"].id,
    )

    assert not scope.is_personal
    assert await scope.conversation_ids(test_db) == (scope_setup["group"].id,)


@pytest.mark.asyncio
async def test_the_personal_scope_stops_at_conversations_the_person_belongs_to(
    test_db: AsyncSession, scope_setup
):
    """Widest is not "everything". It is this account's own membership."""
    scope = await scope_for(
        test_db,
        conversation_id=scope_setup["personal"].id,
        user_id=scope_setup["owner"].id,
    )

    assert scope_setup["elsewhere"].id not in await scope.conversation_ids(test_db)


@pytest.mark.asyncio
async def test_an_ordinary_group_is_never_mistaken_for_the_personal_thread(
    test_db: AsyncSession, scope_setup
):
    """The title is the identity. A one-member group is reachable by accident."""
    lonely = Conversation(type="group", title="Nhóm cũ", created_by=scope_setup["owner"].id)
    test_db.add(lonely)
    await test_db.flush()
    test_db.add(
        ConversationMember(conversation_id=lonely.id, user_id=scope_setup["owner"].id)
    )
    await test_db.commit()

    scope = await scope_for(
        test_db, conversation_id=lonely.id, user_id=scope_setup["owner"].id
    )

    assert not scope.is_personal


@pytest.mark.asyncio
async def test_a_scope_that_cannot_be_established_falls_back_to_the_narrow_one():
    """No session, no proof it is the personal thread. Widening on a missing
    dependency is how a permission check quietly becomes decorative."""
    scope = await scope_for(None, conversation_id="c-1", user_id="u-1")

    assert not scope.is_personal
    assert await scope.conversation_ids(None) == ("c-1",)


@pytest.mark.asyncio
async def test_a_conversation_scope_needs_no_query_to_answer_what_it_reaches():
    """It is one id by construction, so an unreachable database cannot widen it."""
    scope = AssistantScope(
        kind="conversation", user_id="u-1", origin_conversation_id="c-9"
    )

    assert await scope.conversation_ids(None) == ("c-9",)
