"""The state the Assistant Agent carries between its nodes.

Separate from the Translation Agent's ``AgentState`` on purpose. The two agents
share infrastructure and nothing else: this one is invoked on request rather
than on every message, it may take seconds rather than milliseconds, and it
produces rows a human then approves instead of text delivered immediately.
Merging the two states would make every translation carry fields it can never
use, and every change to one agent a reason to re-read the other.

None of these keys are part of `docs/CONTRACT.md`. What the client sees is the
`ActionProposalResponse` rows and the reply text, both of which have their own
schemas; the shape in here is free to change without a contract amendment, for
the same reason ADR-16 gives for `telemetry`.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# What the planner is allowed to ask for. A closed set rather than free text
# because `route` dispatches on it by equality: a plan naming a step this list
# does not contain would silently reach no executor at all, and the run would
# end looking successful with nothing done.
PlannedOperation = Literal["summarize", "extract_actions"]


class PlannedStep(TypedDict):
    """One operation the planner chose, and why."""

    operation: PlannedOperation
    reason: str


class AssistantState(TypedDict, total=False):
    """Everything the assistant graph reads or writes for one request.

    ``total=False`` because most keys are produced partway through: a run that
    stops at `ask_permission` never has a plan, and one that only summarises
    never has proposals.
    """

    # --- Supplied by the caller ---
    conversation_id: str
    user_id: str
    request_text: str
    # IANA name from the client. Needed before a relative time like "sáng mai"
    # can be resolved at all, and never guessed: `normalize_action_time` refuses
    # rather than inventing an offset.
    timezone: str | None

    # --- Produced by the nodes ---
    # Set when `check_consent` stops the run; names the scope the user must
    # grant. The flow stays inside the graph rather than raising, so the caller
    # gets a sentence to show instead of an exception to translate.
    missing_consent: str | None
    memory: list[str]
    plan: list[PlannedStep]
    summary: dict[str, Any] | None
    proposals: list[dict[str, Any]]
    # Proposal ids the human approved, handed back in through `Command(resume=)`.
    approved_proposal_ids: list[str]
    executed: list[dict[str, Any]]
    reply: str

    # --- Diagnostics ---
    # Same rule the Translation Agent follows: a node records the failure here
    # and the flow continues to a node that can still answer. Nothing in this
    # graph may raise into the caller's request.
    error: str | None
    telemetry: dict[str, Any]
