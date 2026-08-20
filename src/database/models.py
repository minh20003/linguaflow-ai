"""SQLAlchemy database models."""

import uuid
from datetime import UTC, datetime

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
    __table_args__ = (
        # A user must always retain at least one authentication provider.
        # Password-less rows are valid only for Google-native accounts.
        CheckConstraint(
            "password_hash IS NOT NULL OR google_sub IS NOT NULL",
            name="ck_users_has_auth_provider",
        ),
    )

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
    username: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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
    # The language of the interface, separate from the one messages are
    # translated into (docs/CONTRACT.md §1.2). Defaults to English because that
    # is the one language the label tables are guaranteed to cover in full, and
    # it is what a stranger sees before they have chosen anything.
    interface_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Google Sign-In subject identifier. It can be explicitly linked in
    # Settings or assigned during Google sign-in identity resolution.
    # Unique: one Google account maps to one LinguaFlow account.
    google_sub: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class RefreshSession(Base):
    """Revocable refresh session stored as a one-way token hash."""

    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PasswordResetToken(Base):
    """Single-use password-reset token stored as a one-way hash."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PendingRegistration(Base):
    """Pending user registration requiring OTP email verification (Batch F)."""

    __tablename__ = "pending_registrations"

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
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )
    interface_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )
    otp_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    rate_window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<PendingRegistration(id={self.id}, email={self.email}, username={self.username})>"


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
    # How far this member has read. Null means they have never opened the
    # conversation, so everything in it counts as unread.
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
    # SET NULL rather than CASCADE: withdrawing a message must not take the
    # replies to it down as well — they are other people's words.
    reply_to_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Removal is soft: `translation_results` and `translation_attempts` reference
    # this row, so deleting it would take the measurement evidence ADR-16 exists
    # to preserve down with it, silently skewing the fallback rate in §3.4.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Attachment(Base):
    """A file uploaded to a conversation, optionally carried by a message.

    `message_id` is nullable because the file is uploaded before the message
    that carries it exists: the client uploads, gets an id back, then sends the
    message referencing it (docs/CONTRACT.md §3.7).
    """

    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_conversation_id", "conversation_id"),
        Index("ix_attachments_message_id", "message_id"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL keeps the stored file reachable for audit if its message goes.
    message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploader_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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


class TranslationEdit(Base):
    """One reader's attempt at a better wording for a translation (F-05).

    Append-only: editing again writes a new row rather than replacing the old
    one, and the row with the newest `created_at` *for that editor* is the one
    in effect. The history behind it is what a later admin feature would read
    to compare human wording against the machine's (docs/CONTRACT.md §3.10).

    Private to its author. Nobody else in the conversation reads these rows,
    which is why `editor_id` cascades: deleting an account deletes notes only
    that account could ever see.
    """

    __tablename__ = "translation_edits"
    __table_args__ = (
        # Ordered the way every read filters: newest edit by one person on one
        # translation, without scanning the rest of the table.
        Index(
            "ix_translation_edits_lookup",
            "translation_id",
            "editor_id",
            "created_at",
        ),
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
    editor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    edited_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Stamped in Python, unlike every other table here, because this is the only
    # column that has to *order* rows rather than just date them: the newest
    # edit is the one in effect. `func.now()` renders as SQLite's
    # CURRENT_TIMESTAMP, which resolves to whole seconds — two saves inside one
    # second tie, and the tie was resolved by primary key, so fixing a typo and
    # saving twice quickly could bring the older wording back.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


# Every way a translation attempt can end. The first three produce a
# `translation_results` row; the last four produce nothing at all, which is
# exactly why this table exists — without them there is no denominator, and a
# "fallback rate" computed only over successes is not a rate of anything.
ATTEMPT_OUTCOMES = (
    "llm",  # the configured LLM translated and the output passed validation
    "secondary",  # deep-translator translated instead (ADR-07 tier 2)
    "original",  # no tier translated, the original text was delivered (tier 3)
    "passthrough",  # source language equalled target, no model was called
    "timeout",  # the run exceeded translation_timeout_seconds
    "error",  # the graph raised
    "empty",  # the graph returned an empty translation
)


class TranslationAttempt(Base):
    """One row per (message, target language) tried, whatever the outcome.

    A measurement log, not application state, and the difference drives the
    schema. `translation_results` holds what readers are shown, so it is unique
    on (message_id, target_language) and carries only the fields the product
    contract exposes. This table is append-only: a retry is a second attempt and
    deserves its own row, so there is no unique constraint, and the columns are
    free to change with what the team wants to measure.

    Writes must never be allowed to fail a translation — see `record_attempt`
    in `src/services/translation.py`, which is the only writer.
    """

    __tablename__ = "translation_attempts"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ({})".format(", ".join(f"'{o}'" for o in ATTEMPT_OUTCOMES)),
            name="ck_translation_attempts_outcome",
        ),
        Index("ix_translation_attempts_created_at", "created_at"),
        Index("ix_translation_attempts_message_id", "message_id"),
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
    # What the sender's profile claimed, known before the run starts.
    source_language_declared: Mapped[str] = mapped_column(String(10), nullable=False)
    # What detection concluded. Null when detection was skipped or failed, so
    # the gap between the two columns is itself measurable (ADR-11).
    source_language_detected: Mapped[str | None] = mapped_column(String(10), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)

    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    model_configured: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # What the provider reported serving, which is not always what was asked
    # for: aliases resolve, and providers reroute under load.
    model_served: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    detect_method: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    finish_reason: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    detect_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    translate_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Wall clock around the whole run, measured in the service layer. Wider than
    # `translation_results.latency_ms`, which covers model time only: this is
    # what the reader waited, and what NFR-01 is about.
    total_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    context_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Machine-readable code, not prose — the log lines stay for humans.
    fallback_reason: Mapped[str] = mapped_column(String(30), nullable=False, default="")

    # SET NULL rather than CASCADE, the opposite of `feedbacks`, and on purpose:
    # deleting a translation must not delete the record that it happened.
    translation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("translation_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
