"""Test fixtures and configuration."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes import router as api_router
from src.api.websocket import get_connection_manager
from src.api.websocket import router as websocket_router
from src.core.security import create_access_token, get_password_hash
from src.database import get_db
from src.database.models import Base, Conversation, ConversationMember, User
from src.services.connection_manager import ConnectionManager

# ========================
# Test Database Setup
# ========================

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

test_async_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database for each test function.

    Uses an in-memory SQLite database that is created fresh for each test.
    """
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide a session
    async with test_async_session_maker() as session:
        yield session

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test member user."""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        role="member",
        preferred_language="en",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(test_db: AsyncSession) -> User:
    """Create a test admin user."""
    user = User(
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword"),
        role="admin",
        preferred_language="vi",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_two(test_db: AsyncSession) -> User:
    """Create a second member used for direct-chat delivery tests."""
    user = User(
        email="second@example.com",
        password_hash=get_password_hash("secondpassword"),
        role="member",
        preferred_language="vi",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_three(test_db: AsyncSession) -> User:
    """Create a third member used for group-chat delivery tests."""
    user = User(
        email="third@example.com",
        password_hash=get_password_hash("thirdpassword"),
        role="member",
        preferred_language="ja",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def conversation_factory(test_db: AsyncSession):
    """Create a durable test conversation with the supplied members."""

    async def create(
        creator: User,
        members: list[User],
        conversation_type: str = "direct",
        title: str | None = None,
    ) -> Conversation:
        unique_member_ids = list(dict.fromkeys([*(member.id for member in members), creator.id]))
        conversation = Conversation(
            type=conversation_type,
            title=title,
            created_by=creator.id,
        )
        test_db.add(conversation)
        await test_db.flush()
        test_db.add_all(
            [
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=user_id,
                )
                for user_id in unique_member_ids
            ]
        )
        await test_db.commit()
        await test_db.refresh(conversation)
        return conversation

    return create


def auth_headers_for_user(user: User) -> dict[str, str]:
    """Generate authorization headers for a user."""
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user_headers(test_user: User) -> dict[str, str]:
    """Authorization headers for test_user."""
    return auth_headers_for_user(test_user)


@pytest.fixture
def test_admin_headers(test_admin: User) -> dict[str, str]:
    """Authorization headers for test_admin."""
    return auth_headers_for_user(test_admin)


# ========================
# App Client Setup
# ========================

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing API endpoints."""
    # Override the database dependency to use test database
    from src.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def ws_client() -> AsyncGenerator[tuple[TestClient, ConnectionManager], None]:
    """Provide a no-lifespan WebSocket app backed by the test database."""
    ws_app = FastAPI()
    ws_app.include_router(api_router, prefix="/api/v1")
    ws_app.include_router(websocket_router, prefix="/api/v1")
    manager = ConnectionManager()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    ws_app.dependency_overrides[get_db] = override_get_db
    ws_app.dependency_overrides[get_connection_manager] = lambda: manager

    with TestClient(ws_app) as test_client:
        yield test_client, manager

    ws_app.dependency_overrides.clear()


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
