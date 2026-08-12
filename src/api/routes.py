"""API routes for the application."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user
from src.core.security import create_access_token, get_password_hash, verify_password
from src.database import get_db
from src.database.models import Conversation, TranslationResult, User
from src.schemas.auth import (
    SUPPORTED_LANGUAGES,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateLanguageRequest,
    UserResponse,
    normalize_email,
)
from src.schemas.chat import (
    ConversationCreateRequest,
    ConversationMemberSummary,
    ConversationResponse,
    MessageResponse,
    TranslationSummary,
)
from src.services.chat import (
    ChatService,
    ConversationMembershipError,
    ConversationNotFoundError,
    ConversationValidationError,
    ReferencedUsersNotFoundError,
)

router = APIRouter()


# ========================
# Authentication Endpoints
# ========================


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create an account and return a token for it.

    Returns the same shape as login rather than the user, because the client
    lands straight in the chat after registering and needs a usable session.

    `preferred_language` is set here, not afterwards: it is the language the
    account will read messages in, and asking for it later would leave the
    first messages untranslated.

    Args:
        request: Email, password and the language to read in
        db: Database session

    Returns:
        JWT access token for the new account

    Raises:
        HTTPException: 409 if the email is already registered
    """
    existing = await db.scalar(select(User).where(User.email == request.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        # Never read from the request body — a client must not grant itself a role.
        role="member",
        preferred_language=request.preferred_language,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # The check above is a TOCTOU race; the unique index is the real guard.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc

    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(subject=user.id))


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
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

    # Create access token with user ID as subject
    access_token = create_access_token(subject=user.id)

    return TokenResponse(access_token=access_token)


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
    members = await service.get_conversation_members(conversation_id=conversation.id)
    return ConversationResponse(
        id=conversation.id,
        type=conversation.type,
        title=conversation.title,
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        member_ids=[member.id for member in members],
        members=[ConversationMemberSummary.model_validate(member) for member in members],
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

    translations = await _translations_by_message(db, [message.id for message in messages])
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


async def _translations_by_message(
    db: AsyncSession,
    message_ids: list[str],
) -> dict[str, list[TranslationSummary]]:
    """Load every translation for a page of messages in one query.

    History is how a client recovers translations it missed while disconnected,
    so this is what keeps a socket dropping mid-translation from losing data.
    """
    if not message_ids:
        return {}

    rows = await db.scalars(
        select(TranslationResult).where(TranslationResult.message_id.in_(message_ids))
    )

    grouped: dict[str, list[TranslationSummary]] = {}
    for row in rows:
        grouped.setdefault(row.message_id, []).append(
            TranslationSummary(
                translation_id=row.id,
                target_language=row.target_language,
                translated_text=row.translated_text,
                model=row.model,
                latency_ms=row.latency_ms,
                is_fallback=row.is_fallback,
            )
        )
    return grouped


