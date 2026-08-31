"""The closed set of things the Assistant Agent is able to do (ADR-40).

A registry rather than `bind_tools`, and the difference is not stylistic. With
function-calling the set of possible actions is whatever the model decides to
emit, so the human gate has to be enforced somewhere downstream and every new
provider is a chance for it to be enforced differently. Here the set is a dict
in code: a plan naming something outside it reaches nothing, and `writes` is a
property of the registration rather than of the model's mood. That is the same
reasoning ADR-05 gives for the translation agent being a state machine instead of
a ReAct loop, and ADR-32 depends on it — the gate can only be mandatory if the
list of things that need gating is fixed.

Three fields carry the safety properties:

- **`consent_scope`** — checked *before* the tool runs, not after. A tool whose
  scope the user has not granted is not offered to the planner at all, so the
  model never proposes an action that will be refused and never has to be told
  why.
- **`writes`** — true for anything that changes something the user would notice
  outside this conversation. Those route through `human_confirm` without
  exception; the planner cannot opt out, because it never sees the flag.
- **`schema`** — arguments are parsed before the call. Every field is somewhere
  a language model can be wrong, and `extra="forbid"` turns an invented
  parameter into a caught error rather than a silently dropped instruction.

Every tool wraps a service that already exists. None of them reimplement logic:
`ActionProposalService` carries the idempotency key and the owner policy,
`CalendarService` carries the reminder defaults and the Google push, and about
thirty tests hold each of those in place.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.assistant_tools import (
    ExtractActionsArguments,
    ListCalendarEventsArguments,
    ListPeopleArguments,
    ProposeCalendarEventArguments,
    RecallUserMemoryArguments,
    SaveUserMemoryArguments,
    SearchOldMessagesArguments,
    SummarizeConversationArguments,
)
from src.services.assistant_scope import PERSONAL_THREAD_TITLE, AssistantScope

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One thing the assistant can do, and the rules attached to it."""

    name: str
    # Written for the planner, which reads it in the prompt. Says when to reach
    # for this rather than what it does internally — the planner's failure mode
    # is picking a reasonable-looking wrong tool, not misunderstanding an
    # implementation.
    description: str
    schema: type[BaseModel]
    # Permission required before this runs. None means the tool touches nothing
    # the user has to agree to.
    consent_scope: str | None
    # Produces `action_proposals` rows rather than acting. Everything the
    # assistant can change about a person's calendar goes through that one
    # gate, so this flag is what tells the graph a run must stop and ask
    # before anything becomes real. The planner never sees it: it is not a
    # suggestion it gets to weigh.
    produces_proposals: bool
    run: Callable[..., Awaitable[Any]]


class ToolError(RuntimeError):
    """A tool could not run. Carries a sentence the reply can show."""


class UnknownToolError(ToolError):
    """The plan named something the registry does not contain."""


