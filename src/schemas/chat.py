"""Pydantic schemas for the durable chat and WebSocket contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ConversationType = Literal["direct", "group"]


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


class ConversationResponse(BaseModel):
    """Conversation metadata returned to an authenticated member."""

    id: str
    type: ConversationType
    title: str | None
    created_by: str
    created_at: datetime
    member_ids: list[str]


class MessageResponse(BaseModel):
    """Persisted message representation used by REST history."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    client_message_id: str
    conversation_id: str
    sender_id: str
    original_text: str
    created_at: datetime


class AttachmentResponse(BaseModel):
    """Metadata returned after an authorized conversation file upload."""

    id: str
    conversation_id: str
    filename: str
    content_type: str
    size: int
    download_url: str


class RealtimeMessage(BaseModel):
    """Canonical message data included in WebSocket delivery events."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_id: str
    original_text: str
    created_at: datetime


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


class ErrorEvent(BaseModel):
    """Structured non-fatal WebSocket application error."""

    type: Literal["error"] = "error"
    code: str
    message: str
