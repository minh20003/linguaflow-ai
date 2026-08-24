"""Pydantic schemas for the durable chat and WebSocket contracts."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    computed_field,
    field_validator,
    model_validator,
)

from src.schemas.auth import fallback_profile_names

ConversationType = Literal["direct", "group"]


def _utc_isoformat(value: datetime) -> str:
    """Render a timestamp as UTC with an explicit designator.

    SQLite hands back naive datetimes even though the columns declare
    `timezone=True`, and a naive string is read by `new Date()` in the browser as
    *local* time — which silently backdated every timestamp by the reader's UTC
    offset and made a message just sent read as "7 giờ" ago. The contract has
    always specified the `Z` form (docs/CONTRACT.md §3.2); this enforces it.
    """
    moment = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return moment.isoformat().replace("+00:00", "Z")


# Every timestamp crossing the API boundary, so no caller has to guess a zone.
UtcDatetime = Annotated[datetime, PlainSerializer(_utc_isoformat, return_type=str)]


class ConversationCreateRequest(BaseModel):
    """Minimal authenticated request for creating a conversation."""

    model_config = ConfigDict(extra="forbid")

    type: ConversationType
    member_ids: list[str] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=255)

    @field_validator("member_ids")
    @classmethod
    def member_ids_must_not_contain_blank_values(cls, value: list[str]) -> list[str]:
        """Reject empty user IDs while allowing the service to deduplicate IDs."""
        if any(not member_id.strip() for member_id in value):
            raise ValueError("member_ids must not contain blank values")
        return value


class GroupMembersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_ids: list[str] = Field(min_length=1)


class GroupRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "member"]


class GroupTransferOwnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1)


class GroupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Group name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ConversationMemberSummary(BaseModel):
    """Enough about a member to render them and to know what they read."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    # Carried so a conversation can be labelled with a person's name. Without
    # them the client can only cut the email at the `@`, which stops being a
    # name the moment two accounts share a local part.
    username: str | None = None
    display_name: str | None = None
    preferred_language: str
    group_role: Literal["owner", "admin", "member"] = "member"
    # The standing this member holds in *this* conversation, which is why it
    # cannot be validated straight off the User row: the same account is a
    # junior colleague in one thread and a client in another.
    #
    # Required rather than defaulted, and deliberately so. A default here would
    # be a second place the neutral standing is written down, and it would let a
    # caller that forgot to resolve profiles serialise a plausible-looking
    # `peer` for everyone. The resolver owns that default (`profile_for`); this
    # layer only reports what it was given.
    honorific_profile: str

    @model_validator(mode="after")
    def fill_legacy_profile_names(self) -> "ConversationMemberSummary":
        """Apply the same fallback as UserDTO, so one member never renders blank."""
        self.username, self.display_name = fallback_profile_names(
            self.email, self.username, self.display_name
        )
        return self


class ConversationResponse(BaseModel):
    """Conversation metadata returned to an authenticated member."""

    id: str
    type: ConversationType
    title: str | None
    description: str | None = None
    created_by: str
    created_at: UtcDatetime
    member_ids: list[str]
    # `member_ids` alone leaves a direct conversation with no name to show and
    # every incoming message unattributed. Both are kept: the id list is what
    # existing clients read.
    members: list[ConversationMemberSummary] = []
    # The newest message, in the calling account's own language where a
    # translation exists — a preview nobody can read identifies nothing
    # (docs/CONTRACT.md §3.5). Null until the conversation has a message.
    last_message: str | None = None
    last_message_at: UtcDatetime | None = None
    # Members holding a live socket right now, read from the in-process
    # connection registry rather than from storage (docs/CONTRACT.md §3.5).
    online_member_ids: list[str] = []
    # Messages from other people newer than this reader's last_read_at (§3.8).
    unread_count: int = 0


class TranslationEditSummary(BaseModel):
    """The caller's newest wording for one translation (docs/CONTRACT.md §3.10).

    Carries no editor field: an account only ever reads its own edits, so the
    author is always whoever asked.
    """

    model_config = ConfigDict(from_attributes=True)

    edit_id: str
    edited_text: str
    edited_at: UtcDatetime


