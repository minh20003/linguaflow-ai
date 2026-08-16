"""Test fixtures and configuration."""

from __future__ import annotations

import asyncio
import os
import tempfile
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
from src.services import translation as translation_module
from src.services.connection_manager import ConnectionManager

# ========================
# Test Database Setup
# ========================

# These are initialized in test_db fixture, after the temp file is created.
# Exported for tests that need to verify DB state with a separate session.
# Use these names consistently throughout.
test_engine: create_async_engine | None = None
test_async_session_maker: async_sessionmaker | None = None

_ws_engine: create_async_engine | None = None
_ws_session_maker: async_sessionmaker | None = None


def _init_engines(db_file: str) -> None:
    """Initialize test setup and WebSocket engines pointing to the same file.

    Using separate engines with separate pools allows concurrent access to the
    same SQLite file without StaticPool connection contention issues.
    The SQLite file itself handles locking and consistency.
    Enabling WAL mode allows concurrent reads during writes.
    """
    global test_engine, test_async_session_maker, _ws_engine, _ws_session_maker

    url = f"sqlite+aiosqlite:///{db_file}"

    # Enable WAL mode on the database before creating engines.
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.close()

    # Engine for test fixtures (creating users, conversations, etc.)
    test_engine = create_async_engine(
        url,
        echo=False,
        connect_args={
            "timeout": 30,
        },
    )
    test_async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Separate engine for WebSocket handler.
    _ws_engine = create_async_engine(
        url,
        echo=False,
        connect_args={
            "timeout": 30,
        },
    )
    _ws_session_maker = async_sessionmaker(
        _ws_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def _settle_background_translations() -> None:
    """Stop translation tasks still running for the test that just finished.

    Sending or editing a message schedules translation in a task that
    deliberately outlives the request (`schedule_translations`). No test waits
    for it, so without this the task is still querying when `_close_engines`
    disposes the engine underneath it: the aiosqlite connection is gone, the
    task dies mid-statement, and its session is never checked back in.
    SQLAlchemy then warns from inside the garbage collector, and pytest blames
    whichever test happens to be running at that moment — which is how a change
    in one module could redden a test in another that never touched it.

    Must run *before* the engines are disposed, which is why it is called from
    the fixtures that dispose them rather than from an autouse fixture: an
    autouse fixture is set up first and so torn down last, exactly too late.

    Cancelled rather than awaited: a task blocked on a real LLM call would hang
    the suite. Production never does this — the process is not torn down between
    messages — so this belongs to the harness, not to the service.
    """
    pending = [task for task in translation_module._BACKGROUND_TASKS if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _close_engines() -> None:
    """Dispose all engines after test."""
    global test_engine, test_async_session_maker, _ws_engine, _ws_session_maker

    if test_engine is not None:
        await test_engine.dispose()
        test_engine = None
        test_async_session_maker = None

    if _ws_engine is not None:
        await _ws_engine.dispose()
        _ws_engine = None
        _ws_session_maker = None


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database for each test function.

    Creates all tables at start, then yields a session for test data setup.
    After the test, drops all tables and removes the temp file.
    """
    global test_engine, test_async_session_maker, _ws_engine, _ws_session_maker

    # Create a temp file for this test function's database.
    fd, db_file = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    _init_engines(db_file)

    # Create all tables.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide a session for test data setup.
    session = test_async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

    # Drop all tables and clean up. Background translations first: disposing the
    # engine under a running task is what strands the connection.
    await _settle_background_translations()
    await _close_engines()
    try:
        os.unlink(db_file)
    except OSError:
        pass


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
async def client(
    test_db: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing API endpoints.

    Depends on test_db to ensure the database is initialized before use.
    """
    from src.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        # Use the same session maker as test_db for consistency
        if test_async_session_maker is None:
            raise RuntimeError("test_db fixture must be used before client fixture")
        session = test_async_session_maker()
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
async def ws_client(
    _db_for_ws_fixture: None,
) -> AsyncGenerator[tuple[TestClient, ConnectionManager], None]:
    """Provide a no-lifespan WebSocket app backed by the test database.

    This fixture depends on _db_for_ws_fixture which initializes the DB if test_db
    hasn't been used.
    """
    if _ws_session_maker is None:
        raise RuntimeError("Database not initialized. Use _db_for_ws or test_db fixture.")

    ws_app = FastAPI()
    ws_app.include_router(api_router, prefix="/api/v1")
    ws_app.include_router(websocket_router, prefix="/api/v1")
    manager = ConnectionManager()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session = _ws_session_maker()
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


@pytest_asyncio.fixture
async def _db_for_ws_fixture() -> None:
    """Initialize database for ws_client when test_db is not used.

    This is a no-op when test_db is already initialized.
    """
    global test_engine
    if test_engine is None:
        fd, db_file = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        _init_engines(db_file)

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        _db_for_ws_fixture._db_file = db_file
        yield
        if hasattr(_db_for_ws_fixture, '_db_file'):
            await _settle_background_translations()
            await _close_engines()
            try:
                os.unlink(_db_for_ws_fixture._db_file)
            except OSError:
                pass
    else:
        yield


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM to avoid calling OpenAI during tests."""
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