class ToolArgumentError(ToolError):
    """The planner's arguments did not fit the tool's schema."""


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What one tool call produced, and enough about it to plan the next step."""

    tool: str
    ok: bool
    # Rendered into the observation the planner reads before replanning. Text
    # rather than the raw object: the planner is a language model, and handing
    # it an ORM row teaches it to expect fields that are not part of any
    # contract.
    summary: str
    data: Any = None


def build_registry(
    db: AsyncSession,
    *,
    scope: AssistantScope,
) -> dict[str, ToolSpec]:
    """Bind every tool to one session, scope and account.

    Bound rather than passed per call, and that is a safety property rather than
    convenience: the account and the conversations it may read are closed over
    here from the authenticated request, so no argument schema exposes them and
    no plan the model produces can name a different person's calendar or a
    thread outside the scope. The planner decides *what* to do; it never decides
    *whose*, and it never decides *how widely*.

    The scope itself comes from where the request arrived -- the private
    assistant thread reads the whole account, a mention inside a conversation
    reads that conversation -- and is resolved by `scope_for`, not from anything
    the person wrote. A question that could widen its own reach would make the
    rule decorative.
    """
    user_id = scope.user_id
    conversation_id = scope.origin_conversation_id

    async def search_old_messages(*, query: str, top_n: int = 4) -> ToolResult:
        from src.config import get_settings
        from src.services.assistant_retrieval import RetrievalConfig, retrieve

        settings = get_settings()
        # Every conversation in scope, which in the private thread is all of
        # them. A person asking their own assistant "what did we decide about
        # the deadline" does not know or care which thread it was decided in,
        # and answering only from the thread they are standing in -- one that
        # contains nothing but their questions -- is how it came to answer
        # "nothing was said" about things that were said at length elsewhere.
        chunks = await retrieve(
            db,
            conversation_ids=await scope.conversation_ids(db),
            query_text=query,
            config=RetrievalConfig(
                top_k=settings.assistant_retrieval_top_k, top_n=top_n
            ),
        )
        if not chunks:
            # An explicit empty result rather than silence. The planner has to be
            # able to tell "the conversation does not say" from "the tool did not
            # run", because the first is an answer and the second is a retry.
            return ToolResult(
                tool="search_old_messages",
                ok=True,
                summary="Nothing in the conversations I can read matches that.",
                data=[],
            )
        return ToolResult(
            tool="search_old_messages",
            ok=True,
            summary="\n\n".join(chunk.text for chunk in chunks),
            data=[
                {
                    "chunk_id": chunk.chunk_id,
                    # Which thread the hit came from. With several in scope the
                    # answer has to be able to say where something was said,
                    # and the planner has to be able to tell two threads apart.
                    "conversation_id": chunk.conversation_id,
                    "message_ids": list(chunk.message_ids),
                }
                for chunk in chunks
            ],
        )

    async def summarize_conversation(
        *, message_limit: int = 200, target_language: str | None = None
    ) -> ToolResult:
        from src.services.conversation_intelligence import (
            ConversationIntelligenceService,
        )

        summary = await ConversationIntelligenceService().summarize_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            db=db,
            message_limit=message_limit,
            target_language=target_language,
        )
        return ToolResult(
            tool="summarize_conversation",
            ok=True,
            summary=summary.summary or "The conversation has nothing to summarise.",
            data=summary.model_dump(mode="json"),
        )

    async def extract_actions(*, source_message_id: str = "") -> ToolResult:
        from src.services.conversation_intelligence import (
            ConversationIntelligenceService,
        )

        if not source_message_id:
            return ToolResult(
                tool="extract_actions",
                ok=False,
                summary="There is no message to extract actions from.",
                data=[],
            )
        proposals = await ConversationIntelligenceService().extract_actions_from_message(
            conversation_id=conversation_id,
            message_id=source_message_id,
            user_id=user_id,
            db=db,
        )
        return ToolResult(
            tool="extract_actions",
            ok=True,
            summary=f"{len(proposals)} proposal(s) awaiting confirmation.",
            data=[proposal.model_dump(mode="json") for proposal in proposals],
        )

    async def list_calendar_events(
        *, starts_after=None, starts_before=None
    ) -> ToolResult:
        from src.services.calendar import CalendarService

        events = await CalendarService(db).list_events(
            user_id=user_id,
            starts_after=starts_after,
            starts_before=starts_before,
        )
        return ToolResult(
            tool="list_calendar_events",
            ok=True,
            summary="\n".join(
                f"{event.starts_at.isoformat()} — {event.title}" for event in events
            )
            or "Nothing on the calendar in that window.",
            data=[
                {"id": event.id, "title": event.title, "starts_at": event.starts_at.isoformat()}
                for event in events
            ],
        )

    async def propose_calendar_event(
        *,
        title: str,
        starts_at,
        ends_at=None,
        details: str | None = None,
        location: str | None = None,
        source_message_id: str = "",
    ) -> ToolResult:
        from src.schemas.intelligence import ActionCandidateDTO
        from src.services.action_proposals import ActionProposalService

        if not source_message_id:
            return ToolResult(
                tool="propose_calendar_event",
                ok=False,
                summary="There is no message to attach this proposal to.",
                data=[],
            )

        # A proposal, never a calendar entry. Everything the assistant wants to
        # put on a calendar goes through `action_proposals` and the same gate a
        # detected commitment goes through — one approval path rather than two.
        # That is what ADR-34 means by an approved proposal being the thing a
        # calendar entry comes from, and it is what makes the pause survivable:
        # the row exists before `interrupt()` suspends, so a restart loses the
        # suspension and not the proposal (ADR-32).
        #
        # It is also what lets the person approving *annotate* — correct the
        # title or time, and say how far ahead they want to be nudged. A direct
        # write has nothing to annotate: by the time they see it, it happened.
        proposals = await ActionProposalService(db).create_proposals_from_candidates(
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            candidates=[
                ActionCandidateDTO(
                    action_type="appointment",
                    title=title,
                    details=details,
                    location=location,
                    scheduled_time=starts_at,
                    # The planner proposed this rather than reading it out of a
                    # message, so it is not stated fact. Below the confidence of
                    # an extracted commitment on purpose.
                    confidence_score=0.6,
                )
            ],
            owner_user_id=user_id,
            source_mode="on_demand",
            created_by_user_id=user_id,
        )
        return ToolResult(
            tool="propose_calendar_event",
            ok=True,
            summary=f"Proposed “{title}” for your approval.",
            data=[
                {"id": proposal.id, "title": proposal.title} for proposal in proposals
            ],
        )

    async def list_people() -> ToolResult:
        """Who is in the conversations this request may read.

        In the private thread that is every conversation the account belongs to,
        with the members of each; from inside a conversation it is that
        conversation alone. Without this the assistant could search what was
        said but could not say who said it or who else was there, so a question
        as ordinary as "ai trong nhóm dự án" had no path to an answer.

        Names only. No email address, no account id the person could not already
        read off the member list in the interface: this widens what the
        assistant can say, not what the reader is entitled to.

        No arguments at all. It had one -- a conversation id to narrow to -- and
        the planner filled it in with an id it had no way to know, which
        filtered every conversation away and produced "no conversation in
        scope". The person was then told the assistant could not see their
        conversations, which was false and came from an argument that existed
        only to be got wrong. The scope already says what may be read; there is
        nothing here for a model to decide.
        """
        from sqlalchemy import select as _select

        from src.database.models import Conversation as _Conversation
        from src.database.models import ConversationMember as _Member
        from src.database.models import User as _User

        allowed = await scope.conversation_ids(db)
        if not allowed:
            return ToolResult(
                tool="list_people",
                ok=True,
                summary="No conversation in scope.",
                data=[],
            )

        rows = (
            await db.execute(
                _select(
                    _Member.conversation_id,
                    _Conversation.type,
                    _Conversation.title,
                    _User.display_name,
                    _User.username,
                    _User.email,
                )
                .join(_Conversation, _Conversation.id == _Member.conversation_id)
                .join(_User, _User.id == _Member.user_id)
                .where(_Member.conversation_id.in_(allowed))
            )
        ).all()

        grouped: dict[str, dict[str, object]] = {}
        for cid, kind, title, display_name, username, email in rows:
            if title == PERSONAL_THREAD_TITLE:
                # The person's own thread with the assistant. Listing them as
                # the sole member of it is noise in every answer.
                continue
            entry = grouped.setdefault(
                cid, {"conversation_id": cid, "type": kind, "title": title, "members": []}
            )
            # The same fallback the summariser uses for a speaker label. An
            # account can have neither a display name nor a username -- the two
            # seeded developer accounts have neither -- and "Unknown, Unknown"
            # is worse than useless: it reads as the assistant not being allowed
            # to see, which is what it then tells the person.
            name = display_name or username or (email or "").split("@")[0] or "Unknown"
            members = entry["members"]
            assert isinstance(members, list)
            members.append(name)

        # Written as sentences rather than as `direct: A, B`. The answering
        # stage reads this summary and nothing else about the call, and a
        # cryptic line gets treated as data it does not understand well enough
        # to use -- which reaches the person as "I cannot see your
        # conversations", the one thing that is not true here.
        lines = []
        for entry in grouped.values():
            members = ", ".join(sorted(entry["members"]))
            title = entry["title"]
            lines.append(
                f'Group "{title}" - members: {members}'
                if title
                else f"Direct conversation - members: {members}"
            )
        header = (
            "The conversations this person belongs to, and who is in each:"
            if lines
            else "This person shares no conversation with anybody else."
        )
        return ToolResult(
            tool="list_people",
            ok=True,
            summary="\n".join([header, *lines]),
            data=list(grouped.values()),
        )

    async def recall_user_memory(*, query: str, top_n: int = 3) -> ToolResult:
        from src.services.assistant_memory import recall

        facts = await recall(db, user_id=user_id, query_text=query, top_n=top_n)
        return ToolResult(
            tool="recall_user_memory",
            ok=True,
            summary="\n".join(f"- {fact.content}" for fact in facts)
            or "Nothing is known about that yet.",
            data=[{"id": fact.id, "kind": fact.kind, "content": fact.content} for fact in facts],
        )

    async def save_user_memory(
        *, kind: str, content: str, confidence: float = 0.5
    ) -> ToolResult:
        from src.services.assistant_memory import remember

        fact = await remember(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            kind=kind,
            content=content,
            confidence=confidence,
        )
        return ToolResult(
            tool="save_user_memory",
            ok=True,
            summary=f"Noted: {content}",
            data={"id": fact.id},
        )

    specs = (
        ToolSpec(
            name="search_old_messages",
            description=(
                "Search earlier messages by meaning. In the person's own "
                "assistant chat this reaches every conversation they belong "
                "to; inside a conversation it reaches only that one. Use it "
                "whenever the answer might have been said before the recent "
                "messages, which is most questions beginning 'what did we'."
            ),
            schema=SearchOldMessagesArguments,
            consent_scope="read_conversations",
            produces_proposals=False,
            run=search_old_messages,
        ),
        ToolSpec(
            name="list_people",
            description=(
                "List the conversations in reach and who is in each of them. "
                "In the person's own assistant chat that is all their "
                "conversations; inside a conversation it is only that one. Use "
                "it for 'who is in the group', or before naming somebody."
            ),
            schema=ListPeopleArguments,
            consent_scope="read_conversations",
            produces_proposals=False,
            run=list_people,
        ),
        ToolSpec(
            name="summarize_conversation",
            description=(
                "Condense the conversation into key points, decisions and open "
                "items. Use it for 'what did I miss', not to answer one "
                "specific question — searching is cheaper and more precise."
            ),
            schema=SummarizeConversationArguments,
            consent_scope="read_conversations",
            produces_proposals=False,
            run=summarize_conversation,
        ),
        ToolSpec(
            name="extract_actions",
            description=(
                "Find tasks and appointments in the message that triggered this "
                "request and propose them for confirmation."
            ),
            schema=ExtractActionsArguments,
            consent_scope="read_conversations",
            # Writes `action_proposals` rows, so it goes through the gate. The
            # rows are pending by construction, but a proposal the user never
            # asked for still appears in their task box.
            produces_proposals=True,
            run=extract_actions,
        ),
        ToolSpec(
            name="list_calendar_events",
            description=(
                "Read what is already on the person's calendar. Always call this "
                "before proposing a new entry, so a clash is noticed first."
            ),
            schema=ListCalendarEventsArguments,
            consent_scope="calendar_read",
            produces_proposals=False,
            run=list_calendar_events,
        ),
        ToolSpec(
            name="propose_calendar_event",
            description=(
                "Propose a calendar entry for the person to approve. It does "
                "not go on the calendar until they say so, and they can correct "
                "the time, its timezone, and how far ahead to be reminded when "
                "they do. Give an absolute start time; if the time was said as "
                "'tomorrow morning' and no timezone is known, ask instead of "
                "guessing."
            ),
            schema=ProposeCalendarEventArguments,
            consent_scope="calendar_write",
            produces_proposals=True,
            run=propose_calendar_event,
        ),
        ToolSpec(
            name="recall_user_memory",
            description=(
                "Look up durable facts about this person — how far ahead they "
                "like to be reminded, what they own, what recurs."
            ),
            schema=RecallUserMemoryArguments,
            consent_scope="store_memory",
            produces_proposals=False,
            run=recall_user_memory,
        ),
        ToolSpec(
            name="save_user_memory",
            description=(
                "Record one durable fact about this person. Not for anything "
                "specific to this conversation, which the transcript already "
                "holds."
            ),
            schema=SaveUserMemoryArguments,
            consent_scope="store_memory",
            # Writes, but changes nothing the user sees outside the assistant and
            # nothing anyone else can observe, so it does not earn a confirmation
            # dialogue. Gating it would put a prompt in front of the person every
            # time the assistant noticed a preference, which is how a gate stops
            # being read.
            produces_proposals=False,
            run=save_user_memory,
        ),
    )
    return {spec.name: spec for spec in specs}


async def available_tools(
    db: AsyncSession, *, user_id: str, registry: dict[str, ToolSpec]
) -> dict[str, ToolSpec]:
    """The subset of tools this person has granted the permission for.

    Filtered before planning rather than checked after. A planner shown a tool it
    is not allowed to use will propose it, the run will refuse, and the person
    gets an apology instead of an answer — while a planner shown only what it may
    do plans around the restriction on its own.

    This does not replace the check inside each service. Those stay: this is
    about what the model is offered, and a permission can be revoked between the
    plan and the call.

    One query, not one per tool. `has_consent` in a loop issued seven round
    trips for a question with a single answer, on a path that runs again on
    every replan — and it held the session open across all of them, which in the
    test suite was long enough for a schema teardown to deadlock against a
    background task still inside that read. `get_consents` returns the whole
    vocabulary in one statement, including the scopes with no row, so nothing is
    lost by asking once.
    """
    from src.services.agent_consent import get_consents

    granted_scopes = {
        consent.scope for consent in await get_consents(db, user_id) if consent.is_granted
    }
    return {
        name: spec
        for name, spec in registry.items()
        if spec.consent_scope is None or spec.consent_scope in granted_scopes
    }


def parse_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate one call's arguments against the tool's schema.

    Raises:
        ToolArgumentError: the arguments do not fit. The message names the
            fields, because it is fed back to the planner as an observation and
            a replan can only fix what it is told.
    """
    try:
        return spec.schema.model_validate(arguments or {}).model_dump(exclude_none=True)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'arguments'}: {error['msg']}"
            for error in exc.errors()
        )
        raise ToolArgumentError(f"{spec.name} rejected its arguments — {problems}") from exc


