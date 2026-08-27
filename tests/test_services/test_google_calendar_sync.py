"""Tests for two-way Google Calendar sync, and mostly for the loop that isn't.

Every sync of this shape can echo: we push a change, Google reports it back,
we apply it and mark the row as owing another push, and the two sides trade the
same event forever. Nothing about that failure is loud — the calendar looks
correct the whole time, and the only symptom is quota disappearing. So the etag
check gets the most attention here.

Nothing reaches the network. `httpx` is patched at the transport boundary with a
handler that answers like Google, so the request bodies and the header are
asserted rather than assumed.

Fixtures live in this file rather than tests/conftest.py, which is shared across
all feature areas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.core.crypto import decrypt, encrypt
from src.database.models import CalendarEvent, CalendarLink
from src.services.google_calendar import (
    RemoteEvent,
    apply_remote_changes,
    build_authorization_url,
    is_configured_for_calendar,
    push_event,
)

VALID_JWT_SECRET = "x" * 48


def settings_with_key(**overrides) -> Settings:
    """Settings carrying a real Fernet key, so encryption is exercised."""
    return Settings(
        jwt_secret=VALID_JWT_SECRET,
        token_encryption_key=Fernet.generate_key().decode(),
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://example.test/callback",
        **overrides,
    )


@pytest_asyncio.fixture
async def linked(test_db: AsyncSession, test_user) -> tuple[CalendarLink, Settings]:
    """A connected account whose tokens are stored encrypted."""
    config = settings_with_key()
    link = CalendarLink(
        user_id=test_user.id,
        google_calendar_id="primary",
        refresh_token_encrypted=encrypt("refresh-token", settings=config),
        access_token_encrypted=encrypt("access-token", settings=config),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        sync_enabled=True,
    )
    test_db.add(link)
    await test_db.commit()
    await test_db.refresh(link)
    return link, config


def transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_a_change_coming_back_from_google_with_our_own_etag_is_ignored(
    test_db: AsyncSession, test_user, linked
) -> None:
    """The stop that keeps the two sides from trading one event forever."""
    link, _config = linked
    ours = CalendarEvent(
        user_id=test_user.id,
        source="assistant",
        title="Họp nhóm",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        google_event_id="g-1",
        google_etag='"etag-1"',
        sync_state="synced",
    )
    test_db.add(ours)
    await test_db.commit()

    echoed = RemoteEvent(
        google_event_id="g-1",
        etag='"etag-1"',
        title="Tiêu đề do Google trả về",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=None,
        location=None,
        details=None,
        all_day=False,
        cancelled=False,
    )
    applied = await apply_remote_changes(test_db, link, [echoed])

    await test_db.refresh(ours)
    assert applied == 0
    assert ours.title == "Họp nhóm"
    # The decisive assertion: had it been applied, this would read
    # `pending_push` and the next cycle would send our own change back again.
    assert ours.sync_state == "synced"


@pytest.mark.asyncio
async def test_a_genuine_remote_edit_carries_a_new_etag_and_is_applied(
    test_db: AsyncSession, test_user, linked
) -> None:
    """The other half: a real change from Google must not be mistaken for an echo."""
    link, _config = linked
    ours = CalendarEvent(
        user_id=test_user.id,
        source="assistant",
        title="Họp nhóm",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        google_event_id="g-2",
        google_etag='"etag-1"',
        sync_state="synced",
    )
    test_db.add(ours)
    await test_db.commit()

    moved = RemoteEvent(
        google_event_id="g-2",
        etag='"etag-2"',
        title="Họp nhóm (dời giờ)",
        starts_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 9, 1, 11, 0, tzinfo=UTC),
        location="Phòng B",
        details=None,
        all_day=False,
        cancelled=False,
    )
    applied = await apply_remote_changes(test_db, link, [moved])

    await test_db.refresh(ours)
    assert applied == 1
    assert ours.title == "Họp nhóm (dời giờ)"
    assert ours.location == "Phòng B"
    # Applied, but still not owing a push — the change came *from* Google.
    assert ours.sync_state == "synced"


@pytest.mark.asyncio
async def test_an_event_created_in_google_arrives_read_only(
    test_db: AsyncSession, test_user, linked
) -> None:
    """Editing it here would fight whatever produced it there."""
    link, _config = linked
    remote = RemoteEvent(
        google_event_id="g-new",
        etag='"etag-x"',
        title="Khám răng",
        starts_at=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        ends_at=None,
        location=None,
        details=None,
        all_day=False,
        cancelled=False,
    )
    await apply_remote_changes(test_db, link, [remote])

    stored = await test_db.scalar(
        select(CalendarEvent).where(CalendarEvent.google_event_id == "g-new")
    )
    assert stored is not None
    assert stored.source == "google"
    assert stored.sync_state == "remote_only"


@pytest.mark.asyncio
async def test_a_deletion_in_google_cancels_the_local_entry(
    test_db: AsyncSession, test_user, linked
) -> None:
    link, _config = linked
    ours = CalendarEvent(
        user_id=test_user.id,
        source="assistant",
        title="Sẽ bị xoá bên Google",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        google_event_id="g-3",
        google_etag='"etag-1"',
        sync_state="synced",
    )
    test_db.add(ours)
    await test_db.commit()

    await apply_remote_changes(
        test_db,
        link,
        [
            RemoteEvent(
                google_event_id="g-3",
                etag='"etag-2"',
                title="Sẽ bị xoá bên Google",
                starts_at=None,
                ends_at=None,
                location=None,
                details=None,
                all_day=False,
                cancelled=True,
            )
        ],
    )

    await test_db.refresh(ours)
    assert ours.status == "cancelled"


@pytest.mark.asyncio
async def test_deleting_something_never_mirrored_here_creates_nothing(
    test_db: AsyncSession, test_user, linked
) -> None:
    """A tombstone for an event we never held is not an event."""
    link, _config = linked
    applied = await apply_remote_changes(
        test_db,
        link,
        [
            RemoteEvent(
                google_event_id="g-unknown",
                etag='"e"',
                title="",
                starts_at=None,
                ends_at=None,
                location=None,
                details=None,
                all_day=False,
                cancelled=True,
            )
        ],
    )

    assert applied == 0
    assert (await test_db.scalars(select(CalendarEvent))).all() == []


@pytest.mark.asyncio
async def test_pushing_an_event_stores_the_etag_google_returned(
    test_db: AsyncSession, test_user, linked, monkeypatch
) -> None:
    """Storing it is what makes the change recognisable when it comes back."""
    link, config = linked
    event = CalendarEvent(
        user_id=test_user.id,
        source="assistant",
        title="Gửi báo cáo",
        starts_at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        timezone="Asia/Ho_Chi_Minh",
        sync_state="local_only",
    )
    test_db.add(event)
    await test_db.commit()

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"id": "g-99", "etag": '"etag-new"'})

    original = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs["transport"] = transport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)

    await push_event(test_db, link, event, settings=config)

    await test_db.refresh(event)
    assert event.google_event_id == "g-99"
    assert event.google_etag == '"etag-new"'
    assert event.sync_state == "synced"
    assert seen["method"] == "POST"
    assert seen["auth"] == "Bearer access-token"
    assert "Asia/Ho_Chi_Minh" in str(seen["body"])


@pytest.mark.asyncio
async def test_a_stored_refresh_token_is_not_readable_as_plain_text(
    test_db: AsyncSession, linked
) -> None:
    """Leaking one grants standing access to somebody's real calendar."""
    link, config = linked

    assert "refresh-token" not in link.refresh_token_encrypted
    assert decrypt(link.refresh_token_encrypted, settings=config) == "refresh-token"


def test_the_consent_url_asks_for_offline_access_and_the_narrow_scope() -> None:
    """Without `prompt=consent` Google omits the refresh token after the first
    authorization, and the link dies silently an hour later."""
    url = build_authorization_url(state="signed-state", settings=settings_with_key())

    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "calendar.events" in url
    # Not the broader `auth/calendar`, which also grants managing calendars —
    # a permission nothing here uses but every user would be asked to grant.
    assert "auth%2Fcalendar&" not in url
    assert "state=signed-state" in url


def test_calendar_is_reported_unconfigured_without_an_encryption_key() -> None:
    """Refusing is the point: the alternative is storing tokens in the clear."""
    keyless = Settings(
        jwt_secret=VALID_JWT_SECRET,
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://example.test/callback",
        token_encryption_key="",
    )
    assert is_configured_for_calendar(keyless) is False
    assert is_configured_for_calendar(settings_with_key()) is True