class TranslationSummary(BaseModel):
    """One rendered translation attached to a message in REST history."""

    model_config = ConfigDict(from_attributes=True)

    translation_id: str
    target_language: str
    # Which standing this wording addresses the reader with. Carried so a client
    # holding several translations of one message can tell them apart: after
    # `honorific_profile` joined the unique key, `target_language` alone no
    # longer identifies a row (docs/CONTRACT.md section 5, note 6).
    honorific_profile: str
    translated_text: str
    model: str
    latency_ms: int
    is_fallback: bool
    # The requesting account's own feedback, so a vote survives a page reload.
    # Per-caller data: never shared between accounts (docs/CONTRACT.md §3.2).
    my_rating: int | None = None
    my_correction: str | None = None
    my_edit: TranslationEditSummary | None = None


class AttachmentResponse(BaseModel):
    """Metadata for a stored conversation file (docs/CONTRACT.md §3.7)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    filename: str
    content_type: str
    size: int
    created_at: datetime

    @computed_field
    @property
    def download_url(self) -> str:
        """Where to fetch the bytes.

        Derived rather than stored so every caller spells the path the same way;
        the REST layer and the socket layer would otherwise each build their own,
        and only one of them could stay right.
        """
        return f"/api/v1/conversations/{self.conversation_id}/attachments/{self.id}"


class MentionSummary(BaseModel):
    """A durable mention target, validated server-side against the thread."""

    type: Literal["user", "assistant"]
    user_id: str | None = None


class MessageResponse(BaseModel):
    """Persisted message representation used by REST history."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    client_message_id: str
    conversation_id: str
    sender_id: str
    original_text: str
    source_language: str
    mentions: list[MentionSummary] = []
    assistant_generated: bool = False
    # Carrying translations here is what makes a socket that dropped mid
    # translation a non-event: the client recovers them on reconnect rather
    # than waiting for a `translation_completed` that was already sent.
    translations: list[TranslationSummary] = []
    created_at: UtcDatetime
    # Null until the sender edits or removes the message (docs/CONTRACT.md §3.6).
    edited_at: UtcDatetime | None = None
    deleted_at: UtcDatetime | None = None
    # The file this message carries, and the message it answers (§3.7).
    attachment: AttachmentResponse | None = None
    reply_to_message_id: str | None = None
    forwarded_from_message_id: str | None = None


class EditMessageRequest(BaseModel):
    """New text for a message its sender is correcting (F-06)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        """Reject a whitespace-only edit rather than blanking the message.

        Clearing a message is what DELETE is for, and it records `deleted_at`
        so the thread can say the message was withdrawn.
        """
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class FeedbackRequest(BaseModel):
    """A reader's verdict on one translation (F-05).

    The UI offers a thumbs pair rather than five stars, so it sends the extremes
    of the range the `feedbacks` table already constrains: 5 for up, 1 for down.
    Keeping the column as-is is what lets this ship without a schema migration.
    """

    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    correction: str | None = Field(default=None, max_length=5000)

    @field_validator("correction")
    @classmethod
    def correction_must_not_be_blank(cls, value: str | None) -> str | None:
        """Store a missing correction as null rather than as whitespace."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class FeedbackResponse(BaseModel):
    """Identifier of the stored feedback row."""

    feedback_id: str


class TranslationEditRequest(BaseModel):
    """A better wording for one translation (F-05, docs/CONTRACT.md §3.10).

    Deliberately not a patch of `translation_results.translated_text`: the
    machine's output stays where it is so the two can be compared later, and
    this text is stored beside it.
    """

    model_config = ConfigDict(extra="forbid")

    edited_text: str = Field(min_length=1, max_length=5000)
    # Whether this wording may be used to improve the system. Defaults to false
    # and has to be asked for explicitly: ADR-19 made these rows private to
    # their author, and consent is what makes a derived record of one legitimate
    # rather than an exception to that rule (docs/NewFeature.md 3.1, option A).
    consent_to_share: bool = False

    @field_validator("edited_text")
    @classmethod
    def edited_text_must_not_be_blank(cls, value: str) -> str:
        """Reject whitespace, which would read as "cleared" but store as set."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("edited_text must not be blank")
        return cleaned


class TranslationEditResponse(BaseModel):
    """The stored edit, echoed back so the client can show it immediately."""

    edit_id: str
    translation_id: str
    message_id: str
    target_language: str
    # Same reason as on TranslationSummary: the pair, not the language alone,
    # names the translation this edit was written against.
    honorific_profile: str
    edited_text: str
    edited_at: UtcDatetime


class ReadReceiptResponse(BaseModel):
    """State after marking a conversation read (docs/CONTRACT.md §3.8)."""

    unread_count: int = 0


class MessageReadEvent(BaseModel):
    """WebSocket event telling senders their message has been seen."""

    type: Literal["message_read"] = "message_read"
    conversation_id: str
    user_id: str
    read_at: UtcDatetime


class RealtimeMessage(BaseModel):
    """Canonical message data included in WebSocket delivery events."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_id: str
    original_text: str
    created_at: UtcDatetime
    mentions: list[MentionSummary] = []
    assistant_generated: bool = False
    # Carried live so a recipient renders the quote and the file without
    # refetching history (docs/CONTRACT.md §3.7).
    reply_to_message_id: str | None = None
    forwarded_from_message_id: str | None = None
    attachment: AttachmentResponse | None = None


