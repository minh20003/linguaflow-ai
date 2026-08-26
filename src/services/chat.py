"""Business logic for durable conversations and original chat messages."""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.database.models import (
    ActionProposal,
    Attachment,
    Conversation,
    ConversationMember,
    Feedback,
    Message,
    MessageReaction,
    SavedMessage,
    TranslationEdit,
    TranslationResult,
    User,
)
from src.schemas.chat import ConversationType
from src.services.blocking import DirectMessagingBlockedError, is_blocked_between
from src.services.llm import LLMConfigError, extract_text, get_llm
from src.services.profiles import profile_for, select_for_reader

logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Base exception for controlled chat business-rule failures."""


class ConversationNotFoundError(ChatServiceError):
    """Raised when a requested conversation does not exist."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__("Conversation not found")


class ConversationMembershipError(ChatServiceError):
    """Raised when a user is not a member of a conversation."""

    def __init__(self, conversation_id: str, user_id: str) -> None:
        self.conversation_id = conversation_id
        self.user_id = user_id
        super().__init__("You are not a member of this conversation")


class MessageNotFoundError(ChatServiceError):
    """Raised when a message does not exist in the conversation given."""

    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        super().__init__("Message not found")


class MessageOwnershipError(ChatServiceError):
    """Raised when someone other than the sender tries to change a message."""

    def __init__(self, message_id: str, user_id: str) -> None:
        self.message_id = message_id
        self.user_id = user_id
        super().__init__("Only the sender can change this message")


class MessageAlreadyDeletedError(ChatServiceError):
    """Raised when editing a message that was already withdrawn."""

    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        super().__init__("This message was already deleted")


class TranslationNotFoundError(ChatServiceError):
    """Raised when feedback references a translation that does not exist."""

    def __init__(self, translation_id: str) -> None:
        self.translation_id = translation_id
        super().__init__("Translation not found")


class ClientMessageIdConflictError(ChatServiceError):
    """Raised when an idempotency key is reused with different message text."""

    def __init__(self, client_message_id: str) -> None:
        self.client_message_id = client_message_id
        super().__init__("client_message_id was already used with different text")


class ConversationValidationError(ChatServiceError):
    """Raised when a conversation or message violates a domain rule."""


class DirectConversationRequiredError(ChatServiceError):
    """An operation is only meaningful for a one-to-one conversation."""


class ReferencedUsersNotFoundError(ChatServiceError):
    """Raised when a conversation request references missing users."""

    def __init__(self, missing_user_ids: Sequence[str]) -> None:
        self.missing_user_ids = tuple(missing_user_ids)
        super().__init__("One or more referenced users do not exist")


@dataclass(frozen=True, slots=True)
class ConversationResult:
    """A conversation, and whether this call is what brought it into existence.

    Mirrors `SendMessageResult.created`: both endpoints answer a request that may
    turn out to be a repeat, and the caller needs the difference to pick a status
    code without asking the database a second question.
    """

    conversation: Conversation
    created: bool


@dataclass(frozen=True, slots=True)
class SendMessageResult:
    """Canonical persisted message and eligible realtime recipients."""

    message: Message
    recipient_ids: tuple[str, ...]
    created: bool


def message_mentions(message: Message) -> list[dict[str, str]]:
    """Return a defensive representation of persisted mention metadata."""
    try:
        parsed = json.loads(message.mentions_json)
    except (TypeError, json.JSONDecodeError):
        return []
    return [item for item in parsed if isinstance(item, dict) and item.get("type") in {"user", "assistant"}]


