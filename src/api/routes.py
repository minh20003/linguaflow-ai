"""API routes for the application."""

import logging
import mimetypes
import re
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import get_connection_manager
from src.config import get_settings
from src.core.deps import get_current_user
from src.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from src.database import get_db
from src.database.models import (
    Attachment,
    Conversation,
    Feedback,
    PasswordResetToken,
    RefreshSession,
    TranslationResult,
    User,
)
from src.schemas.auth import (
    SUPPORTED_LANGUAGES,
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateInterfaceLanguageRequest,
    UpdateLanguageRequest,
    UserResponse,
)
from src.schemas.chat import (
    AttachmentResponse,
    ConversationCreateRequest,
    ConversationMemberSummary,
    ConversationResponse,
    EditMessageRequest,
    FeedbackRequest,
    FeedbackResponse,
    MessageDeletedEvent,
    MessageReadEvent,
    MessageResponse,
    MessageUpdatedEvent,
    ReadReceiptResponse,
    TranslationEditRequest,
    TranslationEditResponse,
    TranslationEditSummary,
    TranslationSummary,
)
from src.services.chat import (
    ChatService,
    ChatServiceError,
    ConversationMembershipError,
    ConversationNotFoundError,
    ConversationValidationError,
    MessageAlreadyDeletedError,
    MessageNotFoundError,
    MessageOwnershipError,
    ReferencedUsersNotFoundError,
    TranslationNotFoundError,
)
from src.services.connection_manager import ConnectionManager
from src.services.translation import schedule_translations

logger = logging.getLogger(__name__)

router = APIRouter()

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
_MAX_FILENAME_LENGTH = 120


def _safe_filename(filename: str | None) -> str:
    """Keep a human-readable filename while preventing path traversal."""
    name = Path(filename or "attachment").name
    name = _SAFE_FILENAME.sub("_", name).strip(" ._")
    return (name or "attachment")[:_MAX_FILENAME_LENGTH]


def _attachment_path(conversation_id: str, attachment_id: str) -> Path:
    """Resolve a server generated attachment id to its storage path."""
    root = Path(get_settings().upload_dir).resolve()
    candidate = (root / conversation_id / attachment_id).resolve()
    if root not in candidate.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
    return candidate


# ========================
# Authentication Endpoints
# ========================


