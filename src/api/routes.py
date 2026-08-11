"""API routes for the application."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import agent
from src.core.deps import get_current_user
from src.core.security import create_access_token, verify_password
from src.database import get_db
from src.database.models import User
from src.models.schemas import ChatRequest, ChatResponse
from src.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UpdateLanguageRequest,
    UserResponse,
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
