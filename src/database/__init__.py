"""Database module for async SQLAlchemy setup."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

# Lazy load settings to avoid import errors during testing
# when JWT_SECRET might not be set
_settings = None


def _get_settings():
    """Get settings with caching."""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def _get_engine():
    """Get or create async engine."""
    settings = _get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        pool_pre_ping=True,
    )


# Cache the engine
_engine = None


def get_engine():
    """Get or create async engine with caching."""
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


def get_async_session_maker():
    """Get or create async session maker with caching."""
    engine = get_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all tables. Called on app startup."""
    from src.database.models import Base  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
