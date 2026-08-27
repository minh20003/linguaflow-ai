"""The Assistant Agent: a planner-executor state machine with a human gate.

```
START -> check_consent -> [not granted] -> ask_permission -> END
                       -> load_memory -> plan -> route
route -> summarize        -> respond -> END
route -> extract_actions  -> human_confirm -> execute -> respond -> END
route -> [no operation]   -> respond -> END
```

Planner-executor rather than ReAct, for the reason ADR-05 already gives for the
Translation Agent: the flow has conditional branches and a mandatory human gate,
and it does not need the model free to choose tools. `plan` emits a structured
list of operations and `route` dispatches on it, so the set of things that can
happen is fixed in code rather than decided by a model at run time.

Every node takes the full ``AssistantState`` and returns a dict holding only the
fields it changed; LangGraph merges those partial updates. That convention is
stated here once rather than repeated in each node's docstring, matching
`src/agents/nodes/translation.py`.

Hard rule, inherited from the Translation Agent: **no node raises**. A failure is
recorded in ``state["error"]`` and the flow continues to `respond`, which can
still say something useful. An assistant that throws into the request would turn
a bad LLM day into a broken chat feature.

`human_confirm` calls LangGraph's ``interrupt()``, which suspends the run until
the caller resumes it with ``Command(resume=...)``. The suspension itself lives
in the checkpointer and is therefore process-local (ADR-32); what survives a
restart is the `action_proposals` rows the node wrote before suspending, which
carry everything `execute` needs. The graph is the computation, the database is
the truth — the same division the Translation Agent draws.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.assistant.prompts import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_user_prompt,
)
from src.agents.assistant.state import AssistantState, PlannedStep
from src.services.agent_consent import ConsentRequiredError, require_consent

logger = logging.getLogger(__name__)

# Operations `route` knows how to dispatch. Anything else in a plan is dropped
# with a warning rather than followed: the planner is a language model, and a
# hallucinated operation name must not become an unhandled edge.
KNOWN_OPERATIONS = ("summarize", "extract_actions")

# How much recent conversation `load_memory` recalls. Wider than a translation's
# three-to-five lines because a summary is about a stretch of exchanges, and
# bounded because the whole transcript would not fit a prompt or a budget.
MEMORY_LIMIT = 30


def _note(state: AssistantState, **entries: Any) -> dict[str, Any]:
    """Shallow-merge into telemetry, which has no LangGraph reducer.

    Returning the dict bare would replace the whole thing and lose whatever
    earlier nodes recorded — the same trap `state["telemetry"]` has in the
    Translation Agent.
    """
    merged = dict(state.get("telemetry") or {})
    merged.update(entries)
    return merged


def make_check_consent(db: AsyncSession) -> Callable[[AssistantState], Awaitable[dict[str, Any]]]:
    """Build the node that refuses to start without the user's permission."""

    async def check_consent(state: AssistantState) -> dict[str, Any]:
        """Verify the caller granted `read_conversations` before anything reads.

        Answers inside the graph rather than raising. The caller asked the
        assistant a question and deserves a sentence back, not a 403 to
        translate — and the REST surface still refuses independently, because
        `ConversationIntelligenceService` checks the same scope itself.
        """
        try:
            await require_consent(db, state["user_id"], "read_conversations")
        except ConsentRequiredError as exc:
            return {"missing_consent": exc.scope, "telemetry": _note(state, consent="missing")}
        return {"missing_consent": None, "telemetry": _note(state, consent="granted")}

    return check_consent