class AuthEvent(BaseModel):
    """Initial WebSocket authentication frame."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["auth"]
    token: str = Field(min_length=1)


class SendMessageEvent(BaseModel):
    """Authenticated WebSocket event for sending an original message."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["send_message"]
    client_message_id: str = Field(min_length=1, max_length=128)
    conversation_id: str = Field(min_length=1, max_length=36)
    text: str = Field(min_length=1, max_length=5000)
    # Both optional: a plain message carries neither (docs/CONTRACT.md §4.1).
    attachment_id: str | None = Field(default=None, max_length=255)
    reply_to_message_id: str | None = Field(default=None, max_length=36)
    forwarded_from_message_id: str | None = Field(default=None, max_length=36)
    mentions: list[MentionSummary] = []

    @field_validator("client_message_id", "conversation_id")
    @classmethod
    def identifiers_must_not_be_blank(cls, value: str) -> str:
        """Reject identifiers consisting only of whitespace."""
        if not value.strip():
            raise ValueError("identifier must not be blank")
        return value

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        """Reject whitespace-only messages without changing persisted text."""
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class TypingEvent(BaseModel):
    """Client-side notice that someone started or stopped composing."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["typing"]
    conversation_id: str = Field(min_length=1, max_length=36)
    is_typing: bool


class TypingNotificationEvent(BaseModel):
    """Server-side relay of `typing` to the other members of a conversation."""

    type: Literal["typing"] = "typing"
    conversation_id: str
    user_id: str
    is_typing: bool


class AuthOkEvent(BaseModel):
    """WebSocket event confirming authentication."""

    type: Literal["auth_ok"] = "auth_ok"
    user_id: str


class MessageCreatedEvent(BaseModel):
    """WebSocket acknowledgement for a sender's newly persisted message."""

    type: Literal["message_created"] = "message_created"
    client_message_id: str
    message: RealtimeMessage


class MessageReceivedEvent(BaseModel):
    """WebSocket delivery event for other conversation members."""

    type: Literal["message_received"] = "message_received"
    message: RealtimeMessage


class MentionNotificationEvent(BaseModel):
    """Realtime cue for a member explicitly tagged in a message."""

    type: Literal["mention"] = "mention"
    message_id: str
    conversation_id: str
    sender_id: str


class TranslationCompletedEvent(BaseModel):
    """WebSocket delivery event for a finished translation.

    Addressed at fan-out to the members of one bucket — those who share a
    `preferred_language` *and* a standing — rather than broadcast for the client
    to filter (docs/CONTRACT.md section 4.4).

    That addressing is not on its own enough to identify the row, which is why
    `honorific_profile` is on the payload. A sender in a `direct` conversation
    receives the translation meant for the other person as well as their own, so
    that the rating and edit controls can sit under their own message (ADR-19),
    and with a widened key `target_language` no longer tells those two apart.

    `conversation_id` is carried explicitly because a per-user socket gives the
    client no other way to route this event to the right thread.
    """

    type: Literal["translation_completed"] = "translation_completed"
    message_id: str
    conversation_id: str
    translation_id: str
    source_language: str
    target_language: str
    honorific_profile: str
    translated_text: str
    model: str
    latency_ms: int
    is_fallback: bool


class MessageUpdatedEvent(BaseModel):
    """WebSocket event for a message whose sender changed its text (F-06).

    Carries only what changed. The retranslation that follows arrives as an
    ordinary `translation_completed`, so clients need no second code path
    (docs/CONTRACT.md §4.2).
    """

    type: Literal["message_updated"] = "message_updated"
    message_id: str
    conversation_id: str
    original_text: str
    edited_at: UtcDatetime


class MessageDeletedEvent(BaseModel):
    """WebSocket event for a message its sender withdrew (F-06)."""

    type: Literal["message_deleted"] = "message_deleted"
    message_id: str
    conversation_id: str
    deleted_at: UtcDatetime


class ErrorEvent(BaseModel):
    """Structured non-fatal WebSocket application error."""

    type: Literal["error"] = "error"
    code: str
    message: str
