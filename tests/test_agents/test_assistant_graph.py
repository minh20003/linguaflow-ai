"""Tests for the Assistant Agent's planner-executor graph and its human gate.

The load-bearing assertion is that `human_confirm` genuinely suspends: a graph
that ran straight through it would approve everything while every other test
still passed, which is precisely the failure the mandatory-confirmation rule
exists to prevent (`docs/NewFeature.md` §1.3).

Nothing here reaches a network. The planner's model is injected, and the two
executors are patched at their service boundary — what is under test is the
graph's routing and gating, not the quality of a summary.

Fixtures live in this file rather than tests/conftest.py, which is shared across
all feature areas.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.agents.assistant import build_assistant_graph
from src.agents.assistant.graph import _parse_plan, respond, route_after_plan


def planner_returning(*operations: str) -> Any:
    """Build a model whose only job is to answer the planner prompt."""
    steps = ", ".join(f'{{"operation": "{name}", "reason": "test"}}' for name in operations)
    model = MagicMock()
    model.ainvoke = AsyncMock(return_value=MagicMock(content=f'{{"steps": [{steps}]}}'))
    return model


def config(thread: str) -> dict[str, Any]:
    """A thread id is what the checkpointer keys a suspended run on."""
    return {"configurable": {"thread_id": thread}}


@pytest.fixture(autouse=True)
def permitted_and_quiet(monkeypatch):
    """Grant the permission and silence the memory read, by default.

    `check_consent` and `load_memory` both query for real, which is the point of
    them — neither can be satisfied by seeding the state, and a test that could
    seed its way past a permission check would not be testing the check. So they
    are patched at their boundary here, and the two tests that are *about* those
    nodes override this.
    """
    monkeypatch.setattr(
        "src.agents.assistant.graph.require_consent", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "src.services.chat.ChatService.get_message_history", AsyncMock(return_value=[])
    )
    # Semantic recall off by default: it is additive, and the tests about
    # routing should not depend on an embedding provider being reachable.
    monkeypatch.setattr(
        "src.services.agent_consent.has_consent", AsyncMock(return_value=False)
    )


@pytest.mark.asyncio
async def test_the_graph_stops_at_the_human_gate_instead_of_confirming(monkeypatch) -> None:
    """The whole point of the gate: nothing is executed before a person answers."""
    confirm = AsyncMock()
    monkeypatch.setattr(
        "src.services.action_proposals.ActionProposalService.confirm_proposal", confirm
    )

    async def fake_extract(self, **kwargs):
        return [SimpleNamespace(model_dump=lambda mode: {"id": "p-1", "title": "Gửi báo cáo"})]

    monkeypatch.setattr(
        "src.services.conversation_intelligence.ConversationIntelligenceService."
        "extract_actions_from_message",
        fake_extract,
    )

    graph = build_assistant_graph(
        db=None,
        checkpointer=InMemorySaver(),
        llm_factory=lambda: planner_returning("extract_actions"),
    )
    result = await graph.ainvoke(
        {
            "conversation_id": "c-1",
            "user_id": "u-1",
            "request_text": "@assistant nhắc mình việc này",
            "memory": ["Tôi sẽ gửi báo cáo sáng mai"],
            "telemetry": {"source_message_id": "m-1"},
        },
        config("thread-gate"),
    )

    assert "__interrupt__" in result
    confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_resuming_the_gate_confirms_only_the_proposals_the_person_named(
    monkeypatch,
) -> None:
    """Silence is not consent: an unnamed proposal stays pending, not rejected."""
    confirmed: list[str] = []

    async def fake_confirm(self, proposal_id, user_id, corrections=None):
        confirmed.append(proposal_id)
        return SimpleNamespace(id=proposal_id, title=f"Việc {proposal_id}")

    monkeypatch.setattr(
        "src.services.action_proposals.ActionProposalService.confirm_proposal", fake_confirm
    )

    async def fake_extract(self, **kwargs):
        return [
            SimpleNamespace(model_dump=lambda mode: {"id": "p-1", "title": "A"}),
            SimpleNamespace(model_dump=lambda mode: {"id": "p-2", "title": "B"}),
        ]

    monkeypatch.setattr(
        "src.services.conversation_intelligence.ConversationIntelligenceService."
        "extract_actions_from_message",
        fake_extract,
    )

    graph = build_assistant_graph(
        db=None,
        checkpointer=InMemorySaver(),
        llm_factory=lambda: planner_returning("extract_actions"),
    )
    thread = config("thread-resume")
    await graph.ainvoke(
        {
            "conversation_id": "c-1",
            "user_id": "u-1",
            "request_text": "nhắc mình",
            "telemetry": {"source_message_id": "m-1"},
        },
        thread,
    )

    final = await graph.ainvoke(
        Command(resume={"approved_proposal_ids": ["p-1"]}),
        thread,
    )

    assert confirmed == ["p-1"]
    assert "Việc p-1" in final["reply"]


@pytest.mark.asyncio
async def test_a_missing_permission_ends_the_run_before_any_message_is_read(
    monkeypatch,
) -> None:
    """`check_consent` is the first node for a reason."""
    from src.services.agent_consent import ConsentRequiredError

    monkeypatch.setattr(
        "src.agents.assistant.graph.require_consent",
        AsyncMock(side_effect=ConsentRequiredError("read_conversations")),
    )
    loaded = AsyncMock(return_value=[])
    monkeypatch.setattr("src.services.chat.ChatService.get_message_history", loaded)

    graph = build_assistant_graph(
        db=None,
        checkpointer=InMemorySaver(),
        llm_factory=lambda: planner_returning("summarize"),
    )
    result = await graph.ainvoke(
        {
            "conversation_id": "c-1",
            "user_id": "u-1",
            "request_text": "tóm tắt giúp mình",
        },
        config("thread-consent"),
    )

    loaded.assert_not_awaited()
    assert "read_conversations" in result["reply"]


@pytest.mark.asyncio
async def test_a_summary_request_never_reaches_the_human_gate(monkeypatch) -> None:
    """Approving a summary would be a confirmation dialog with nothing to decide."""

    async def fake_summarize(self, **kwargs):
        return SimpleNamespace(
            message_count=3,
            model_dump=lambda mode: {"summary": "Nhóm chốt deadline thứ sáu", "key_points": []},
        )

    monkeypatch.setattr(
        "src.services.conversation_intelligence.ConversationIntelligenceService."
        "summarize_conversation",
        fake_summarize,
    )

    graph = build_assistant_graph(
        db=None,
        checkpointer=InMemorySaver(),
        llm_factory=lambda: planner_returning("summarize"),
    )
    result = await graph.ainvoke(
        {
            "conversation_id": "c-1",
            "user_id": "u-1",
            "request_text": "tóm tắt giúp mình",
        },
        config("thread-summary"),
    )

    assert "__interrupt__" not in result
    assert result["reply"] == "Nhóm chốt deadline thứ sáu"


@pytest.mark.asyncio
async def test_a_planner_outage_still_answers_by_falling_back_to_summarizing(
    monkeypatch,
) -> None:
    """No node raises: an LLM outage must not become a broken chat feature."""

    async def fake_summarize(self, **kwargs):
        return SimpleNamespace(
            message_count=1,
            model_dump=lambda mode: {"summary": "Bản tóm tắt dự phòng", "key_points": []},
        )

    monkeypatch.setattr(
        "src.services.conversation_intelligence.ConversationIntelligenceService."
        "summarize_conversation",
        fake_summarize,
    )

    broken = MagicMock()
    broken.ainvoke = AsyncMock(side_effect=RuntimeError("provider down"))

    graph = build_assistant_graph(
        db=None, checkpointer=InMemorySaver(), llm_factory=lambda: broken
    )
    result = await graph.ainvoke(
        {
            "conversation_id": "c-1",
            "user_id": "u-1",
            "request_text": "giúp mình với",
        },
        config("thread-outage"),
    )

    assert result["reply"] == "Bản tóm tắt dự phòng"


def test_the_planner_cannot_invent_an_operation_that_reaches_nothing() -> None:
    """An unknown name would route nowhere and finish looking successful."""
    steps = _parse_plan('{"steps": [{"operation": "delete_everything", "reason": "x"}]}')
    assert steps == []


def test_a_plan_naming_no_known_operation_still_produces_a_reply() -> None:
    """Routing to `respond` rather than off the end of the graph."""
    assert route_after_plan({"plan": []}) == "respond"
    assert respond({})["reply"]


def test_the_planner_survives_a_model_that_wraps_json_in_a_code_fence() -> None:
    """Providers add fences unprompted; a strict parser would read that as failure."""
    steps = _parse_plan('```json\n{"steps": [{"operation": "summarize", "reason": "r"}]}\n```')
    assert [step["operation"] for step in steps] == ["summarize"]


@pytest.mark.asyncio
async def test_semantic_recall_reaches_past_the_recent_window(monkeypatch) -> None:
    """Recall answers a question the recent window cannot.

    The two passes exist for different reasons: the time-ordered window is
    always right about recency, and semantic search reaches things said weeks
    ago that no limit would have included. This asserts the second one is
    merged in, and merged chronologically rather than appended.
    """
    from datetime import UTC, datetime

    old = SimpleNamespace(
        id="m-old",
        original_text="Chốt deadline là 30/9",
        deleted_at=None,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    recent = SimpleNamespace(
        id="m-recent",
        original_text="Sáng nay họp lúc 9h",
        deleted_at=None,
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
    )

    monkeypatch.setattr(
        "src.services.chat.ChatService.get_message_history", AsyncMock(return_value=[recent])
    )
    monkeypatch.setattr(
        "src.services.agent_consent.has_consent", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        "src.services.semantic_search.search_similar_messages",
        AsyncMock(return_value=[old]),
    )

    captured: dict[str, Any] = {}

    async def fake_summarize(self, **kwargs):
        return SimpleNamespace(
            message_count=2, model_dump=lambda mode: {"summary": "ok", "key_points": []}
        )

    monkeypatch.setattr(
        "src.services.conversation_intelligence.ConversationIntelligenceService."
        "summarize_conversation",
        fake_summarize,
    )

    graph = build_assistant_graph(
        db=None,
        checkpointer=InMemorySaver(),
        llm_factory=lambda: planner_returning("summarize"),
    )
    state = await graph.ainvoke(
        {
            "conversation_id": "c-1",
            "user_id": "u-1",
            "request_text": "deadline là khi nào",
        },
        config("thread-recall"),
    )
    captured["memory"] = state["memory"]

    # Oldest first, so the recalled line leads rather than being tacked on.
    assert captured["memory"] == ["Chốt deadline là 30/9", "Sáng nay họp lúc 9h"]


@pytest.mark.asyncio
async def test_a_recalled_message_already_in_the_window_is_not_repeated(
    monkeypatch,
) -> None:
    """A duplicated line reads to the model as the thing having been said twice."""
    from datetime import UTC, datetime

    same = SimpleNamespace(
        id="m-1",
        original_text="Chốt deadline là 30/9",
        deleted_at=None,
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
    )

    monkeypatch.setattr(
        "src.services.chat.ChatService.get_message_history", AsyncMock(return_value=[same])
    )
    monkeypatch.setattr(
        "src.services.agent_consent.has_consent", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        "src.services.semantic_search.search_similar_messages",
        AsyncMock(return_value=[same]),
    )

    async def fake_summarize(self, **kwargs):
        return SimpleNamespace(
            message_count=1, model_dump=lambda mode: {"summary": "ok", "key_points": []}
        )

    monkeypatch.setattr(
        "src.services.conversation_intelligence.ConversationIntelligenceService."
        "summarize_conversation",
        fake_summarize,
    )

    graph = build_assistant_graph(
        db=None,
        checkpointer=InMemorySaver(),
        llm_factory=lambda: planner_returning("summarize"),
    )
    state = await graph.ainvoke(
        {"conversation_id": "c-1", "user_id": "u-1", "request_text": "deadline"},
        config("thread-dedupe"),
    )

    assert state["memory"] == ["Chốt deadline là 30/9"]
