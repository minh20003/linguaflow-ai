"""API routes for the application."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import agent
from src.core.deps import get_current_user
from src.core.security import create_access_token, verify_password
from src.database import get_db
from src.database.models import Conversation, User
from src.models.schemas import ChatRequest, ChatResponse
from src.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UpdateLanguageRequest,
    UserResponse,
)
from src.schemas.chat import (
    ConversationCreateRequest,
    ConversationResponse,
    MessageResponse,
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

    return [MessageResponse.model_validate(message) for message in messages]


# ========================
# Legacy Chat Endpoints
# ========================


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat với AI agent."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
