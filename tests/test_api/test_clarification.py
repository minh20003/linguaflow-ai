"""Tests for Execution-Relevant Ambiguity and Clarification API (B-08 / Batch L)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token, get_password_hash
from src.database.models import ActionProposal, Conversation, ConversationMember, Message, User
from src.services.agent_consent import set_consents


@pytest_asyncio.fixture
async def clarify_setup(test_db: AsyncSession):
    """Create test conversation and messages for clarification testing."""
    alice = User(
        email="alice_clarify@example.com",
        username="alice_clar",
        display_name="Alice Clarify",
        password_hash=get_password_hash("pass123"),
        role="member",
        preferred_language="en",
    )
    bob = User(
        email="bob_clarify@example.com",
        username="bob_clar",
        display_name="Bob Clarify",
        password_hash=get_password_hash("pass123"),
        role="member",
        preferred_language="vi",
    )
    outsider = User(
        email="outsider_clarify@example.com",
        username="outsider_clar",
        display_name="Outsider User",
        password_hash=get_password_hash("pass123"),
        role="member",
        preferred_language="fr",
    )
    test_db.add_all([alice, bob, outsider])
    await test_db.flush()

    conv = Conversation(type="direct", created_by=alice.id)
    test_db.add(conv)
    await test_db.flush()

    test_db.add_all([
        ConversationMember(conversation_id=conv.id, user_id=alice.id),
        ConversationMember(conversation_id=conv.id, user_id=bob.id),
    ])

    m_ambiguous = Message(
        conversation_id=conv.id,
        sender_id=alice.id,
        client_message_id="c-msg-ambig",
        original_text="Tôi sẽ gửi báo cáo tài chính sớm nhé.",
        source_language="vi",
    )
    m_clear = Message(
        conversation_id=conv.id,
        sender_id=bob.id,
        client_message_id="c-msg-clear",
        original_text="Ok, cảm ơn bạn nhiều.",
        source_language="vi",
    )
    test_db.add_all([m_ambiguous, m_clear])
    await test_db.commit()

    # Granted to all three, the outsider included: these tests measure
    # membership and ambiguity detection, not permissions (ADR-30).
    for account in (alice, bob, outsider):
        await set_consents(test_db, account.id, {"read_conversations": True})

    return {
        "alice": alice,
        "bob": bob,
        "outsider": outsider,
        "conv_id": conv.id,
        "m_ambiguous_id": m_ambiguous.id,
        "m_clear_id": m_clear.id,
        "m_ambiguous": m_ambiguous,
    }


@pytest.mark.asyncio
async def test_clarify_execution_relevant_ambiguity_detected(client: AsyncClient, clarify_setup):
    alice = clarify_setup["alice"]
    conv_id = clarify_setup["conv_id"]
    m_ambiguous_id = clarify_setup["m_ambiguous_id"]
    token = create_access_token(subject=alice.id)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='''{
  "is_ambiguous": true,
  "needs_clarification": true,
  "reason": "Missing specific deadline for the financial report submission.",
  "suggested_clarification_prompt": "Bạn dự kiến sẽ gửi báo cáo tài chính vào ngày giờ cụ thể nào?"
}'''
        )
    )

    with patch("src.agents.conversation_intelligence.clarification.get_llm", return_value=mock_llm):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/{m_ambiguous_id}/clarify",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_ambiguous"] is True
    assert data["needs_clarification"] is True
    assert "báo cáo tài chính" in data["suggested_clarification_prompt"]


@pytest.mark.asyncio
async def test_clarify_non_execution_ambiguity_skipped(client: AsyncClient, clarify_setup):
    bob = clarify_setup["bob"]
    conv_id = clarify_setup["conv_id"]
    m_clear_id = clarify_setup["m_clear_id"]
    token = create_access_token(subject=bob.id)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='''{
  "is_ambiguous": false,
  "needs_clarification": false,
  "reason": "Polite acknowledgment, no actionable tasks or execution ambiguity.",
  "suggested_clarification_prompt": null
}'''
        )
    )

    with patch("src.agents.conversation_intelligence.clarification.get_llm", return_value=mock_llm):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/{m_clear_id}/clarify",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_ambiguous"] is False
    assert data["needs_clarification"] is False
    assert data["suggested_clarification_prompt"] is None


@pytest.mark.asyncio
async def test_clarify_deleted_message_returns_no_clarification(client: AsyncClient, test_db: AsyncSession, clarify_setup):
    alice = clarify_setup["alice"]
    conv_id = clarify_setup["conv_id"]
    m_ambiguous = clarify_setup["m_ambiguous"]
    token = create_access_token(subject=alice.id)

    m_ambiguous.deleted_at = datetime.now(UTC)
    m_ambiguous.original_text = ""
    await test_db.commit()

    with patch("src.agents.conversation_intelligence.clarification.get_llm") as mock_get_llm:
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/{m_ambiguous.id}/clarify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert not mock_get_llm.called

    assert response.status_code == 200
    data = response.json()
    assert data["needs_clarification"] is False


@pytest.mark.asyncio
async def test_clarify_non_member_403(client: AsyncClient, clarify_setup):
    outsider = clarify_setup["outsider"]
    conv_id = clarify_setup["conv_id"]
    m_ambiguous_id = clarify_setup["m_ambiguous_id"]
    token = create_access_token(subject=outsider.id)

    response = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/{m_ambiguous_id}/clarify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_clarify_nonexistent_message_404(client: AsyncClient, clarify_setup):
    alice = clarify_setup["alice"]
    conv_id = clarify_setup["conv_id"]
    token = create_access_token(subject=alice.id)

    response = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/00000000-0000-0000-0000-000000000000/clarify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_clarify_provider_error_503(client: AsyncClient, clarify_setup):
    alice = clarify_setup["alice"]
    conv_id = clarify_setup["conv_id"]
    m_ambiguous_id = clarify_setup["m_ambiguous_id"]
    token = create_access_token(subject=alice.id)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("Provider 500 error"))

    with patch("src.agents.conversation_intelligence.clarification.get_llm", return_value=mock_llm):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/{m_ambiguous_id}/clarify",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_proposal_clarification_resolves_raw_relative_time(client: AsyncClient, test_db: AsyncSession, clarify_setup):
    alice = clarify_setup["alice"]
    conv_id = clarify_setup["conv_id"]
    message = clarify_setup["m_ambiguous"]
    message.created_at = datetime(2026, 8, 21, 8, 0, tzinfo=UTC)
    proposal = ActionProposal(
        conversation_id=conv_id,
        source_message_id=message.id,
        owner_user_id=alice.id,
        source_mode="on_demand",
        action_type="task",
        status="needs_clarification",
        title="Send financial report",
        raw_time_expression="mai 9h",
        missing_fields='["timezone", "time"]',
        confidence_score=0.8,
        idempotency_key="api-clarification-1",
    )
    test_db.add(proposal)
    await test_db.commit()

    response = await client.post(
        f"/api/v1/action-proposals/{proposal.id}/clarify",
        json={"answer": "Asia/Ho_Chi_Minh"},
        headers={"Authorization": f"Bearer {create_access_token(subject=alice.id)}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending_confirmation"
    assert payload["clarification_rounds"] == 1
    assert payload["scheduled_start_at"] == "2026-08-22T02:00:00Z"
    assert payload["confirmed_at"] is None


@pytest.mark.asyncio
async def test_proposal_clarification_is_owner_only_and_capped(client: AsyncClient, test_db: AsyncSession, clarify_setup):
    alice = clarify_setup["alice"]
    bob = clarify_setup["bob"]
    conv_id = clarify_setup["conv_id"]
    message = clarify_setup["m_ambiguous"]
    proposal = ActionProposal(
        conversation_id=conv_id,
        source_message_id=message.id,
        owner_user_id=alice.id,
        source_mode="on_demand",
        action_type="task",
        status="needs_clarification",
        title="Needs manual correction",
        raw_time_expression="mai 9h",
        missing_fields='["timezone", "time"]',
        clarification_rounds=2,
        confidence_score=0.8,
        idempotency_key="api-clarification-2",
    )
    test_db.add(proposal)
    await test_db.commit()
    unauthorized = await client.post(
        f"/api/v1/action-proposals/{proposal.id}/clarify",
        json={"answer": "Asia/Ho_Chi_Minh"},
        headers={"Authorization": f"Bearer {create_access_token(subject=bob.id)}"},
    )
    assert unauthorized.status_code == 403
    capped = await client.post(
        f"/api/v1/action-proposals/{proposal.id}/clarify",
        json={"answer": "Asia/Ho_Chi_Minh"},
        headers={"Authorization": f"Bearer {create_access_token(subject=alice.id)}"},
    )
    assert capped.status_code == 409
    assert "manual_correction_required" in capped.json()["detail"]