def make_load_memory(
    db: AsyncSession,
    *,
    limit: int = MEMORY_LIMIT,
) -> Callable[[AssistantState], Awaitable[dict[str, Any]]]:
    """Build the node that recalls what the conversation has already said."""

    async def load_memory(state: AssistantState) -> dict[str, Any]:
        """Recall the conversation, by clock and by meaning.

        Two passes because they answer different questions. The time-ordered
        window is what "what did I miss" needs and is always right about
        recency. Semantic recall is what "what did we decide about the deadline"
        needs, and it reaches past the window into things said weeks ago that no
        limit would have included.

        Goes through `ChatService.get_message_history` for the first pass, which
        applies both the membership check and the visibility filter, so this
        node cannot become a second way into messages that skips either. The
        second pass carries the same visibility filter itself.

        Semantic recall is additive: it is skipped when the user has not granted
        `store_memory`, when nothing is embedded yet, or when the provider is
        down, and in each case the node still returns the recent window.
        """
        from src.services.agent_consent import has_consent
        from src.services.chat import ChatService
        from src.services.semantic_search import search_similar_messages

        try:
            messages = await ChatService(db).get_message_history(
                user_id=state["user_id"],
                conversation_id=state["conversation_id"],
                limit=limit,
            )
        except Exception as exc:
            logger.warning("Assistant memory load failed", exc_info=True)
            return {"memory": [], "error": str(exc), "telemetry": _note(state, memory_lines=0)}

        usable = [
            message
            for message in messages
            if message.deleted_at is None and message.original_text.strip()
        ]
        recent_ids = {message.id for message in usable}

        recalled: list[Any] = []
        if await has_consent(db, state["user_id"], "store_memory"):
            recalled = [
                message
                for message in await search_similar_messages(
                    db,
                    conversation_id=state["conversation_id"],
                    user_id=state["user_id"],
                    query_text=state.get("request_text", ""),
                )
                # A message already in the recent window would otherwise appear
                # twice in the transcript, which reads as it having been said
                # twice.
                if message.id not in recent_ids
            ]

        # Merged into one chronological block. The model is told this is the
        # conversation in order and nothing about which pass found which line;
        # how a line was retrieved is not something a summary should reason
        # about, the same rule `DatabaseContextProvider` follows.
        merged = sorted([*usable, *recalled], key=lambda row: (row.created_at, row.id))
        lines = [message.original_text for message in merged]
        return {
            "memory": lines,
            "telemetry": _note(
                state, memory_lines=len(lines), memory_recalled=len(recalled)
            ),
        }

    return load_memory