async def call_tool(
    spec: ToolSpec, arguments: dict[str, Any], **bound: Any
) -> ToolResult:
    """Run one tool, turning any failure into a result rather than an exception.

    The assistant graph's hard rule is that no node raises (ADR-32), and a tool
    is the most likely thing in it to fail — a provider is down, a calendar entry
    was deleted between the plan and the call. A failed tool has to become an
    observation the planner can act on, not an exception that ends the run: with
    the failure in hand it can try a different tool or tell the person what did
    not work, and both are better than silence.
    """
    try:
        parsed = parse_arguments(spec, arguments)
    except ToolArgumentError as exc:
        return ToolResult(tool=spec.name, ok=False, summary=str(exc))

    try:
        return await spec.run(**parsed, **bound)
    except Exception as exc:  # noqa: BLE001 - see docstring
        logger.warning("Assistant tool %s failed", spec.name, exc_info=True)
        return ToolResult(
            tool=spec.name,
            ok=False,
            summary=f"{spec.name} failed: {type(exc).__name__}: {exc}",
        )


def render_catalogue(registry: dict[str, ToolSpec]) -> str:
    """Render the offered tools for the planner prompt.

    Includes each tool's argument names and which are required, because a
    planner that has to guess the shape guesses wrong and the call is rejected —
    a round trip spent on something the prompt could have said outright.
    """
    lines: list[str] = []
    for name, spec in sorted(registry.items()):
        fields = spec.schema.model_fields
        rendered = ", ".join(
            f"{field}{'' if info.is_required() else '?'}"
            for field, info in fields.items()
        )
        lines.append(f'- "{name}"({rendered}): {spec.description}')
    return "\n".join(lines)
