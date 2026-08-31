"""Shared service utilities for Conversation Intelligence operations (B-09)."""

from __future__ import annotations

from typing import Any, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from src.agents.conversation_intelligence.observability import build_runnable_config
from src.agents.conversation_intelligence.parsing import invoke_with_repair
from src.config import Settings, get_settings
from src.schemas.intelligence import ActionProposalResponse
from src.services.agent_consent import has_consent, require_consent
from src.services.llm import get_intelligence_llm

T = TypeVar("T", bound=BaseModel)


class ConversationIntelligenceService:
    """Base service for invoking intelligence operations safely with timeouts and structured output."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_model(self, provider: str | None = None) -> Any:
        """Get configured ChatModel instance."""
        return get_intelligence_llm(settings=self.settings, provider=provider)

    async def invoke_structured(
        self,
        messages: list[BaseMessage],
        schema: type[T],
        operation: str = "intelligence_operation",
        timeout: float | None = None,
        conversation_id: str | None = None,
        message_id: str | None = None,
        provider: str | None = None,
        **metadata: Any,
    ) -> T:
        """Safely invoke LLM for structured output with bounded timeout and repair retry."""
        llm = self.get_model(provider=provider)
        eff_timeout = timeout if timeout is not None else float(self.settings.llm_timeout_seconds)
        eff_provider = provider or self.settings.llm_provider
        eff_model = self.settings.llm_model

        runnable_config = build_runnable_config(
            operation=operation,
            conversation_id=conversation_id,
            message_id=message_id,
            **metadata,
        )

        return await invoke_with_repair(
            llm=llm,
            messages=messages,
            schema=schema,
            operation=operation,
            timeout=eff_timeout,
            provider=eff_provider,
            model=eff_model,
            conversation_id=conversation_id,
            message_id=message_id,
            runnable_config=runnable_config,
        )

    async def summarize_conversation(
        self,
        conversation_id: str,
        user_id: str,
        db: Any,
        message_limit: int = 200,
        target_language: str | None = None,
    ) -> Any:
        """Fetch authorized messages and generate grounded conversation summary (B-03)."""
        from sqlalchemy import select

        from src.agents.conversation_intelligence.summary import (
            format_transcript_line,
            generate_long_conversation_summary,
        )
        from src.database.models import User
        from src.schemas.intelligence import ConversationSummaryResponse
        from src.services.chat import ChatService

        # Before membership, not after: this asks about the caller's own account
        # and involves no conversation data, so checking it first costs a single
        # indexed lookup and avoids reading messages the user never agreed to
        # let a model see.
        await require_consent(db, user_id, "read_conversations")

        chat_service = ChatService(db)
        # 1. Membership & existence authorization + message history retrieval
        messages = await chat_service.get_message_history(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=message_limit,
        )

        # 2. Determine target language
        user = await db.get(User, user_id)
        eff_target_lang = target_language or (user.preferred_language if user else "vi")

        # 3. Filter out deleted messages (soft-deleted rows keep row but have deleted_at set / blank text)
        usable_messages = [
            m for m in messages
            if m.deleted_at is None and m.original_text and m.original_text.strip()
        ]

        if not usable_messages:
            return ConversationSummaryResponse(
                summary="",
                key_points=[],
                decisions=[],
                open_items=[],
                message_count=0,
                target_language=eff_target_lang,
                window_start_at=None,
                window_end_at=None,
            )

        # 4. Resolve sender display names
        sender_ids = list({m.sender_id for m in usable_messages})
        users_res = await db.execute(select(User).where(User.id.in_(sender_ids)))
        user_map = {
            u.id: (u.display_name or u.username or u.email.split("@")[0])
            for u in users_res.scalars().all()
        }

        # 5. Format transcript (chronological order)
        transcript_lines = [
            format_transcript_line(
                created_at_str=m.created_at.isoformat() if m.created_at else "",
                speaker_name=user_map.get(m.sender_id, "User"),
                text=m.original_text,
            )
            for m in usable_messages
        ]
        # 6. Generate summary
        #
        # Lines rather than a joined transcript: above LONG_CONVERSATION_THRESHOLD
        # this splits into batches, and the batch boundaries have to fall between
        # messages. Cutting a joined string by length would hand one batch a
        # fragment whose speaker and timestamp are in the previous batch. Below
        # the threshold it joins them again and takes the single-pass path, so
        # there is one entry point rather than a choice the caller has to make.
        return await generate_long_conversation_summary(
            transcript_lines=transcript_lines,
            target_language=eff_target_lang,
            message_count=len(usable_messages),
            window_start_at=usable_messages[0].created_at,
            window_end_at=usable_messages[-1].created_at,
            conversation_id=conversation_id,
            settings=self.settings,
        )

    async def extract_actions_from_message(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        db: Any,
    ) -> list[Any]:
        """Extract candidate actions from a specific message and persist as ActionProposals (B-04)."""
        from sqlalchemy import select

        from src.agents.conversation_intelligence.action_graph import extract_action_candidates
        from src.database.models import Conversation, ConversationMember, Message, User
        from src.schemas.intelligence import ActionProposalResponse
        from src.services.action_proposals import ActionProposalService
        from src.services.chat import (
            ConversationMembershipError,
            ConversationNotFoundError,
            MessageNotFoundError,
        )

        await require_consent(db, user_id, "read_conversations")

        # 1. Verify conversation existence and caller membership
        conv = await db.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFoundError(conversation_id)

        member_stmt = select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        if (await db.execute(member_stmt)).scalar_one_or_none() is None:
            raise ConversationMembershipError(conversation_id, user_id)

        # 2. Fetch message
        msg = await db.get(Message, message_id)
        if msg is None or msg.conversation_id != conversation_id:
            raise MessageNotFoundError(message_id)

        # If message was withdrawn/deleted or has blank text, return empty
        if msg.deleted_at is not None or not msg.original_text or not msg.original_text.strip():
            return []

        # 3. Retrieve conversation members for attribution context
        members_stmt = (
            select(User)
            .join(ConversationMember, ConversationMember.user_id == User.id)
            .where(ConversationMember.conversation_id == conversation_id)
        )
        members_res = await db.execute(members_stmt)
        members_list = [
            {
                "id": u.id,
                "name": u.display_name or u.username or u.email.split("@")[0],
                "username": u.username or "",
            }
            for u in members_res.scalars().all()
        ]

        sender_user = await db.get(User, msg.sender_id)
        sender_name = (
            sender_user.display_name or sender_user.username or sender_user.email.split("@")[0]
            if sender_user else "User"
        )

        # 4. Extract action candidates via LLM
        candidates = await extract_action_candidates(
            message_text=msg.original_text,
            sender_id=msg.sender_id,
            sender_name=sender_name,
            members=members_list,
            reference_timestamp=msg.created_at,
            conversation_id=conversation_id,
            message_id=message_id,
            settings=self.settings,
        )

        if not candidates:
            return []

        requester = next((member for member in members_list if member["id"] == user_id), None)
        if requester is None:
            return []
        eligible = [
            candidate
            for candidate in candidates
            if self._candidate_belongs_to_requester(
                message_text=msg.original_text,
                sender_id=msg.sender_id,
                requester_id=user_id,
                requester=requester,
                candidate=candidate,
            )
        ]
        if not eligible:
            return []

        # 5. Persist proposals idempotently
        prop_service = ActionProposalService(db)
        proposals = await prop_service.create_proposals_from_candidates(
            conversation_id=conversation_id,
            source_message_id=message_id,
            candidates=eligible,
            owner_user_id=user_id,
            source_mode="on_demand",
            created_by_user_id=user_id,
        )

        return [ActionProposalResponse.model_validate(p) for p in proposals]

    @staticmethod
    def _candidate_belongs_to_requester(
        *,
        message_text: str,
        sender_id: str,
        requester_id: str,
        requester: dict[str, str],
        candidate: Any,
    ) -> bool:
        """Conservative server-side B-04 eligibility, independent of model IDs."""
        import re

        text = message_text.casefold()
        sender_self_commitment = bool(
            re.search(r"\b(?:i(?:'ll| will| am going to)|i commit to)\b", text)
            or re.search(r"(?:tôi|mình|em|anh)\s+sẽ", text)
        )
        if sender_id != requester_id and sender_self_commitment:
            return False

        aliases = {requester.get("username", "").casefold(), requester.get("name", "").casefold()}
        aliases.update(alias.split()[0] for alias in list(aliases) if alias)
        requester_named = any(alias and re.search(rf"\b{re.escape(alias)}\b", text) for alias in aliases)
        assignment = bool(re.search(r"\b(?:please|can you|could you|need you to|nhờ)\b", text))
        relationship = getattr(candidate, "relationship", "other_or_unknown")
        if sender_id == requester_id:
            return sender_self_commitment or relationship in {
                "requester_self_commitment",
                "requester_appointment",
            }
        if requester_named and assignment:
            return True
        return bool(
            candidate.action_type == "appointment"
            and requester_named
            and relationship == "requester_appointment"
        )

    async def analyze_ambiguity_and_clarification(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        db: Any,
    ) -> Any:
        """Analyze message for execution-relevant ambiguity and suggest clarification (B-08)."""
        from sqlalchemy import select

        from src.agents.conversation_intelligence.clarification import analyze_message_ambiguity
        from src.database.models import Conversation, ConversationMember, Message, User
        from src.schemas.intelligence import ClarificationAnalysisResponse
        from src.services.chat import (
            ConversationMembershipError,
            ConversationNotFoundError,
            MessageNotFoundError,
        )

        await require_consent(db, user_id, "read_conversations")

        # 1. Verify conversation existence and caller membership
        conv = await db.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFoundError(conversation_id)

        member_stmt = select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        if (await db.execute(member_stmt)).scalar_one_or_none() is None:
            raise ConversationMembershipError(conversation_id, user_id)

        # 2. Fetch message
        msg = await db.get(Message, message_id)
        if msg is None or msg.conversation_id != conversation_id:
            raise MessageNotFoundError(message_id)

        if msg.deleted_at is not None or not msg.original_text or not msg.original_text.strip():
            return ClarificationAnalysisResponse(
                is_ambiguous=False,
                needs_clarification=False,
                reason="Message is empty or was deleted",
                suggested_clarification_prompt=None,
            )

        # 3. Resolve sender display name
        sender_user = await db.get(User, msg.sender_id)
        sender_name = (
            sender_user.display_name or sender_user.username or sender_user.email.split("@")[0]
            if sender_user else "User"
        )

        # 4. Invoke clarification analysis
        return await analyze_message_ambiguity(
            message_text=msg.original_text,
            sender_name=sender_name,
            reference_timestamp=msg.created_at,
            conversation_id=conversation_id,
            message_id=message_id,
            settings=self.settings,
        )

    async def detect_self_commitments_from_message(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        db: Any,
    ) -> list[ActionProposalResponse]:
        """Detect proactive self-commitments from message and create ActionProposals (B-10)."""
        from sqlalchemy import select

        from src.agents.conversation_intelligence.self_commitment import detect_self_commitments
        from src.database.models import (
            ActionProposal,
            Conversation,
            ConversationMember,
            Message,
            User,
        )
        from src.services.action_proposals import ActionProposalService
        from src.services.chat import (
            ConversationMembershipError,
            ConversationNotFoundError,
            MessageNotFoundError,
        )

        # Only `read_conversations` here. This method serves both the manual
        # endpoint and the background scanner, and a request the user typed is
        # not proactive — the extra `proactive_scan` check belongs to the
        # scanner, in `commitment_detection.py`.
        await require_consent(db, user_id, "read_conversations")

        # 1. Verify conversation and caller membership
        conv = await db.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFoundError(conversation_id)

        member_stmt = select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        if (await db.execute(member_stmt)).scalar_one_or_none() is None:
            raise ConversationMembershipError(conversation_id, user_id)

        # 2. Fetch message
        msg = await db.get(Message, message_id)
        if msg is None or msg.conversation_id != conversation_id:
            raise MessageNotFoundError(message_id)
        if msg.sender_id != user_id:
            raise ConversationMembershipError(conversation_id, user_id)

        if msg.deleted_at is not None or not msg.original_text or not msg.original_text.strip():
            return []

        # 3. Resolve sender display name
        sender_user = await db.get(User, msg.sender_id)
        sender_name = (
            sender_user.display_name or sender_user.username or sender_user.email.split("@")[0]
            if sender_user else "User"
        )

        # 4. Detect self-commitments via LLM.
        #
        # The sender's timezone goes in with the message. `msg.created_at` is
        # UTC, and a model told only that resolves "mai" against the UTC date --
        # which is the previous day for every message sent before 07:00 in
        # Hanoi, so the appointment came out a day early with nothing to catch
        # it. The model needs the date the sender was actually looking at.
        sender_timezone = sender_user.timezone if sender_user else None
        candidates = await detect_self_commitments(
            message_text=msg.original_text,
            sender_id=msg.sender_id,
            sender_name=sender_name,
            reference_timestamp=msg.created_at,
            conversation_id=conversation_id,
            message_id=message_id,
            settings=self.settings,
            sender_timezone=sender_timezone,
        )

        if not candidates:
            return []

        # 5. Persist one proposal per member, each deciding for themselves.
        #
        # An appointment the assistant noticed by itself is not the sender's
        # private business: everybody in the conversation is party to it, so
        # everybody is offered it, and approving or rejecting is each person's
        # own act. One shared row could not express that -- a single `status`
        # cannot say "confirmed by two of us and declined by the third" -- so
        # each member gets their own row and their own decision. This is only
        # true of the proactive path; a proposal somebody asked the assistant
        # for stays with the person who asked (ADR-31).
        #
        # Every row resolves its time in the *sender's* timezone, not the
        # owner's: "6h" is a wall clock belonging to whoever said it, and
        # re-reading it on each recipient's clock would move the meeting by the
        # offset between them.
        #
        # A private message is never fanned out. It is addressed to one account
        # by construction, and its text is exactly what must not reach the rest
        # of the conversation.
        recipients = (
            [msg.sender_id]
            if msg.visibility != "public"
            else await self._proactive_recipients(db, conversation_id, msg.sender_id)
        )

        prop_service = ActionProposalService(db)
        proposals: list[ActionProposal] = []
        for owner_id in recipients:
            proposals.extend(
                await prop_service.create_proposals_from_candidates(
                    conversation_id=conversation_id,
                    source_message_id=message_id,
                    candidates=candidates,
                    owner_user_id=owner_id,
                    source_mode="proactive",
                    created_by_user_id=None,
                    timezone_user_id=msg.sender_id,
                )
            )

        return [ActionProposalResponse.model_validate(p) for p in proposals]

    @staticmethod
    async def _proactive_recipients(
        db: Any, conversation_id: str, sender_id: str
    ) -> list[str]:
        """Who is offered a proposal the assistant raised on its own.

        The sender, plus every other member who has granted `proactive_scan`.

        The sender is included unconditionally because the path that got here
        has already cleared them: the manual endpoint is a request they typed,
        which needs only `read_conversations`, and the background scanner checks
        their `proactive_scan` before it calls at all. Re-checking here would
        take the manual endpoint away from anyone who never turned scanning on,
        which is a permission they were deliberately not asked for.

        Every other member is checked, because nobody asked on their behalf --
        a card in their chat is the assistant acting proactively at them, which
        is exactly what `proactive_scan` governs. A member who never answered
        has no row, and no row means not granted
        (`docs/CONTRACT.md` §5 note 19), so silence produces no card.
        """
        from sqlalchemy import select as _select

        from src.database.models import ConversationMember as _Member

        member_ids = list(
            (
                await db.scalars(
                    _select(_Member.user_id).where(
                        _Member.conversation_id == conversation_id
                    )
                )
            ).all()
        )
        others = [uid for uid in member_ids if uid != sender_id]
        return [sender_id] + [
            uid for uid in others if await has_consent(db, uid, "proactive_scan")
        ]

