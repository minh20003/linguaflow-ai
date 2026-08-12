"""SQLAlchemy database models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model for authentication and preferences."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Conversation(Base):
    """A durable direct or group chat conversation."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "type IN ('direct', 'group')",
            name="ck_conversations_type",
        ),
        Index("ix_conversations_created_by", "created_by"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConversationMember(Base):
    """A user's membership in a conversation."""

    __tablename__ = "conversation_members"
    __table_args__ = (
        Index("ix_conversation_members_user_id_conversation_id", "user_id", "conversation_id"),
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Message(Base):
    """An original chat message persisted before realtime delivery."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "sender_id",
            "conversation_id",
            "client_message_id",
            name="uq_messages_sender_conversation_client_message",
        ),
        Index("ix_messages_conversation_created_at_id", "conversation_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    client_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Provisional on insert — it is the sender's preferred_language, which says
    # what they usually write in, not what this message is in. The agent's
    # detect_language node overwrites it (docs/CONTRACT.md section 4.3).
    source_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TranslationResult(Base):
    """One message rendered into one target language.

    Members who share a target language share a row, so the `translation_id`
    they each receive is the same — which is what lets F-05 attach feedback to a
    translation rather than to a recipient (docs/CONTRACT.md section 4.4).
    """

    __tablename__ = "translation_results"
    __table_args__ = (
        # Enforces the shared-row rule above in the schema rather than in hope,
        # and makes the background translation task idempotent under retry.
        UniqueConstraint(
            "message_id",
            "target_language",
            name="uq_translation_results_message_target",
        ),
        Index("ix_translation_results_message_id", "message_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_language: Mapped[str] = mapped_column(String(10), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Empty when tier 3 of the fallback chain returned the original untranslated
    # (ARCHITECTURE.md section 5.1).
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # True whenever the text did not come from the configured LLM, including a
    # successful secondary-provider translation.
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Feedback(Base):
    """A reader's correction of a translation (F-05).

    The table exists so `translation_results` has somewhere to point; the
    endpoint and the correction UI are Sprint 2.
    """

    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedbacks_rating"),
        Index("ix_feedbacks_translation_id", "translation_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    translation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("translation_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