class ChatService:
    """Encapsulate chat authorization, persistence, and idempotency rules."""

    max_message_length = 5000
    max_client_message_id_length = 128
    assistant_conversation_title = "__linguachat_assistant__"

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_conversation(
        self,
        *,
        creator_id: str,
        conversation_type: ConversationType | str,
        member_ids: Sequence[str],
        title: str | None = None,
    ) -> ConversationResult:
        """Create a direct or group conversation with validated membership.

        A direct conversation that already exists is returned as it is rather
        than duplicated: two people have one thread between them, and a second
        one would split their history in half (docs/CONTRACT.md §3.5). Groups are
        not deduplicated — the same people can have several groups for several
        purposes.

        Returns:
            The conversation, and whether it was created by this call.
        """
        self._validate_conversation_request(
            creator_id=creator_id,
            conversation_type=conversation_type,
            member_ids=member_ids,
            title=title,
        )

        unique_member_ids = self._unique_member_ids(creator_id, member_ids)
        if conversation_type == "direct" and len(unique_member_ids) != 2:
            raise ConversationValidationError(
                "A direct conversation must have exactly two distinct members"
            )
        if conversation_type == "group" and len(unique_member_ids) < 2:
            raise ConversationValidationError(
                "A group conversation must have at least two distinct members"
            )

        existing_user_ids = set(
            (
                await self._db.scalars(
                    select(User.id).where(User.id.in_(unique_member_ids))
                )
            ).all()
        )
        missing_user_ids = [
            user_id for user_id in unique_member_ids if user_id not in existing_user_ids
        ]
        if missing_user_ids:
            raise ReferencedUsersNotFoundError(missing_user_ids)

        if conversation_type == "direct":
            other_id = next(user_id for user_id in unique_member_ids if user_id != creator_id)
            if await is_blocked_between(self._db, creator_id, other_id):
                raise DirectMessagingBlockedError("Direct messaging is unavailable")
            existing = await self._find_direct_conversation(unique_member_ids)
            if existing is not None:
                return ConversationResult(conversation=existing, created=False)

        conversation = Conversation(
            type=conversation_type,
            title=title,
            created_by=creator_id,
        )
        self._db.add(conversation)
        await self._db.flush()

        self._db.add_all(
            [
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=user_id,
                    role="owner" if conversation_type == "group" and user_id == creator_id else "member",
                )
                for user_id in unique_member_ids
            ]
        )
        await self._db.flush()
        await self._db.refresh(conversation)
        return ConversationResult(conversation=conversation, created=True)

    async def get_or_create_assistant_conversation(
        self, *, user_id: str
    ) -> ConversationResult:
        """Return the private, durable thread used to talk to the Assistant.

        This is deliberately a one-member system group rather than a fake
        frontend-only thread.  It lets the normal history and WebSocket
        pipelines carry assistant requests and responses across reconnects.
        """
        member = aliased(ConversationMember)
        member_count = (
            select(func.count())
            .select_from(member)
            .where(member.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
        )
        existing = await self._db.scalar(
            select(Conversation)
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Conversation.id,
            )
            .where(
                Conversation.type == "group",
                Conversation.title == self.assistant_conversation_title,
                Conversation.created_by == user_id,
                Conversation.deleted_at.is_(None),
                ConversationMember.user_id == user_id,
                member_count == 1,
            )
            .order_by(Conversation.created_at, Conversation.id)
            .limit(1)
        )
        if existing is not None:
            return ConversationResult(conversation=existing, created=False)

        conversation = Conversation(
            type="group",
            title=self.assistant_conversation_title,
            created_by=user_id,
        )
        self._db.add(conversation)
        await self._db.flush()
        self._db.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user_id,
                role="owner",
            )
        )
        await self._db.flush()
        await self._db.refresh(conversation)
        return ConversationResult(conversation=conversation, created=True)

    async def _find_direct_conversation(
        self,
        member_ids: Sequence[str],
    ) -> Conversation | None:
        """Return the direct conversation between exactly these two people.

        One query: the membership rows for the pair are grouped by conversation
        and only a group holding both of them counts. The total-member check
        guards the case a group of two was somehow stored with type `direct`,
        which would otherwise be reused as if it were the pair's own thread.

        Args:
            member_ids: The two distinct member ids, creator included.

        Returns:
            The existing conversation, or None when the pair has none yet.
        """
        # Aliased, and correlated explicitly: the outer query already joins
        # ConversationMember, so an unaliased subquery correlates to that join
        # instead of counting, and SQLAlchemy refuses it for having no FROM.
        any_member = aliased(ConversationMember)
        total_members = (
            select(func.count())
            .select_from(any_member)
            .where(any_member.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
        )
        return await self._db.scalar(
            select(Conversation)
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Conversation.id,
            )
            .where(
                Conversation.type == "direct",
                ConversationMember.user_id.in_(member_ids),
                total_members == len(member_ids),
            )
            .group_by(Conversation.id)
            .having(func.count(func.distinct(ConversationMember.user_id)) == len(member_ids))
            .order_by(Conversation.created_at, Conversation.id)
            .limit(1)
        )

    async def list_conversations(self, *, user_id: str) -> list[Conversation]:
        """List conversations the supplied user belongs to in stable order."""
        result = await self._db.scalars(
            select(Conversation)
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Conversation.id,
            )
            .where(ConversationMember.user_id == user_id, Conversation.deleted_at.is_(None))
            .order_by(
                ConversationMember.is_pinned.desc(),
                ConversationMember.pinned_at.desc().nullslast(),
                Conversation.created_at.desc(),
                Conversation.id.desc(),
            )
        )
        return list(result.all())

    async def get_last_messages(
        self,
        *,
        conversation_ids: Sequence[str],
        reader_language: str,
        reader_profiles: Mapping[str, str] | None = None,
        reader_tones: Mapping[str, str] | None = None,
    ) -> dict[str, tuple[str, datetime]]:
        """Summarise the newest message of each conversation for one reader.

        Two queries regardless of how many conversations are passed: ranking the
        messages in the database rather than fetching each conversation's last
        message separately is what keeps the list endpoint off an N+1.

        A message can hold several translations into one language, differing in
        how they address the reader, so the language alone no longer picks a
        row. This used to be a dict comprehension keyed by message id, which
        meant whichever row the database returned last silently won — the
        preview in the sidebar and the text inside the conversation could
        disagree, and neither would be wrong twice in the same way.

        Args:
            conversation_ids: Conversations to summarise.
            reader_language: Language the calling account reads; the translation
                into it is preferred over the original text where one exists.
            reader_profiles: The caller's standing in each conversation, already
                resolved by the endpoint. Absent entries fall back to the
                neutral standing, which is also the state of every conversation
                too young to have been profiled.

        Returns:
            Conversation id mapped to its preview text and send time.
            Conversations without messages are absent from the mapping.
        """
        if not conversation_ids:
            return {}

        ranked = (
            select(
                Message.id,
                Message.conversation_id,
                Message.original_text,
                Message.created_at,
                Message.deleted_at,
                func.row_number()
                .over(
                    partition_by=Message.conversation_id,
                    order_by=(Message.created_at.desc(), Message.id.desc()),
                )
                .label("rank"),
            )
            # Withdrawn messages stay in the ranking. The earlier rule skipped
            # them so the message before became the preview again, which read as
            # the conversation quietly rewinding: the row went back to older
            # text, or blank when there was nothing before it, and neither says
            # what happened. The row now reports the withdrawal instead — see
            # the empty-text convention below and docs/CONTRACT.md §3.5.
            .where(Message.conversation_id.in_(conversation_ids))
            .subquery()
        )
        newest = (await self._db.execute(select(ranked).where(ranked.c.rank == 1))).all()

        candidates = (
            await self._db.execute(
                select(
                    TranslationResult.message_id,
                    TranslationResult.translated_text,
                    TranslationResult.target_language,
                    TranslationResult.honorific_profile,
                )
                .where(
                    TranslationResult.message_id.in_([row.id for row in newest]),
                    TranslationResult.target_language == reader_language,
                )
                .order_by(
                    TranslationResult.version.desc(),
                    TranslationResult.created_at.desc(),
                    TranslationResult.id.desc(),
                )
            )
        ).all()

        by_message: dict[str, list] = {}
        for candidate in candidates:
            by_message.setdefault(candidate.message_id, []).append(candidate)

        profiles = reader_profiles or {}
        tones = reader_tones or {}
        translated: dict[str, str] = {}
        for row in newest:
            chosen = select_for_reader(
                by_message.get(row.id, []),
                target_language=reader_language,
                honorific_profile=profile_for(profiles, row.conversation_id),
                translation_tone=tones.get(row.conversation_id, "natural"),
            )
            if chosen is not None:
                translated[row.id] = chosen.translated_text

        # A withdrawn message previews as empty text with its timestamp intact.
        # The wording belongs to the client: it is interface copy, and this
        # endpoint has no business deciding which language the reader wants it
        # in. Ordinary messages can never be empty — the send path rejects blank
        # text — so "" is unambiguous (docs/CONTRACT.md §3.5).
        return {
            row.conversation_id: (
                "" if row.deleted_at is not None
                else translated.get(row.id, row.original_text),
                row.created_at,
            )
            for row in newest
        }

    async def get_contact_ids(self, *, user_id: str) -> tuple[str, ...]:
        """Everyone sharing at least one conversation with ``user_id``.

        This is the audience for presence: connecting must not tell the whole
        installation that someone came online, only the people they actually
        talk to.

        Args:
            user_id: Account whose contacts are wanted; never included itself.

        Returns:
            Distinct user ids in a stable order.
        """
        mine = select(ConversationMember.conversation_id).where(
            ConversationMember.user_id == user_id
        )
        result = await self._db.scalars(
            select(ConversationMember.user_id)
            .where(
                ConversationMember.conversation_id.in_(mine),
                ConversationMember.user_id != user_id,
            )
            .distinct()
            .order_by(ConversationMember.user_id)
        )
        return tuple(result.all())

    async def get_conversation_member_ids(
        self,
        *,
        conversation_id: str,
    ) -> tuple[str, ...]:
        """Return stable member IDs for a known, authorized conversation."""
        result = await self._db.scalars(
            select(ConversationMember.user_id)
            .where(ConversationMember.conversation_id == conversation_id)
            .order_by(ConversationMember.user_id)
        )
        return tuple(result.all())

    async def get_conversation_members(
        self,
        *,
        conversation_id: str,
    ) -> Sequence[User]:
        """Return the member rows themselves, for rendering and for language fan-out."""
        result = await self._db.scalars(
            select(User)
            .join(ConversationMember, ConversationMember.user_id == User.id)
            .where(ConversationMember.conversation_id == conversation_id)
            .order_by(User.id)
        )
        return result.all()

    async def get_members_by_conversation(
        self,
        *,
        conversation_ids: Sequence[str],
    ) -> dict[str, list[User]]:
        """Load the members of many conversations in one query.

        The list endpoint renders every conversation it returns, so asking per
        conversation made the query count grow with the list — the same N+1 that
        `get_last_messages` and `get_unread_counts` are shaped to avoid.

        Args:
            conversation_ids: Conversations whose members are wanted.

        Returns:
            Conversation id mapped to its members, ordered by user id.
        """
        if not conversation_ids:
            return {}

        rows = await self._db.execute(
            select(ConversationMember.conversation_id, User)
            .join(User, ConversationMember.user_id == User.id)
            .where(ConversationMember.conversation_id.in_(conversation_ids))
            .order_by(User.id)
        )
        grouped: dict[str, list[User]] = {}
        for conversation_id, user in rows.all():
            grouped.setdefault(conversation_id, []).append(user)
        return grouped

    async def get_member_preferences_for_conversations(
        self, *, user_id: str, conversation_ids: Sequence[str]
    ) -> dict[str, ConversationMember]:
        """Load the caller's pin/mute rows for a whole sidebar in one query."""
        if not conversation_ids:
            return {}
        rows = await self._db.scalars(
            select(ConversationMember).where(
                ConversationMember.user_id == user_id,
                ConversationMember.conversation_id.in_(conversation_ids),
            )
        )
        return {row.conversation_id: row for row in rows}

    async def update_conversation_preferences(
        self,
        *,
        user_id: str,
        conversation_id: str,
        is_pinned: bool | None,
        is_muted: bool | None,
    ) -> ConversationMember:
        """Set explicit per-member preferences without moving an existing pin."""
        await self._require_membership(conversation_id=conversation_id, user_id=user_id)
        member = await self._db.get(ConversationMember, (conversation_id, user_id))
        if member is None:  # defensive, _require_membership has already checked
            raise ConversationMembershipError(conversation_id, user_id)
        if is_pinned is not None:
            if is_pinned and not member.is_pinned:
                member.is_pinned = True
                member.pinned_at = datetime.now(UTC)
            elif not is_pinned:
                member.is_pinned = False
                member.pinned_at = None
        if is_muted is not None:
            member.is_muted = is_muted
        await self._db.commit()
        await self._db.refresh(member)
        return member

    async def get_message_history(
        self,
        *,
        user_id: str,
        conversation_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Return a member's recent messages in deterministic chronology."""
        if not 1 <= limit <= 100:
            raise ConversationValidationError("limit must be between 1 and 100")

        await self._require_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        recent_messages = list(
            (
                await self._db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        recent_messages.reverse()
        return recent_messages

    async def get_message_for_member(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ) -> Message:
        """Return one message after the same scope check mutations use."""
        return await self._require_message_for_member(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    async def mark_conversation_read(
        self,
        *,
        user_id: str,
        conversation_id: str,
    ) -> datetime:
        """Move this member's read mark to now (docs/CONTRACT.md §3.8).

        Args:
            user_id: Member who has caught up.
            conversation_id: Conversation being marked.

        Returns:
            The moment recorded, for the receipt other members are told about.

        Raises:
            ConversationNotFoundError: No such conversation.
            ConversationMembershipError: Caller is not a member.
        """
        await self._require_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        read_at = datetime.now(UTC)
        await self._db.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
            .values(last_read_at=read_at)
        )
        await self._db.commit()
        return read_at

    async def search_messages(
        self,
        *,
        user_id: str,
        conversation_id: str,
        query: str,
        reader_language: str,
        limit: int,
        before_created_at: datetime | None = None,
        before_id: str | None = None,
    ) -> list[Message]:
        """Find non-deleted originals or candidate translations in one thread.

        Translation rows are narrowed to the caller's language here, then the
        route's reader-selection ladder discards any candidate rendering they
        are not entitled to before it becomes a result.
        """
        if not 1 <= limit <= 100:
            raise ConversationValidationError("limit must be between 1 and 100")
        await self._require_membership(conversation_id=conversation_id, user_id=user_id)
        needle = query.strip()
        if not needle:
            raise ConversationValidationError("q must not be blank")
        escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = (
            select(Message)
            .outerjoin(TranslationResult, TranslationResult.message_id == Message.id)
            .where(
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
                or_(
                    Message.original_text.ilike(pattern, escape="\\"),
                    (TranslationResult.target_language == reader_language)
                    & TranslationResult.translated_text.ilike(pattern, escape="\\"),
                ),
            )
            .distinct()
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit + 1)
        )
        if before_created_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    Message.created_at < before_created_at,
                    (Message.created_at == before_created_at) & (Message.id < before_id),
                )
            )
        return list((await self._db.scalars(statement)).all())

    async def get_unread_counts(
        self,
        *,
        user_id: str,
        conversation_ids: Sequence[str],
    ) -> dict[str, int]:
        """Count each conversation's messages this user has not read yet.

        One grouped query rather than one per conversation, for the same reason
        `get_last_messages` is written that way.

        Args:
            user_id: Reader whose marks decide what counts.
            conversation_ids: Conversations to count within.

        Returns:
            Conversation id mapped to its unread total; absent means zero.
        """
        if not conversation_ids:
            return {}

        # Own messages are never unread, and a withdrawn one has nothing to read.
        rows = await self._db.execute(
            select(Message.conversation_id, func.count(Message.id))
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Message.conversation_id,
            )
            .where(
                ConversationMember.user_id == user_id,
                Message.conversation_id.in_(conversation_ids),
                Message.sender_id != user_id,
                Message.deleted_at.is_(None),
                (ConversationMember.last_read_at.is_(None))
                | (Message.created_at > ConversationMember.last_read_at),
            )
            .group_by(Message.conversation_id)
        )
        return {conversation_id: total for conversation_id, total in rows.all()}

    async def send_message(
        self,
        *,
        sender_id: str,
        conversation_id: str,
        client_message_id: str,
        text: str,
        attachment_id: str | None = None,
        reply_to_message_id: str | None = None,
        forwarded_from_message_id: str | None = None,
        mentions: Sequence[Mapping[str, str | None]] = (),
    ) -> SendMessageResult:
        """Persist an authorized original message before any transport fan-out.

        An `attachment_id` is claimed by this message; a `reply_to_message_id`
        is stored only when it names a message in the same conversation, so a
        quote can never point somewhere the reader cannot see.
        """
        self._validate_send_message_request(
            sender_id=sender_id,
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            text=text,
        )

        conversation = await self._db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        member_ids = await self.get_conversation_member_ids(
            conversation_id=conversation_id,
        )
        if sender_id not in member_ids:
            raise ConversationMembershipError(conversation_id, sender_id)
        if conversation.type == "direct":
            other_ids = [member_id for member_id in member_ids if member_id != sender_id]
            if other_ids and await is_blocked_between(self._db, sender_id, other_ids[0]):
                raise DirectMessagingBlockedError("Direct messaging is unavailable")
        recipient_ids = tuple(
            member_id for member_id in member_ids if member_id != sender_id
        )
        normalized_mentions = self._normalize_mentions(
            mentions=mentions,
            member_ids=member_ids,
            sender_id=sender_id,
        )

        # One round trip is valuable on a remote database.  The outer join
        # retains the authenticated sender's language even when no idempotency
        # row exists, avoiding separate "existing message" and "language"
        # queries on every ordinary send.
        idempotency_row = await self._db.execute(
            select(User.preferred_language, Message)
            .outerjoin(
                Message,
                and_(
                    Message.sender_id == sender_id,
                    Message.conversation_id == conversation_id,
                    Message.client_message_id == client_message_id,
                ),
            )
            .where(User.id == sender_id)
        )
        sender_language, existing_message = idempotency_row.one_or_none() or ("en", None)
        if existing_message is not None:
            self._raise_if_text_conflicts(existing_message, text)
            await self._db.commit()
            return SendMessageResult(
                message=existing_message,
                recipient_ids=recipient_ids,
                created=False,
            )

        message = Message(
            client_message_id=client_message_id,
            conversation_id=conversation_id,
            sender_id=sender_id,
            original_text=text,
            mentions_json=json.dumps(normalized_mentions),
            source_language=sender_language or "en",
            reply_to_message_id=await self._resolve_reply_target(
                conversation_id=conversation_id,
                reply_to_message_id=reply_to_message_id,
            ),
            forwarded_from_message_id=await self._resolve_forward_target(
                sender_id=sender_id,
                forwarded_from_message_id=forwarded_from_message_id,
            ),
        )
        self._db.add(message)

        try:
            # Commit is deliberate: fan-out must never precede durable persistence.
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            existing_message = await self._find_message_by_client_message_id(
                sender_id=sender_id,
                conversation_id=conversation_id,
                client_message_id=client_message_id,
            )
            if existing_message is None:
                raise
            self._raise_if_text_conflicts(existing_message, text)
            await self._db.commit()
            return SendMessageResult(
                message=existing_message,
                recipient_ids=recipient_ids,
                created=False,
            )

        await self._claim_attachment(
            attachment_id=attachment_id,
            conversation_id=conversation_id,
            uploader_id=sender_id,
            message_id=message.id,
        )

        # PostgreSQL returns server defaults (including `created_at`) as part
        # of the INSERT. Avoiding a refresh and another commit keeps the
        # acknowledgement on the same durable-write round trip.
        return SendMessageResult(
            message=message,
            recipient_ids=recipient_ids,
            created=True,
        )

    async def create_assistant_reply(
        self,
        *,
        trigger_message: Message,
        member_ids: Sequence[str],
    ) -> SendMessageResult:
        """Persist an in-thread answer to an explicit assistant mention."""
        existing = await self._find_message_by_client_message_id(
            sender_id=trigger_message.sender_id,
            conversation_id=trigger_message.conversation_id,
            client_message_id=f"assistant:{trigger_message.id}",
        )
        if existing is not None:
            return SendMessageResult(existing, tuple(member_ids), False)

        reply = Message(
            client_message_id=f"assistant:{trigger_message.id}",
            conversation_id=trigger_message.conversation_id,
            sender_id=trigger_message.sender_id,
            original_text=await self._assistant_reply_text(trigger_message),
            source_language=trigger_message.source_language,
            assistant_generated=True,
            reply_to_message_id=trigger_message.id,
        )
        self._db.add(reply)
        await self._db.commit()
        await self._db.refresh(reply)
        await self._db.commit()
        return SendMessageResult(reply, tuple(member_ids), True)

    async def _assistant_reply_text(self, trigger_message: Message) -> str:
        """Answer a mention using recent in-conversation context.

        The answer and action-extraction jobs are intentionally separate: this
        makes a useful conversational reply available immediately while every
        calendar change remains a user-approved proposal.
        """
        fallback = (
            "Mình chưa thể tạo câu trả lời đầy đủ ngay lúc này. "
            "Bạn có thể thử lại, hoặc nêu rõ hơn điều bạn muốn mình hỗ trợ."
        )
        request = re.sub(r"(^|\s)@assistant\b", " ", trigger_message.original_text, flags=re.IGNORECASE).strip()
        if not request:
            return "Bạn muốn mình hỗ trợ điều gì trong cuộc trò chuyện này?"

        try:
            recent = list(
                reversed(
                    (await self._db.scalars(
                        select(Message)
                        .where(
                            Message.conversation_id == trigger_message.conversation_id,
                            Message.deleted_at.is_(None),
                        )
                        .order_by(Message.created_at.desc(), Message.id.desc())
                        .limit(8)
                    )).all()
                )
            )
            transcript = "\n".join(
                f"{'Trợ lý' if message.assistant_generated else 'Người dùng'}: {message.original_text}"
                for message in recent
                if message.original_text.strip()
            )
            response = await get_llm().ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Bạn là Trợ lý thông minh trong ứng dụng nhắn tin. "
                            "Trả lời trực tiếp, đầy đủ và hữu ích cho yêu cầu mới nhất, "
                            "dựa trên ngữ cảnh được cung cấp. Trả lời bằng cùng ngôn ngữ "
                            "với yêu cầu của người dùng. Không tự khẳng định đã tạo, sửa "
                            "hoặc thêm lịch/công việc: nếu có đề xuất, nói rõ người dùng phải "
                            "xác nhận trước. Không nhắc lại tag @assistant."
                        )
                    ),
                    HumanMessage(
                        content=f"Ngữ cảnh gần đây:\n{transcript}\n\nYêu cầu cần trả lời:\n{request}"
                    ),
                ]
            )
            answer = extract_text(response)
            return answer[:5000] if answer else fallback
        except (LLMConfigError, OSError, RuntimeError, ValueError):
            logger.warning("Assistant conversational reply unavailable", exc_info=True)
            return fallback

    @staticmethod
    def _normalize_mentions(
        *,
        mentions: Sequence[Mapping[str, str | None]],
        member_ids: Sequence[str],
        sender_id: str,
    ) -> list[dict[str, str]]:
        """Reject spoofed tags and retain each valid target only once."""
        member_set = set(member_ids)
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for mention in mentions:
            mention_type = mention.get("type")
            if mention_type == "assistant":
                key = ("assistant", "")
                if key not in seen:
                    result.append({"type": "assistant"})
                    seen.add(key)
                continue
            user_id = mention.get("user_id")
            if mention_type == "user" and user_id and user_id in member_set and user_id != sender_id:
                key = ("user", user_id)
                if key not in seen:
                    result.append({"type": "user", "user_id": user_id})
                    seen.add(key)
        return result

    async def edit_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        text: str,
    ) -> tuple[Message, tuple[str, ...]]:
        """Replace a message's text on behalf of its sender (F-06).

        Stale translations are dropped here rather than left to rot: they render
        text the sender has retracted, and the caller schedules a fresh
        translation from the returned message.

        Args:
            user_id: Account attempting the edit.
            conversation_id: Conversation the message must belong to.
            message_id: Message being edited.
            text: Replacement text, already validated as non-blank.

        Returns:
            The updated message and the other members' ids, for realtime fan-out.

        Raises:
            MessageNotFoundError: No such message in that conversation.
            MessageOwnershipError: Caller is not the sender.
            MessageAlreadyDeletedError: The message was withdrawn.
            ConversationValidationError: Text longer than the message limit.
        """
        if len(text) > self.max_message_length:
            raise ConversationValidationError(
                f"text must be at most {self.max_message_length} characters"
            )

        message, recipient_ids = await self._require_own_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        if message.deleted_at is not None:
            raise MessageAlreadyDeletedError(message_id)

        message.original_text = text
        message.edited_at = datetime.now(UTC)
        await self._db.execute(
            delete(TranslationResult).where(TranslationResult.message_id == message.id)
        )
        await self._db.execute(
            update(ActionProposal)
            .where(ActionProposal.source_message_id == message.id, ActionProposal.status.in_(("needs_clarification", "pending_confirmation")))
            .values(status="stale", stale_at=datetime.now(UTC))
        )
        await self._db.commit()
        await self._db.refresh(message)
        return message, recipient_ids

    async def delete_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ) -> tuple[Message, tuple[str, ...]]:
        """Withdraw a message on behalf of its sender, keeping the row (F-06).

        Deleting twice is not an error: the caller asked for the message to be
        gone, and it is.

        Args:
            user_id: Account attempting the deletion.
            conversation_id: Conversation the message must belong to.
            message_id: Message being withdrawn.

        Returns:
            The updated message and the other members' ids, for realtime fan-out.

        Raises:
            MessageNotFoundError: No such message in that conversation.
            MessageOwnershipError: Caller is not the sender.
        """
        message, recipient_ids = await self._require_own_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        if message.deleted_at is None:
            message.deleted_at = datetime.now(UTC)
            await self._db.execute(
                update(ActionProposal)
                .where(ActionProposal.source_message_id == message.id, ActionProposal.status.in_(("needs_clarification", "pending_confirmation")))
                .values(status="stale", stale_at=datetime.now(UTC))
            )
            await self._db.commit()
            await self._db.refresh(message)
        return message, recipient_ids

    async def _resolve_reply_target(
        self,
        *,
        conversation_id: str,
        reply_to_message_id: str | None,
    ) -> str | None:
        """Keep a reply link only when it points inside this conversation.

        A quote of a message from somewhere else would render text the reader is
        not entitled to, so an id that does not belong here is dropped rather
        than rejected — the message itself is still worth sending.
        """
        if reply_to_message_id is None:
            return None
        parent_conversation = await self._db.scalar(
            select(Message.conversation_id).where(Message.id == reply_to_message_id)
        )
        return reply_to_message_id if parent_conversation == conversation_id else None

    async def _resolve_forward_target(
        self,
        *,
        sender_id: str,
        forwarded_from_message_id: str | None,
    ) -> str | None:
        """Keep a forward link only for a message the sender may read."""
        if forwarded_from_message_id is None:
            return None
        permitted = await self._db.scalar(
            select(Message.id)
            .join(ConversationMember, ConversationMember.conversation_id == Message.conversation_id)
            .where(
                Message.id == forwarded_from_message_id,
                Message.deleted_at.is_(None),
                ConversationMember.user_id == sender_id,
            )
        )
        return forwarded_from_message_id if permitted else None

    async def _claim_attachment(
        self,
        *,
        attachment_id: str | None,
        conversation_id: str,
        uploader_id: str,
        message_id: str,
    ) -> None:
        """Bind an already uploaded file to the message that carries it.

        Scoped to the uploader and the conversation so one member cannot attach
        another member's file, or a file from a conversation they left.
        """
        if attachment_id is None:
            return
        await self._db.execute(
            update(Attachment)
            .where(
                Attachment.id == attachment_id,
                Attachment.conversation_id == conversation_id,
                Attachment.uploader_id == uploader_id,
                Attachment.message_id.is_(None),
            )
            .values(message_id=message_id)
        )
        await self._db.commit()

    async def set_saved_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        is_saved: bool,
    ) -> bool:
        """Create or remove a bookmark idempotently after scoped authorization."""
        message = await self._require_message_for_member(
            user_id=user_id, conversation_id=conversation_id, message_id=message_id
        )
        if is_saved:
            if message.deleted_at is not None:
                raise MessageAlreadyDeletedError(message_id)
            existing = await self._db.scalar(
                select(SavedMessage.id).where(
                    SavedMessage.user_id == user_id, SavedMessage.message_id == message_id
                )
            )
            if existing is None:
                self._db.add(SavedMessage(user_id=user_id, message_id=message_id))
                try:
                    await self._db.commit()
                except IntegrityError:
                    await self._db.rollback()
            return True
        await self._db.execute(
            delete(SavedMessage).where(
                SavedMessage.user_id == user_id, SavedMessage.message_id == message_id
            )
        )
        await self._db.commit()
        return False

    async def saved_message_ids(self, *, user_id: str, message_ids: Sequence[str]) -> set[str]:
        if not message_ids:
            return set()
        rows = await self._db.scalars(
            select(SavedMessage.message_id).where(
                SavedMessage.user_id == user_id, SavedMessage.message_id.in_(message_ids)
            )
        )
        return set(rows)

    async def list_saved_messages(
        self,
        *,
        user_id: str,
        limit: int,
        before_created_at: datetime | None = None,
        before_id: str | None = None,
    ) -> list[tuple[Message, SavedMessage]]:
        """Read bookmark history ordered by relation creation, not message time."""
        if not 1 <= limit <= 100:
            raise ConversationValidationError("limit must be between 1 and 100")
        statement = (
            select(Message, SavedMessage)
            .join(SavedMessage, SavedMessage.message_id == Message.id)
            .join(
                ConversationMember,
                (ConversationMember.conversation_id == Message.conversation_id)
                & (ConversationMember.user_id == user_id),
            )
            .where(SavedMessage.user_id == user_id, Message.deleted_at.is_(None))
            .order_by(SavedMessage.created_at.desc(), SavedMessage.id.desc())
            .limit(limit + 1)
        )
        if before_created_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    SavedMessage.created_at < before_created_at,
                    (SavedMessage.created_at == before_created_at) & (SavedMessage.id < before_id),
                )
            )
        rows = await self._db.execute(statement)
        return list(rows.all())

    async def update_reaction(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        emoji: str,
        add: bool,
    ) -> list[tuple[str, int, list[str]]]:
        """Explicitly add/remove an emoji and return canonical aggregates."""
        message = await self._require_message_for_member(
            user_id=user_id, conversation_id=conversation_id, message_id=message_id
        )
        if add:
            if message.deleted_at is not None:
                raise MessageAlreadyDeletedError(message_id)
            exists = await self._db.scalar(
                select(MessageReaction.id).where(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user_id,
                    MessageReaction.emoji == emoji,
                )
            )
            if exists is None:
                self._db.add(MessageReaction(message_id=message_id, user_id=user_id, emoji=emoji))
                try:
                    await self._db.commit()
                except IntegrityError:
                    await self._db.rollback()
        else:
            await self._db.execute(
                delete(MessageReaction).where(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user_id,
                    MessageReaction.emoji == emoji,
                )
            )
            await self._db.commit()
        return (await self.reactions_by_message(message_ids=[message_id])).get(message_id, [])

    async def reactions_by_message(
        self, *, message_ids: Sequence[str]
    ) -> dict[str, list[tuple[str, int, list[str]]]]:
        """Fetch all reaction aggregates for a message page in a bounded query."""
        if not message_ids:
            return {}
        rows = await self._db.execute(
            select(MessageReaction.message_id, MessageReaction.emoji, MessageReaction.user_id)
            .where(MessageReaction.message_id.in_(message_ids))
            .order_by(MessageReaction.emoji, MessageReaction.user_id)
        )
        grouped: dict[str, dict[str, list[str]]] = {}
        for message_id, emoji, user_id in rows:
            grouped.setdefault(message_id, {}).setdefault(emoji, []).append(user_id)
        return {
            message_id: [(emoji, len(user_ids), user_ids) for emoji, user_ids in emojis.items()]
            for message_id, emojis in grouped.items()
        }

    async def _require_message_for_member(
        self, *, user_id: str, conversation_id: str, message_id: str
    ) -> Message:
        await self._require_membership(conversation_id=conversation_id, user_id=user_id)
        message = await self._db.get(Message, message_id)
        if message is None or message.conversation_id != conversation_id:
            raise MessageNotFoundError(message_id)
        return message

    async def get_attachments_by_message(
        self,
        *,
        message_ids: Sequence[str],
    ) -> dict[str, Attachment]:
        """Load the attachment of each message in a page, in one query."""
        if not message_ids:
            return {}
        rows = await self._db.scalars(
            select(Attachment).where(Attachment.message_id.in_(message_ids))
        )
        return {row.message_id: row for row in rows.all() if row.message_id}

    async def _require_own_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ) -> tuple[Message, tuple[str, ...]]:
        member_ids = await self._require_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        message = await self._db.get(Message, message_id)
        # A message id from another conversation must read as missing rather
        # than as forbidden, or the error tells the caller it exists.
        if message is None or message.conversation_id != conversation_id:
            raise MessageNotFoundError(message_id)
        if message.sender_id != user_id:
            raise MessageOwnershipError(message_id, user_id)
        return message, tuple(
            member_id for member_id in member_ids if member_id != user_id
        )

    async def submit_translation_feedback(
        self,
        *,
        user_id: str,
        translation_id: str,
        rating: int,
        correction: str | None,
    ) -> Feedback:
        """Record one reader's verdict on a translation, replacing their previous one.

        Args:
            user_id: Account submitting the feedback.
            translation_id: Translation being rated.
            rating: 1 to 5, matching the table's check constraint.
            correction: Suggested replacement text, or None.

        Returns:
            The stored feedback row.

        Raises:
            ConversationValidationError: Rating outside the allowed range.
            TranslationNotFoundError: No translation carries that id.
            ConversationMembershipError: Caller cannot read the rated message.
        """
        if not 1 <= rating <= 5:
            raise ConversationValidationError("rating must be between 1 and 5")

        conversation_id = await self._db.scalar(
            select(Message.conversation_id)
            .join(TranslationResult, TranslationResult.message_id == Message.id)
            .where(TranslationResult.id == translation_id)
        )
        if conversation_id is None:
            raise TranslationNotFoundError(translation_id)

        # Without this, holding a translation_id would be enough to write
        # feedback on a conversation the caller was never part of.
        await self._require_membership(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        existing_feedback = await self._db.scalar(
            select(Feedback).where(
                Feedback.translation_id == translation_id,
                Feedback.user_id == user_id,
            )
        )
        # One vote per reader is enforced here rather than by a unique
        # constraint: adding one to the existing table needs a destructive
        # rebuild (ADR-06), and a changed vote should replace, not accumulate.
        if existing_feedback is not None:
            existing_feedback.rating = rating
            existing_feedback.correction = correction
            feedback = existing_feedback
        else:
            feedback = Feedback(
                translation_id=translation_id,
                user_id=user_id,
                rating=rating,
                correction=correction,
            )
            self._db.add(feedback)

        await self._db.commit()
        await self._db.refresh(feedback)
        return feedback

    async def submit_translation_edit(
        self,
        *,
        user_id: str,
        translation_id: str,
        edited_text: str,
    ) -> tuple[TranslationEdit, TranslationResult, Message]:
        """Store one account's wording for a translation (docs/CONTRACT.md §3.10).

        Appends rather than replaces, unlike `submit_translation_feedback`
        above: an edit that supersedes another is still evidence of what the
        machine got wrong, and the history is the whole point of the table.

        Args:
            user_id: Account writing the edit; the only account that will read it.
            translation_id: Translation being reworded.
            edited_text: The wording this account proposes.

        Returns:
            The stored edit, the translation it belongs to, and the message it
            translates — the caller needs the target language from the second
            and, with consent, the original wording from the third, and both
            are already in hand here rather than worth a second query.

        Raises:
            TranslationNotFoundError: No translation carries that id.
            ConversationMembershipError: Caller is not in that conversation.
            ConversationValidationError: The message has been withdrawn.
        """
        translation = await self._db.get(TranslationResult, translation_id)
        if translation is None:
            raise TranslationNotFoundError(translation_id)

        message = await self._db.get(Message, translation.message_id)
        if message is None:
            raise TranslationNotFoundError(translation_id)

        # Membership rather than "reads this language": the server keeps the
        # same scope the feedback endpoint already uses, and the narrower rule
        # about which controls appear belongs to the client (§3.10).
        await self._require_membership(
            conversation_id=message.conversation_id,
            user_id=user_id,
        )

        if message.deleted_at is not None:
            raise ConversationValidationError(
                "Cannot edit the translation of a withdrawn message"
            )

        edit = TranslationEdit(
            translation_id=translation_id,
            editor_id=user_id,
            edited_text=edited_text,
        )
        self._db.add(edit)
        await self._db.commit()
        await self._db.refresh(edit)
        return edit, translation, message

    async def latest_translation_edits(
        self,
        *,
        translation_ids: list[str],
        editor_id: str,
    ) -> dict[str, TranslationEdit]:
        """One account's newest edit for each of several translations.

        Args:
            translation_ids: Translations being rendered.
            editor_id: Account whose edits are read; never another member's.

        Returns:
            Newest edit per translation id, missing where that account never
            edited.
        """
        if not translation_ids:
            return {}

        rows = await self._db.scalars(
            select(TranslationEdit)
            .where(
                TranslationEdit.translation_id.in_(translation_ids),
                TranslationEdit.editor_id == editor_id,
            )
            .order_by(TranslationEdit.created_at, TranslationEdit.id)
        )
        # Ascending, so the last row for each translation wins. `created_at` is
        # stamped in Python with microsecond precision (see the column), which is
        # what makes "newest" meaningful — the `server_default` beside it renders
        # as SQLite's whole-second CURRENT_TIMESTAMP and would let two quick
        # edits tie. The id only keeps the order deterministic if a row ever does
        # arrive without the Python default, as a raw SQL insert would; it is a
        # random uuid4, so it settles such a tie arbitrarily rather than correctly.
        return {edit.translation_id: edit for edit in rows}

    async def _require_membership(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> tuple[str, ...]:
        conversation = await self._db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)

        member_ids = await self.get_conversation_member_ids(
            conversation_id=conversation_id,
        )
        if user_id not in member_ids:
            raise ConversationMembershipError(conversation_id, user_id)
        return member_ids

    async def _find_message_by_client_message_id(
        self,
        *,
        sender_id: str,
        conversation_id: str,
        client_message_id: str,
    ) -> Message | None:
        return await self._db.scalar(
            select(Message).where(
                Message.sender_id == sender_id,
                Message.conversation_id == conversation_id,
                Message.client_message_id == client_message_id,
            )
        )

    @staticmethod
    def _unique_member_ids(
        creator_id: str,
        member_ids: Sequence[str],
    ) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*member_ids, creator_id)))

    @staticmethod
    def _raise_if_text_conflicts(existing_message: Message, text: str) -> None:
        if existing_message.original_text != text:
            raise ClientMessageIdConflictError(existing_message.client_message_id)

    @staticmethod
    def _validate_conversation_request(
        *,
        creator_id: str,
        conversation_type: ConversationType | str,
        member_ids: Sequence[str],
        title: str | None,
    ) -> None:
        if conversation_type not in {"direct", "group"}:
            raise ConversationValidationError("conversation type must be 'direct' or 'group'")
        if not isinstance(creator_id, str) or not creator_id.strip():
            raise ConversationValidationError("creator_id must be a non-empty string")
        if any(not isinstance(member_id, str) or not member_id.strip() for member_id in member_ids):
            raise ConversationValidationError("member_ids must contain non-empty strings")
        if title is not None and len(title) > 255:
            raise ConversationValidationError("title must be at most 255 characters")

    @classmethod
    def _validate_send_message_request(
        cls,
        *,
        sender_id: str,
        conversation_id: str,
        client_message_id: str,
        text: str,
    ) -> None:
        if not isinstance(sender_id, str) or not sender_id.strip():
            raise ConversationValidationError("sender_id must be a non-empty string")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ConversationValidationError("conversation_id must be a non-empty string")
        if not isinstance(client_message_id, str) or not client_message_id.strip():
            raise ConversationValidationError("client_message_id must be a non-empty string")
        if len(client_message_id) > cls.max_client_message_id_length:
            raise ConversationValidationError(
                "client_message_id must be at most 128 characters"
            )
        if not isinstance(text, str) or not text.strip():
            raise ConversationValidationError("text must not be blank")
        if len(text) > cls.max_message_length:
            raise ConversationValidationError("text must be at most 5000 characters")