async def _issue_auth_response(
    user: User,
    db: AsyncSession,
    *,
    remember: bool,
) -> AuthResponse:
    """Create an access token and a revocable, rotated refresh session."""
    settings = get_settings()
    refresh_token = create_refresh_token()
    refresh_days = settings.refresh_expire_days if remember else 1
    db.add(RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=refresh_days),
    ))
    await db.commit()
    return AuthResponse(
        access_token=create_access_token(subject=user.id),
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Create a durable account and start its first authenticated session."""
    duplicate = await db.execute(
        select(User).where((User.email == request.email) | (User.username == request.username))
    )
    existing = duplicate.scalar_one_or_none()
    if existing is not None:
        detail = "Email is already registered" if existing.email == request.email else "Username is already registered"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    display_name = (request.display_name or request.username).strip()
    user = User(
        email=request.email,
        username=request.username,
        display_name=display_name,
        password_hash=get_password_hash(request.password),
        preferred_language=request.preferred_language,
        # One language question at sign-up, two settings behind it. Someone who
        # picks Japanese wants to read Japanese *and* see a Japanese menu; the
        # two only part company later, if they go and change one of them
        # (docs/CONTRACT.md §1.3).
        interface_language=request.preferred_language,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username is already registered") from exc
    return await _issue_auth_response(user, db, remember=True)


@router.post("/auth/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate user and return JWT token.

    Args:
        request: Login credentials (email and password)
        db: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return await _issue_auth_response(user, db, remember=request.remember)


def _google_profile(credential: str, client_id: str) -> tuple[str, str, str]:
    """Verify a Google ID token and return its immutable identity and profile.

    This is intentionally server-side: accepting a decoded browser JWT without
    verifying its signature/audience would allow anybody to sign in as anyone.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email or not claims.get("email_verified"):
        raise ValueError("Google did not return a verified email address")
    name = str(claims.get("name") or email.split("@", 1)[0]).strip()
    return str(subject), str(email).strip().lower(), name[:100]


def _google_username(email: str, subject: str) -> str:
    """Make a deterministic, valid local username for a new Google account."""
    base = re.sub(r"[^a-z0-9_-]+", "-", email.split("@", 1)[0].lower()).strip("-") or "google-user"
    return f"{base[:40]}-{subject[-8:]}"[:50]


@router.post("/auth/google", response_model=AuthResponse)
async def login_with_google(
    request: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Create or sign in a user after validating a Google ID token."""
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")

    try:
        # Key discovery can make an HTTPS request, so keep the async server
        # event loop responsive while Google's verifier does that work.
        import asyncio
        subject, email, display_name = await asyncio.to_thread(
            _google_profile, request.credential, settings.google_oauth_client_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential") from exc
    except Exception:
        logger.exception("Google token verification failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is temporarily unavailable")

    result = await db.execute(select(User).where(User.google_subject == subject))
    user = result.scalar_one_or_none()
    if user is None:
        # Verified Google ownership of the same email is sufficient to link a
        # password account. It avoids duplicate accounts for the same person.
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            user.google_subject = subject
        else:
            user = User(
                email=email,
                username=_google_username(email, subject),
                display_name=display_name,
                # The schema retains a non-null password hash for legacy email
                # login. A random unknown value means this account cannot be
                # accessed through password login unless a reset flow is added.
                password_hash=get_password_hash(secrets.token_urlsafe(48)),
                google_subject=subject,
            )
            db.add(user)
            try:
                await db.flush()
            except IntegrityError as exc:
                await db.rollback()
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unable to create Google account") from exc

    return await _issue_auth_response(user, db, remember=request.remember)


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_session(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Rotate a valid refresh token and return a fresh authenticated session."""
    result = await db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(request.refresh_token))
    )
    session = result.scalar_one_or_none()
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if session is None or session.revoked_at is not None:
        raise invalid

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        session.revoked_at = datetime.now(UTC)
        await db.commit()
        raise invalid

    user = await db.get(User, session.user_id)
    if user is None:
        raise invalid
    session.revoked_at = datetime.now(UTC)
    return await _issue_auth_response(user, db, remember=(expires_at - datetime.now(UTC)).days > 1)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a browser session. The operation is idempotent."""
    result = await db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(request.refresh_token))
    )
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()


@router.post("/auth/password/forgot", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Create a short-lived reset token without revealing account existence."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    generic = "If the account exists, password reset instructions are ready."
    if user is None:
        return ForgotPasswordResponse(message=generic)

    raw_token = create_refresh_token()
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_expire_minutes),
    ))
    await db.commit()
    # There is no mail provider yet (docs/DEPLOY.md). In development the token
    # comes back in the response so the flow is testable in one screen; anywhere
    # else it goes to the server log only, for an administrator to read out to
    # the person who asked. It is never both — a reset token in an HTTP response
    # is a password anyone who can reach the endpoint may claim.
    if get_settings().app_env == "development":
        return ForgotPasswordResponse(message=generic, reset_token=raw_token)

    logger.warning(
        "Password reset requested for %s. Reset token: %s (valid %s minutes)",
        user.email,
        raw_token,
        get_settings().password_reset_expire_minutes,
    )
    return ForgotPasswordResponse(message=generic)


@router.post("/auth/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Consume a reset token, change the password, and revoke all sessions."""
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_refresh_token(request.token)
        )
    )
    reset = result.scalar_one_or_none()
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    if reset is None or reset.used_at is not None:
        raise invalid
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise invalid
    user = await db.get(User, reset.user_id)
    if user is None:
        raise invalid

    now = datetime.now(UTC)
    user.password_hash = get_password_hash(request.new_password)
    reset.used_at = now
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's information.

    Args:
        current_user: The authenticated user from JWT token

    Returns:
        User information (excludes password hash)
    """
    return UserResponse.model_validate(current_user)


@router.put("/auth/me/language", response_model=UserResponse)
async def update_preferred_language(
    request: UpdateLanguageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the current user's preferred language.

    Args:
        request: New language preference
        current_user: The authenticated user from JWT token
        db: Database session

    Returns:
        Updated user information
    """
    current_user.preferred_language = request.preferred_language
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.put("/auth/me/interface-language", response_model=UserResponse)
async def update_interface_language(
    request: UpdateInterfaceLanguageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the language the interface is drawn in (docs/CONTRACT.md §1.2).

    Deliberately does not touch `preferred_language`. The two are set together
    only once, when the account is created; from then on someone reading
    Japanese messages behind a Vietnamese menu is a choice the product allows.

    Args:
        request: New interface language.
        current_user: The authenticated user from JWT token.
        db: Database session.

    Returns:
        Updated user information.
    """
    current_user.interface_language = request.interface_language
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.get("/languages", response_model=list[str])
async def list_supported_languages() -> list[str]:
    """Return the language codes the system accepts.

    Serving the allowlist is what lets the frontend stop keeping its own copy;
    `SUPPORTED_LANGUAGES` stays the single source of truth (CONTRACT section 1).
    """
    return sorted(SUPPORTED_LANGUAGES)


@router.get("/users", response_model=list[UserResponse])
async def find_users(
    q: str = Query(..., min_length=2, max_length=255),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """Find accounts to start a conversation with (docs/CONTRACT.md §3.1).

    Matches a case-insensitive prefix of the email, the username or the display
    name. Prefix rather than substring: matching anywhere inside the string turns
    this into a way to walk the whole user table one letter at a time, while a
    prefix still finds the person whose name or address the caller is typing.

    `func.lower` rather than `ilike`: SQLite — which the tests run on — applies
    `LIKE` case-insensitively to ASCII only, so `ilike` would agree with
    PostgreSQL on the test data and quietly disagree on real names.

    The caller is excluded: offering someone a conversation with themselves is
    the one result that is never what they meant.

    A list rather than a single object: an empty list is an unambiguous "no such
    account", where a 404 would be confused with a broken route.

    Authentication is required so it is not an anonymous enumeration oracle. It
    remains one for signed-in users, which is accepted at this stage — see the
    rate-limiting note in docs/DEPLOY.md.
    """
    # `%` and `_` are LIKE wildcards, so a query of "%" would otherwise list the
    # whole table — exactly what prefix matching is here to prevent.
    needle = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix = f"{needle}%"
    # A display name is several words, and people search for the one they know:
    # "An" must find "Nguyễn An". Any word may start the match, but no match
    # starts inside a word, so the walk-the-table problem above stays closed.
    word_prefix = f"% {needle}%"
    users = await db.scalars(
        select(User)
        .where(
            User.id != current_user.id,
            or_(
                func.lower(User.email).like(prefix, escape="\\"),
                func.lower(User.username).like(prefix, escape="\\"),
                func.lower(User.display_name).like(prefix, escape="\\"),
                func.lower(User.display_name).like(word_prefix, escape="\\"),
            ),
        )
        .order_by(User.email)
        .limit(20)
    )
    return [UserResponse.model_validate(user) for user in users]


# ========================
# Conversation Endpoints
# ========================


async def _conversation_response(
    service: ChatService,
    conversation: Conversation,
    last_message: tuple[str, datetime] | None = None,
    manager: ConnectionManager | None = None,
    unread_count: int = 0,
    members: Sequence[User] | None = None,
) -> ConversationResponse:
    """Build the minimal conversation representation for an authorized user.

    Args:
        service: Open chat service.
        conversation: Conversation being rendered.
        last_message: Preview text and time, already resolved for the calling
            account. A conversation with no messages passes None.
        manager: Live connection registry, for `online_member_ids`.
        unread_count: Messages this reader has not seen (§3.8).
        members: Already-loaded members. The list endpoint passes them in from
            one batched query; a single-conversation caller lets this load them.

    Returns:
        The conversation as the REST contract defines it (docs/CONTRACT.md §3.5).
    """
    if members is None:
        members = await service.get_conversation_members(conversation_id=conversation.id)
    return ConversationResponse(
        id=conversation.id,
        type=conversation.type,
        title=conversation.title,
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        member_ids=[member.id for member in members],
        members=[ConversationMemberSummary.model_validate(member) for member in members],
        last_message=last_message[0] if last_message else None,
        last_message_at=last_message[1] if last_message else None,
        online_member_ids=list(
            manager.online_user_ids(member.id for member in members)
        ) if manager else [],
        unread_count=unread_count,
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create the minimal direct or group conversation required for chat.

    Asking twice for the same direct conversation is answered with `200` and the
    conversation that already exists, not a second one (docs/CONTRACT.md §3.5).
    """
    service = ChatService(db)
    try:
        result = await service.create_conversation(
            creator_id=current_user.id,
            conversation_type=request.type,
            member_ids=request.member_ids,
            title=request.title,
        )
    except ReferencedUsersNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more referenced users do not exist",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not result.created:
        response.status_code = status.HTTP_200_OK

    return await _conversation_response(service, result.conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> list[ConversationResponse]:
    """List conversations that contain the authenticated user."""
    service = ChatService(db)
    conversations = await service.list_conversations(user_id=current_user.id)
    conversation_ids = [conversation.id for conversation in conversations]
    last_messages = await service.get_last_messages(
        conversation_ids=conversation_ids,
        reader_language=current_user.preferred_language,
    )
    unread = await service.get_unread_counts(
        user_id=current_user.id,
        conversation_ids=conversation_ids,
    )
    members = await service.get_members_by_conversation(conversation_ids=conversation_ids)
    return [
        await _conversation_response(
            service,
            conversation,
            last_messages.get(conversation.id),
            manager,
            unread.get(conversation.id, 0),
            members.get(conversation.id, []),
        )
        for conversation in conversations
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    """Return recent original messages for an authorized conversation member."""
    service = ChatService(db)
    try:
        messages = await service.get_message_history(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=limit,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    live_message_ids = [message.id for message in messages if message.deleted_at is None]
    translations = await _translations_by_message(
        db,
        live_message_ids,
        reader_id=current_user.id,
    )
    attachments = await service.get_attachments_by_message(message_ids=live_message_ids)
    return [
        MessageResponse(
            id=message.id,
            client_message_id=message.client_message_id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            # A withdrawn message keeps its row for the measurement data hanging
            # off it, but its text must not travel anywhere (§3.6).
            original_text="" if message.deleted_at else message.original_text,
            source_language=message.source_language,
            translations=translations.get(message.id, []),
            created_at=message.created_at,
            edited_at=message.edited_at,
            deleted_at=message.deleted_at,
            attachment=(
                AttachmentResponse.model_validate(attachments[message.id])
                if message.id in attachments else None
            ),
            reply_to_message_id=message.reply_to_message_id,
            forwarded_from_message_id=message.forwarded_from_message_id,
        )
        for message in messages
    ]


def _message_error(exc: ChatServiceError) -> HTTPException:
    """Map a message-mutation failure onto its documented status (§3.6)."""
    if isinstance(exc, MessageNotFoundError | ConversationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, MessageOwnershipError | ConversationMembershipError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, MessageAlreadyDeletedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=ReadReceiptResponse,
)
async def mark_conversation_read(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> ReadReceiptResponse:
    """Mark everything in a conversation as read by the caller (§3.8).

    Other members are told so their own copy of the thread can show the message
    as seen rather than merely delivered.
    """
    service = ChatService(db)
    try:
        read_at = await service.mark_conversation_read(
            user_id=current_user.id,
            conversation_id=conversation_id,
        )
        member_ids = await service.get_conversation_member_ids(
            conversation_id=conversation_id,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    await manager.send_to_users(
        tuple(member_id for member_id in member_ids if member_id != current_user.id),
        MessageReadEvent(
            conversation_id=conversation_id,
            user_id=current_user.id,
            read_at=read_at,
        ).model_dump(mode="json"),
    )
    return ReadReceiptResponse()


@router.patch(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=MessageResponse,
)
async def edit_message(
    conversation_id: str,
    message_id: str,
    payload: EditMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> MessageResponse:
    """Replace the text of a message the caller sent (F-06).

    The previous translations are discarded and the message is translated again
    in the background, because a translation of retracted text is worse than no
    translation at all.
    """
    service = ChatService(db)
    try:
        message, recipient_ids = await service.edit_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
            text=payload.text,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    await manager.send_to_users(
        recipient_ids,
        MessageUpdatedEvent(
            message_id=message.id,
            conversation_id=message.conversation_id,
            original_text=message.original_text,
            edited_at=message.edited_at,
        ).model_dump(mode="json"),
    )
    schedule_translations(message=message, publisher=manager)

    return MessageResponse(
        id=message.id,
        client_message_id=message.client_message_id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        original_text=message.original_text,
        source_language=message.source_language,
        translations=[],
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
    )


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_message(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    """Withdraw a message the caller sent, keeping its row (F-06)."""
    service = ChatService(db)
    try:
        message, recipient_ids = await service.delete_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    await manager.send_to_users(
        recipient_ids,
        MessageDeletedEvent(
            message_id=message.id,
            conversation_id=message.conversation_id,
            deleted_at=message.deleted_at,
        ).model_dump(mode="json"),
    )


@router.post(
    "/translations/{translation_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_translation_feedback(
    translation_id: str,
    payload: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Record the authenticated reader's rating and optional correction (F-05).

    Re-submitting replaces that reader's previous verdict on the same
    translation rather than adding a second row.
    """
    service = ChatService(db)
    try:
        feedback = await service.submit_translation_feedback(
            user_id=current_user.id,
            translation_id=translation_id,
            rating=payload.rating,
            correction=payload.correction,
        )
    except TranslationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return FeedbackResponse(feedback_id=feedback.id)


@router.post(
    "/translations/{translation_id}/edits",
    response_model=TranslationEditResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_translation_edit(
    translation_id: str,
    payload: TranslationEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranslationEditResponse:
    """Store the caller's own wording for a translation (docs/CONTRACT.md §3.10).

    Each call appends, so editing again keeps the earlier attempt. The text is
    private to its author and no WebSocket event follows: nobody else's screen
    changes because of it.
    """
    service = ChatService(db)
    try:
        edit, translation = await service.submit_translation_edit(
            user_id=current_user.id,
            translation_id=translation_id,
            edited_text=payload.edited_text,
        )
    except TranslationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        # A withdrawn message, which is a conflict with the message's state
        # rather than a malformed request — same code §3.6 uses for editing one.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return TranslationEditResponse(
        edit_id=edit.id,
        translation_id=translation.id,
        message_id=translation.message_id,
        target_language=translation.target_language,
        edited_text=edit.edited_text,
        edited_at=edit.created_at,
    )


async def _translations_by_message(
    db: AsyncSession,
    message_ids: list[str],
    reader_id: str,
) -> dict[str, list[TranslationSummary]]:
    """Load every translation for a page of messages in one query.

    History is how a client recovers translations it missed while disconnected,
    so this is what keeps a socket dropping mid-translation from losing data.
    Each summary also carries `reader_id`'s own feedback, which is what lets a
    rating button still look rated after a reload.

    Args:
        db: Open session.
        message_ids: Messages whose translations are being rendered.
        reader_id: Account whose feedback is attached; never another member's.

    Returns:
        Translations grouped by message id, in no guaranteed order.
    """
    if not message_ids:
        return {}

    rows = list(
        (
            await db.scalars(
                select(TranslationResult).where(
                    TranslationResult.message_id.in_(message_ids)
                )
            )
        ).all()
    )

    my_feedback = {
        feedback.translation_id: feedback
        for feedback in (
            await db.scalars(
                select(Feedback).where(
                    Feedback.user_id == reader_id,
                    Feedback.translation_id.in_([row.id for row in rows]),
                )
            )
        ).all()
    }

    # The caller's own edits only. Loaded here rather than joined above so the
    # privacy rule is visible in one place: this dict is keyed by translation
    # and filtered by reader, and nothing else ever reaches these rows (§3.10).
    my_edits = await ChatService(db).latest_translation_edits(
        translation_ids=[row.id for row in rows],
        editor_id=reader_id,
    )

    grouped: dict[str, list[TranslationSummary]] = {}
    for row in rows:
        feedback = my_feedback.get(row.id)
        edit = my_edits.get(row.id)
        grouped.setdefault(row.message_id, []).append(
            # Built field by field rather than validated from the ORM object:
            # the row's primary key is `id`, and the client needs it under the
            # name `translation_id` so F-05 can attach feedback to it
            # (docs/CONTRACT.md section 4.4). `from_attributes` cannot rename.
            TranslationSummary(
                translation_id=row.id,
                target_language=row.target_language,
                translated_text=row.translated_text,
                model=row.model,
                latency_ms=row.latency_ms,
                is_fallback=row.is_fallback,
                my_rating=feedback.rating if feedback else None,
                my_correction=feedback.correction if feedback else None,
                my_edit=TranslationEditSummary(
                    edit_id=edit.id,
                    edited_text=edit.edited_text,
                    edited_at=edit.created_at,
                ) if edit else None,
            )
        )
    return grouped


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_conversation_attachment(
    conversation_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    """Upload one file for a conversation the current user belongs to.

    Files are stored outside public static paths. A download requires the same
    conversation-membership check, so knowing a URL never grants access.
    """
    service = ChatService(db)
    try:
        await service.get_message_history(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=1,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation was not found") from exc
    except ConversationMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this conversation") from exc
    except ConversationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    attachment_id = f"{uuid.uuid4().hex}_{_safe_filename(file.filename)}"
    destination = _attachment_path(conversation_id, attachment_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Attachment exceeds the 20 MB limit",
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    # Persisted so a message can claim it later; until then the row is an
    # unattached upload, which is a normal state (docs/CONTRACT.md §3.7).
    attachment = Attachment(
        id=attachment_id,
        conversation_id=conversation_id,
        uploader_id=current_user.id,
        filename=_safe_filename(file.filename),
        content_type=content_type,
        size=written,
    )
    db.add(attachment)
    await db.commit()

    return AttachmentResponse.model_validate(attachment)


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}")
async def download_conversation_attachment(
    conversation_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download an attachment after verifying conversation membership."""
    service = ChatService(db)
    try:
        await service.get_message_history(user_id=current_user.id, conversation_id=conversation_id, limit=1)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation was not found") from exc
    except ConversationMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this conversation") from exc
    except ConversationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    path = _attachment_path(conversation_id, attachment_id)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
    return FileResponse(path, filename=path.name.split("_", 1)[-1], media_type=mimetypes.guess_type(path.name)[0])

