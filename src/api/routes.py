"""API routes for the application."""

import mimetypes
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateLanguageRequest,
    UserResponse,
    normalize_email,
)
from src.schemas.chat import (
    AttachmentResponse,
    ConversationCreateRequest,
    ConversationResponse,
    FeedbackRequest,
    FeedbackResponse,
    MessageResponse,
    TranslationSummary,
)
from src.services.chat import (
    ChatService,
    ConversationMembershipError,
    ConversationNotFoundError,
    ConversationValidationError,
    ReferencedUsersNotFoundError,
    TranslationNotFoundError,
)

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
    # Local development has no mail provider. Returning this only in development
    # keeps the flow testable; production never exposes reset credentials.
    visible_token = raw_token if get_settings().app_env == "development" else None
    return ForgotPasswordResponse(message=generic, reset_token=visible_token)


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


@router.get("/languages", response_model=list[str])
async def list_supported_languages() -> list[str]:
    """Return the language codes the system accepts.

    Serving the allowlist is what lets the frontend stop keeping its own copy;
    `SUPPORTED_LANGUAGES` stays the single source of truth (CONTRACT section 1).
    """
    return sorted(SUPPORTED_LANGUAGES)


@router.get("/users", response_model=list[UserResponse])
async def find_users(
    email: str = Query(..., min_length=3, max_length=255),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """Look up an account by exact email, for adding members to a conversation.

    A list rather than a single object: an empty list is an unambiguous "no such
    account", where a 404 would be confused with a broken route. Exact match
    only — this is a resolver for a known address, not a directory search.

    Authentication is required so it is not an anonymous enumeration oracle. It
    remains one for signed-in users, which is accepted at this stage.
    """
    user = await db.scalar(select(User).where(User.email == normalize_email(email)))
    return [UserResponse.model_validate(user)] if user is not None else []


# ========================
# Conversation Endpoints
# ========================


async def _conversation_response(
    service: ChatService,
    conversation: Conversation,
) -> ConversationResponse:
    """Build the minimal conversation representation for an authorized user."""
    member_ids = await service.get_conversation_member_ids(
        conversation_id=conversation.id,
    )
    return ConversationResponse(
        id=conversation.id,
        type=conversation.type,
        title=conversation.title,
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        member_ids=list(member_ids),
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create the minimal direct or group conversation required for chat."""
    service = ChatService(db)
    try:
        conversation = await service.create_conversation(
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

    return await _conversation_response(service, conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    """List conversations that contain the authenticated user."""
    service = ChatService(db)
    conversations = await service.list_conversations(user_id=current_user.id)
    return [
        await _conversation_response(service, conversation)
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

    translations = await _translations_by_message(
        db,
        [message.id for message in messages],
        reader_id=current_user.id,
    )
    return [
        MessageResponse(
            id=message.id,
            client_message_id=message.client_message_id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            original_text=message.original_text,
            source_language=message.source_language,
            translations=translations.get(message.id, []),
            created_at=message.created_at,
        )
        for message in messages
    ]


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

    grouped: dict[str, list[TranslationSummary]] = {}
    for row in rows:
        feedback = my_feedback.get(row.id)
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
    return AttachmentResponse(
        id=attachment_id,
        conversation_id=conversation_id,
        filename=_safe_filename(file.filename),
        content_type=content_type,
        size=written,
        download_url=f"/api/v1/conversations/{conversation_id}/attachments/{attachment_id}",
    )


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

