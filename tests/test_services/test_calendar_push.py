"""Tests for pushing a calendar change to Google straight away.

This sits on top of the periodic cycle rather than replacing it, and the tests
are mostly about the cases where it must decline. Pushing something it should
not — an entry that came from Google, or one belonging to an account that never
granted write access — is worse than being slow, because the periodic cycle
would never have done it either.

Fixtures live in this file rather than tests/conftest.py, which is shared across
all feature areas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.core.crypto import encrypt
from src.database.models import CalendarEvent, CalendarLink
from src.services import calendar_push


def linked_settings() -> Settings:
    return Settings(
        jwt_secret="x" * 48,
        token_encryption_key=Fernet.generate_key().decode(),
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://example.test/callback",
    )


@pytest_asyncio.fixture
async def linked(test_db: AsyncSession, test_user) -> Settings:
    """An account with a live Google link."""
    config = linked_settings()
    test_db.add(
        CalendarLink(
            user_id=test_user.id,
            google_calendar_id="primary",
            refresh_token_encrypted=encrypt("refresh", settings=config),
            sync_enabled=True,
        )
    )
    await test_db.commit()
    return config


@pytest.fixture
def permitted(monkeypatch):
    """Google configured and `calendar_write` granted, unless a test says not."""
    monkeypatch.setattr(
        "src.services.google_calendar.is_configured_for_calendar", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "src.services.agent_consent.has_consent", AsyncMock(return_value=True)
    )


async def make_event(test_db: AsyncSession, user_id: str, **overrides) -> CalendarEvent:
    event = CalendarEvent(
        user_id=user_id,
        source=overrides.pop("source", "manual"),
        title="Họp nhóm",
        starts_at=datetime.now(UTC) + timedelta(hours=2),
        sync_state=overrides.pop("sync_state", "local_only"),
        **overrides,
    )
    test_db.add(event)
    await test_db.commit()
    await test_db.refresh(event)
    return event


@pytest.mark.asyncio
async def test_a_new_entry_is_sent_to_google_without_waiting_for_the_cycle(
    test_db: AsyncSession, test_user, linked, permitted, monkeypatch
) -> None:
    """The user just pressed save; five minutes later is not "synced"."""
    import tests.conftest as conftest_module

    event = await make_event(test_db, test_user.id)
    push = AsyncMock()
    monkeypatch.setattr("src.services.google_calendar.push_event", push)

    await calendar_push._push(
        event_id=event.id,
        user_id=test_user.id,
        session_factory=conftest_module.test_async_session_maker,
    )

    push.assert_awaited_once()


@pytest.mark.asyncio
async def test_an_entry_that_came_from_google_is_never_pushed_back(
    test_db: AsyncSession, test_user, linked, permitted, monkeypatch
) -> None:
    """The echo the etag check prevents, arriving by a different route."""
    import tests.conftest as conftest_module

    event = await make_event(
        test_db, test_user.id, source="google", sync_state="remote_only", google_event_id="g-1"
    )
    push = AsyncMock()
    monkeypatch.setattr("src.services.google_calendar.push_event", push)

    await calendar_push._push(
        event_id=event.id,
        user_id=test_user.id,
        session_factory=conftest_module.test_async_session_maker,
    )

    push.assert_not_awaited()


@pytest.mark.asyncio
async def test_nothing_is_written_to_google_without_calendar_write_consent(
    test_db: AsyncSession, test_user, linked, monkeypatch
) -> None:
    """Reading a calendar and writing to it are separate asks (ADR-30)."""
    import tests.conftest as conftest_module

    monkeypatch.setattr(
        "src.services.google_calendar.is_configured_for_calendar", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "src.services.agent_consent.has_consent", AsyncMock(return_value=False)
    )
    event = await make_event(test_db, test_user.id)
    push = AsyncMock()
    monkeypatch.setattr("src.services.google_calendar.push_event", push)

    await calendar_push._push(
        event_id=event.id,
        user_id=test_user.id,
        session_factory=conftest_module.test_async_session_maker,
    )

    push.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_push_is_left_for_the_periodic_cycle_to_retry(
    test_db: AsyncSession, test_user, linked, permitted, monkeypatch
) -> None:
    """Late, not lost — and marked so a previously synced entry is not trusted."""
    import tests.conftest as conftest_module
    from src.services.google_calendar import GoogleCalendarError

    event = await make_event(
        test_db, test_user.id, sync_state="synced", google_event_id="g-2"
    )
    monkeypatch.setattr(
        "src.services.google_calendar.push_event",
        AsyncMock(side_effect=GoogleCalendarError("Google is down")),
    )

    await calendar_push._push(
        event_id=event.id,
        user_id=test_user.id,
        session_factory=conftest_module.test_async_session_maker,
    )

    await test_db.refresh(event)
    assert event.sync_state == "pending_push"


@pytest.mark.asyncio
async def test_another_persons_entry_is_not_pushed_under_this_account(
    test_db: AsyncSession, test_user, test_user_two, linked, permitted, monkeypatch
) -> None:
    """Ownership is checked here rather than trusted from the caller."""
    import tests.conftest as conftest_module

    event = await make_event(test_db, test_user_two.id)
    push = AsyncMock()
    monkeypatch.setattr("src.services.google_calendar.push_event", push)

    await calendar_push._push(
        event_id=event.id,
        user_id=test_user.id,
        session_factory=conftest_module.test_async_session_maker,
    )

    push.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_paused_link_stops_the_push_without_disconnecting(
    test_db: AsyncSession, test_user, linked, permitted, monkeypatch
) -> None:
    """`sync_enabled` is the user's pause switch, separate from being linked."""
    import tests.conftest as conftest_module

    link = await test_db.get(CalendarLink, test_user.id)
    link.sync_enabled = False
    await test_db.commit()

    event = await make_event(test_db, test_user.id)
    push = AsyncMock()
    monkeypatch.setattr("src.services.google_calendar.push_event", push)

    await calendar_push._push(
        event_id=event.id,
        user_id=test_user.id,
        session_factory=conftest_module.test_async_session_maker,
    )

    push.assert_not_awaited()