def make_plan(
    llm_factory: Callable[[], Any] | None = None,
) -> Callable[[AssistantState], Awaitable[dict[str, Any]]]:
    """Build the planning node.

    Args:
        llm_factory: Model source; defaults to the configured provider. Injected
            so tests decide what the planner returns without reaching a network.
    """

    async def plan(state: AssistantState) -> dict[str, Any]:
        """Choose which operations answer the request.

        A failure here is not fatal. The planner falls back to summarising,
        which is the operation that needs the least from the request and is
        almost always a defensible answer to "help me with this conversation".
        """
        from src.services.llm import extract_text, get_llm

        factory = llm_factory or get_llm
        prompt = build_planner_user_prompt(
            request_text=state.get("request_text", ""),
            has_memory=bool(state.get("memory")),
        )
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await factory().ainvoke(
                [SystemMessage(content=PLANNER_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            )
            steps = _parse_plan(extract_text(response))
        except Exception as exc:
            logger.warning("Assistant planning failed; defaulting to summarize", exc_info=True)
            return {
                "plan": [{"operation": "summarize", "reason": "planner unavailable"}],
                "error": str(exc),
                "telemetry": _note(state, planner="fallback"),
            }

        return {"plan": steps, "telemetry": _note(state, planner="ok", planned_steps=len(steps))}

    return plan


def _parse_plan(raw: str) -> list[PlannedStep]:
    """Read the planner's JSON, discarding anything this graph cannot dispatch.

    Unknown operation names are dropped rather than passed on. `route` matches
    by equality, so a hallucinated name would reach no executor and the run
    would finish looking successful with nothing done — the failure mode that
    is hardest to notice.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        logger.warning("Assistant planner returned unparseable JSON")
        return []

    steps: list[PlannedStep] = []
    for item in payload.get("steps", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        operation = item.get("operation")
        if operation in KNOWN_OPERATIONS:
            steps.append({"operation": operation, "reason": str(item.get("reason", ""))})
        else:
            logger.warning("Assistant planner proposed unknown operation %r", operation)
    return steps


def route_after_plan(state: AssistantState) -> str:
    """Send the run to the first executor its plan asks for.

    One operation per run: the two executors answer different questions, and
    chaining them would make `human_confirm` gate a summary nobody needs to
    approve. A request needing both is served by asking twice, which is also
    what the user experiences as two answers.
    """
    if state.get("missing_consent"):
        return "ask_permission"
    operations = [step["operation"] for step in state.get("plan", [])]
    if "extract_actions" in operations:
        return "extract_actions"
    if "summarize" in operations:
        return "summarize"
    return "respond"


def route_after_consent(state: AssistantState) -> str:
    """Stop before reading anything when the permission is not there."""
    return "ask_permission" if state.get("missing_consent") else "load_memory"


def route_after_extract(state: AssistantState) -> str:
    """Only pause for a human when there is something to approve."""
    return "human_confirm" if state.get("proposals") else "respond"


def make_summarize(db: AsyncSession) -> Callable[[AssistantState], Awaitable[dict[str, Any]]]:
    """Build the executor that condenses the conversation (B-03)."""

    async def summarize(state: AssistantState) -> dict[str, Any]:
        """Produce key points, decisions and open items for the caller."""
        from src.services.conversation_intelligence import ConversationIntelligenceService

        try:
            result = await ConversationIntelligenceService().summarize_conversation(
                conversation_id=state["conversation_id"],
                user_id=state["user_id"],
                db=db,
            )
        except Exception as exc:
            logger.warning("Assistant summarize failed", exc_info=True)
            return {"error": str(exc), "telemetry": _note(state, summarize="failed")}

        return {
            "summary": result.model_dump(mode="json"),
            "telemetry": _note(state, summarize="ok", summarized_messages=result.message_count),
        }

    return summarize


def make_extract_actions(db: AsyncSession) -> Callable[[AssistantState], Awaitable[dict[str, Any]]]:
    """Build the executor that proposes tasks and appointments (B-04)."""

    async def extract_actions(state: AssistantState) -> dict[str, Any]:
        """Turn the triggering message into proposals awaiting confirmation.

        Reuses `ConversationIntelligenceService` rather than reimplementing the
        extraction: that path already carries the idempotency key, the owner
        scoping and the server-side temporal resolution, and about thirty tests
        hold it in place.
        """
        from src.services.conversation_intelligence import ConversationIntelligenceService

        message_id = state.get("telemetry", {}).get("source_message_id")
        if not message_id:
            return {"proposals": [], "telemetry": _note(state, extract="no_source_message")}

        try:
            proposals = await ConversationIntelligenceService().extract_actions_from_message(
                conversation_id=state["conversation_id"],
                message_id=message_id,
                user_id=state["user_id"],
                db=db,
            )
        except Exception as exc:
            logger.warning("Assistant action extraction failed", exc_info=True)
            return {"proposals": [], "error": str(exc), "telemetry": _note(state, extract="failed")}

        return {
            "proposals": [item.model_dump(mode="json") for item in proposals],
            "telemetry": _note(state, extract="ok", proposal_count=len(proposals)),
        }

    return extract_actions


def human_confirm(state: AssistantState) -> dict[str, Any]:
    """Suspend the run until a person approves or rejects each proposal.

    This is the constraint the assignment calls mandatory and `NewFeature.md`
    §1.3 draws with no path around it: nothing reaches a calendar without a
    human saying so.

    The proposals are already persisted as `pending_confirmation` rows before
    this point, which is what makes the pause safe to lose. If the process
    restarts while suspended, the run is gone but the rows are not, and the
    confirmation endpoint executes from them directly (ADR-32).

    ``interrupt()`` raises internally to suspend, so the return statement below
    only runs on resume, carrying whatever the caller passed to
    ``Command(resume=...)``.
    """
    decision = interrupt(
        {
            "kind": "confirm_proposals",
            "proposals": state.get("proposals", []),
        }
    )
    approved = decision.get("approved_proposal_ids", []) if isinstance(decision, dict) else []
    return {"approved_proposal_ids": list(approved)}


def make_execute(db: AsyncSession) -> Callable[[AssistantState], Awaitable[dict[str, Any]]]:
    """Build the node that carries out what the human approved."""

    async def execute(state: AssistantState) -> dict[str, Any]:
        """Confirm each approved proposal, leaving the rest untouched.

        Silence is a decision: a proposal the human did not name stays
        `pending_confirmation` rather than being rejected, because not answering
        is not the same as saying no.
        """
        from src.services.action_proposals import (
            ActionProposalError,
            ActionProposalService,
        )

        service = ActionProposalService(db)
        executed: list[dict[str, Any]] = []
        for proposal_id in state.get("approved_proposal_ids", []):
            try:
                confirmed = await service.confirm_proposal(proposal_id, state["user_id"])
            except ActionProposalError as exc:
                # One proposal failing must not abandon the others: they are
                # separate promises the user made and approved separately.
                logger.warning("Confirming proposal %s failed: %s", proposal_id, exc)
                continue
            executed.append({"id": confirmed.id, "title": confirmed.title})

        return {"executed": executed, "telemetry": _note(state, executed_count=len(executed))}

    return execute


def ask_permission(state: AssistantState) -> dict[str, Any]:
    """Explain which permission is missing, in words rather than a status code."""
    scope = state.get("missing_consent") or "read_conversations"
    return {
        "reply": (
            "Mình cần bạn cho phép trước đã. Hãy bật quyền tương ứng trong phần "
            f"Cài đặt → Trợ lý ({scope}), rồi nhờ mình lại nhé."
        )
    }


def respond(state: AssistantState) -> dict[str, Any]:
    """Turn whatever the run produced into one message for the caller.

    Reached from every terminal path, including the failing ones, so that a run
    that went wrong still answers instead of returning nothing.
    """
    if state.get("reply"):
        return {}

    executed = state.get("executed") or []
    if executed:
        titles = ", ".join(item["title"] for item in executed)
        return {"reply": f"Đã thêm vào lịch của bạn: {titles}."}

    proposals = state.get("proposals") or []
    if proposals:
        return {
            "reply": (
                f"Mình tìm thấy {len(proposals)} việc cần làm trong hội thoại này. "
                "Bạn xem lại rồi duyệt giúp mình nhé."
            )
        }

    summary = state.get("summary")
    if summary and summary.get("summary"):
        return {"reply": summary["summary"]}

    if state.get("error"):
        return {
            "reply": (
                "Mình chưa xử lý được yêu cầu này ngay lúc này. "
                "Bạn thử lại, hoặc nói rõ hơn điều bạn muốn mình hỗ trợ."
            )
        }

    return {"reply": "Bạn muốn mình hỗ trợ điều gì trong cuộc trò chuyện này?"}


def build_assistant_graph(
    *,
    db: AsyncSession,
    checkpointer: Any,
    llm_factory: Callable[[], Any] | None = None,
) -> Any:
    """Compile the assistant graph with its dependencies bound.

    Built per request rather than once at import, because every node needs the
    caller's database session. The Translation Agent's module-level ``agent`` is
    the exception there, not the rule — its own docstring says the chat service
    should build its own graph with a real provider.

    Args:
        db: Session the nodes read and write through.
        checkpointer: Required. ``interrupt()`` cannot suspend without one, so a
            graph compiled without it would run `human_confirm` straight through
            and approve nothing while looking like it worked.
        llm_factory: Model source for the planner; defaults to the configured
            provider.

    Returns:
        The compiled graph, ready for ``ainvoke`` with a thread id in its config.
    """
    graph = StateGraph(AssistantState)

    graph.add_node("check_consent", make_check_consent(db))
    graph.add_node("load_memory", make_load_memory(db))
    graph.add_node("plan", make_plan(llm_factory))
    graph.add_node("summarize", make_summarize(db))
    graph.add_node("extract_actions", make_extract_actions(db))
    graph.add_node("human_confirm", human_confirm)
    graph.add_node("execute", make_execute(db))
    graph.add_node("ask_permission", ask_permission)
    graph.add_node("respond", respond)

    graph.add_edge(START, "check_consent")
    # Path maps on every conditional edge, for the reason the Translation Agent
    # states: without them the compiled graph shows these nodes as terminal, and
    # compile() cannot check a router's return values against real node names.
    graph.add_conditional_edges(
        "check_consent",
        route_after_consent,
        {"ask_permission": "ask_permission", "load_memory": "load_memory"},
    )
    graph.add_edge("load_memory", "plan")
    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "extract_actions": "extract_actions",
            "summarize": "summarize",
            "respond": "respond",
            "ask_permission": "ask_permission",
        },
    )
    graph.add_edge("summarize", "respond")
    graph.add_conditional_edges(
        "extract_actions",
        route_after_extract,
        {"human_confirm": "human_confirm", "respond": "respond"},
    )
    graph.add_edge("human_confirm", "execute")
    graph.add_edge("execute", "respond")
    graph.add_edge("ask_permission", END)
    graph.add_edge("respond", END)

    return graph.compile(checkpointer=checkpointer)
