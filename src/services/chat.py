"""Business logic for durable conversations and original chat messages."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Conversation, ConversationMember, Message, User
from src.schemas.chat import ConversationType


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


class ClientMessageIdConflictError(ChatServiceError):
    """Raised when an idempotency key is reused with different message text."""

    def __init__(self, client_message_id: str) -> None:
        self.client_message_id = client_message_id
        super().__init__("client_message_id was already used with different text")


class ConversationValidationError(ChatServiceError):
    """Raised when a conversation or message violates a domain rule."""


class ReferencedUsersNotFoundError(ChatServiceError):
    """Raised when a conversation request references missing users."""

    def __init__(self, missing_user_ids: Sequence[str]) -> None:
        self.missing_user_ids = tuple(missing_user_ids)
        super().__init__("One or more referenced users do not exist")


@dataclass(frozen=True, slots=True)
class SendMessageResult:
    """Canonical persisted message and eligible realtime recipients."""

    message: Message
    recipient_ids: tuple[str, ...]
    created: bool


class ChatService:
    """Encapsulate chat authorization, persistence, and idempotency rules."""

    max_message_length = 5000
    max_client_message_id_length = 128

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_conversation(
        self,
        *,
        creator_id: str,
        conversation_type: ConversationType | str,
        member_ids: Sequence[str],
        title: str | None = None,
    ) -> Conversation:
        """Create a direct or group conversation with validated membership."""
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
                )
                for user_id in unique_member_ids
            ]
        )
        await self._db.flush()
        await self._db.refresh(conversation)
        return conversation

    async def list_conversations(self, *, user_id: str) -> list[Conversation]:
        """List conversations the supplied user belongs to in stable order."""
        result = await self._db.scalars(
            select(Conversation)
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Conversation.id,
            )
            .where(ConversationMember.user_id == user_id)
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        )
        return list(result.all())

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

    async def send_message(
        self,
        *,
        sender_id: str,
        conversation_id: str,
        client_message_id: str,
        text: str,
    ) -> SendMessageResult:
        """Persist an authorized original message before any transport fan-out."""
        self._validate_send_message_request(
            sender_id=sender_id,
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            text=text,
        )

        member_ids = await self._require_membership(
            conversation_id=conversation_id,
            user_id=sender_id,
        )
        recipient_ids = tuple(
            member_id for member_id in member_ids if member_id != sender_id
        )

        existing_message = await self._find_message_by_client_message_id(
            sender_id=sender_id,
            conversation_id=conversation_id,
            client_message_id=client_message_id,
        )
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

        await self._db.refresh(message)
        # ``refresh`` starts a new read transaction; close it before transport
        # fan-out so an idle WebSocket does not retain a database transaction.
        await self._db.commit()
        return SendMessageResult(
            message=message,
            recipient_ids=recipient_ids,
            created=True,
        )

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
