"""Tests for the minimal authenticated conversation REST API."""

from datetime import UTC, datetime, timedelta

import pytest

from src.database.models import Message
from tests.conftest import auth_headers_for_user


@pytest.mark.asyncio
async def test_create_direct_conversation_adds_creator_once(
    client,
    test_user,
    test_user_headers,
    test_user_two,
):
    """The creator is automatically included and duplicate IDs are harmless."""
    response = await client.post(
        "/api/v1/conversations",
        headers=test_user_headers,
        json={
            "type": "direct",
            "member_ids": [test_user_two.id, test_user.id, test_user_two.id],
            "title": "Project chat",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "direct"
    assert data["title"] == "Project chat"
    assert data["created_by"] == test_user.id
    assert set(data["member_ids"]) == {test_user.id, test_user_two.id}
    assert len(data["member_ids"]) == 2


@pytest.mark.asyncio
async def test_create_conversation_validates_member_rules(
    client,
    test_user,
    test_user_headers,
):
    """Direct/group cardinality and referenced users are checked server-side."""
    direct_response = await client.post(
        "/api/v1/conversations",
        headers=test_user_headers,
        json={"type": "direct", "member_ids": []},
    )
    assert direct_response.status_code == 400

    group_response = await client.post(
        "/api/v1/conversations",
        headers=test_user_headers,
        json={"type": "group", "member_ids": []},
    )
    assert group_response.status_code == 400

    missing_user_response = await client.post(
        "/api/v1/conversations",
        headers=test_user_headers,
        json={"type": "direct", "member_ids": ["missing-user-id"]},
    )
    assert missing_user_response.status_code == 400


@pytest.mark.asyncio
async def test_list_conversations_only_returns_memberships(
    client,
    conversation_factory,
    test_user,
    test_user_headers,
    test_user_two,
    test_user_three,
):
    """A user cannot discover conversations they do not belong to."""
    visible = await conversation_factory(test_user, [test_user_two])
    await conversation_factory(test_user_two, [test_user_three])

    response = await client.get("/api/v1/conversations", headers=test_user_headers)

    assert response.status_code == 200
    assert [conversation["id"] for conversation in response.json()] == [visible.id]


@pytest.mark.asyncio
async def test_conversation_history_is_member_protected(
    client,
    conversation_factory,
    test_user,
    test_user_two,
    test_user_three,
):
    """A non-member receives a forbidden response instead of message history."""
    conversation = await conversation_factory(test_user, [test_user_two])

    response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages",
        headers=auth_headers_for_user(test_user_three),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not a member of this conversation"


@pytest.mark.asyncio
async def test_conversation_history_returns_recent_messages_chronologically(
    client,
    conversation_factory,
    test_db,
    test_user,
    test_user_headers,
    test_user_two,
):
    """Recent history has a stable chronological order and includes client IDs."""
    conversation = await conversation_factory(test_user, [test_user_two])
    first_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        Message(
            client_message_id="history-1",
            conversation_id=conversation.id,
            sender_id=test_user.id,
            original_text="First",
            created_at=first_time,
        ),
        Message(
            client_message_id="history-2",
            conversation_id=conversation.id,
            sender_id=test_user_two.id,
            original_text="Second",
            created_at=first_time + timedelta(seconds=1),
        ),
        Message(
            client_message_id="history-3",
            conversation_id=conversation.id,
            sender_id=test_user.id,
            original_text="Third",
            created_at=first_time + timedelta(seconds=2),
        ),
    ]
    test_db.add_all(messages)
    await test_db.commit()

    response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages?limit=2",
        headers=test_user_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert [message["client_message_id"] for message in data] == ["history-2", "history-3"]
    assert [message["original_text"] for message in data] == ["Second", "Third"]

    invalid_limit = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages?limit=101",
        headers=test_user_headers,
    )
    assert invalid_limit.status_code == 422
