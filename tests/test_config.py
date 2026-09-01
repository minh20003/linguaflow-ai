"""Tests for the settings that only a deployment exercises.

Every case here fires at import time in production, where nobody is watching a
test run — a wrong value shows up as a container that either will not start or,
worse, starts with a secret anyone can guess.

`Settings` is built with explicit keyword arguments so the developer's own `.env`
cannot decide the outcome.
"""

import pytest

from src.config import Settings

VALID_SECRET = "x" * 48


def settings(**overrides) -> Settings:
    """Build settings with a usable secret unless the test overrides it."""
    return Settings(jwt_secret=VALID_SECRET, **overrides)


def test_a_plain_postgres_url_is_moved_onto_the_async_driver():
    """Managed databases hand out `postgresql://`, which is the sync driver."""
    resolved = settings(database_url="postgresql://user:pass@host:5432/db")

    assert resolved.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_the_heroku_style_postgres_scheme_is_moved_onto_the_async_driver():
    resolved = settings(database_url="postgres://user:pass@host:5432/db")

    assert resolved.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_a_url_that_already_names_a_driver_is_left_alone():
    """Including one that names a driver this project does not install."""
    resolved = settings(database_url="postgresql+psycopg://user:pass@host/db")

    assert resolved.database_url == "postgresql+psycopg://user:pass@host/db"


def test_the_sqlite_default_is_left_alone():
    assert settings().database_url.startswith("sqlite+aiosqlite:///")


def test_database_sql_echo_is_opt_in_to_protect_bound_message_text():
    assert Settings.model_fields["database_echo"].default is False
    assert settings(database_echo=True).database_echo is True


def test_cors_origins_are_split_and_stripped():
    """A list written the way a human writes one must still match an Origin."""
    resolved = settings(cors_origins="http://localhost:3000, https://app.example.com ")

    assert resolved.cors_origin_list == ["http://localhost:3000", "https://app.example.com"]


def test_an_empty_cors_entry_is_dropped():
    """A trailing comma would otherwise produce an origin that matches nothing."""
    resolved = settings(cors_origins="http://localhost:3000,,")

    assert resolved.cors_origin_list == ["http://localhost:3000"]


def test_a_missing_jwt_secret_is_refused_in_every_environment():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(jwt_secret="")


def test_the_example_jwt_secret_is_refused_in_production():
    """It passes an "is it empty" check, which is exactly the danger."""
    with pytest.raises(ValueError, match="example value"):
        Settings(app_env="production", jwt_secret="your-secret-key-here")


def test_a_short_jwt_secret_is_refused_in_production():
    with pytest.raises(ValueError, match="at least"):
        Settings(app_env="production", jwt_secret="short-but-not-a-placeholder")


def test_a_short_jwt_secret_is_allowed_outside_production():
    """Development is not where this rule earns anything, and it costs setup."""
    assert Settings(app_env="development", jwt_secret="dev").jwt_secret == "dev"
