"""Two-way sync between the in-app calendar and Google Calendar.

Written against Google's REST API with `httpx` rather than
`google-api-python-client`. That client is synchronous and discovery-based;
everything here runs inside an async request or an async scheduler job, and
wrapping a sync client in a thread pool to make four HTTP calls is more moving
parts than the calls themselves. `httpx` is already a runtime dependency
(`src/api/routes.py` uses it for Supabase), so this adds none (ADR-35).

**Incoming changes are polled, not pushed** (ADR-36). Google's push channels
need a publicly reachable HTTPS endpoint and renewal roughly weekly; polling
with a `syncToken` needs neither, works unchanged on a laptop, and still only
transfers what changed. The cost is latency measured in minutes, which for a
personal calendar is not a cost worth a webhook's operational surface.

**The loop-prevention rule is the part to not break.** Every sync of this shape
can echo: we push a change, Google reports that change back on the next poll,
we apply it and mark the row as needing a push, and the two sides trade the same
event forever. The stop is `google_etag` — before applying an incoming change,
compare it with the etag we stored when we last wrote. Equal means this is our
own write coming home, and it is ignored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.core.crypto import TokenEncryptionError, decrypt, encrypt, is_configured
from src.database.models import CalendarEvent, CalendarLink

logger = logging.getLogger(__name__)

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"

# Only what the feature does: read events and write the ones the user approved.
# Not `calendar`, which also grants managing calendars themselves — a scope
# nothing here uses and every user would be asked to grant anyway.
SCOPES = ("https://www.googleapis.com/auth/calendar.events",)

# Refresh a little before expiry rather than on it, so a call that starts just
# under the wire does not fail mid-flight.
REFRESH_MARGIN = timedelta(minutes=2)

HTTP_TIMEOUT = 20


class GoogleCalendarError(Exception):
    """A Google Calendar operation failed."""


class GoogleCalendarNotLinkedError(GoogleCalendarError):
    """This account has not connected a Google Calendar."""


class SyncTokenExpiredError(GoogleCalendarError):
    """Google returned 410; the incremental cursor is no longer usable."""


@dataclass(frozen=True, slots=True)
class RemoteEvent:
    """One event as Google describes it, reduced to what this product stores."""

    google_event_id: str
    etag: str | None
    title: str
    starts_at: datetime | None
    ends_at: datetime | None
    location: str | None
    details: str | None
    all_day: bool
    cancelled: bool


def is_configured_for_calendar(settings: Settings | None = None) -> bool:
    """Whether Google Calendar can work at all in this deployment.

    All three are required and each fails differently without the check: no
    client id or secret means the token exchange is rejected by Google, and no
    encryption key means a refresh token would have to be stored in the clear,
    which this refuses to do.
    """
    effective = settings or get_settings()
    return bool(
        effective.google_oauth_client_id
        and effective.google_oauth_client_secret
        and effective.google_oauth_redirect_uri
        and is_configured(effective)
    )


def build_authorization_url(*, state: str, settings: Settings | None = None) -> str:
    """Build the consent URL the user is sent to.

    `access_type=offline` with `prompt=consent` is what produces a refresh
    token. Without `prompt=consent` Google omits the refresh token on every
    authorization after the first, and the symptom is a link that works until
    the access token expires an hour later and then silently stops.
    """
    from urllib.parse import urlencode

    effective = settings or get_settings()
    query = urlencode(
        {
            "client_id": effective.google_oauth_client_id,
            "redirect_uri": effective.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return f"{AUTH_ENDPOINT}?{query}"


async def exchange_code(code: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Trade the authorization code for tokens."""
    effective = settings or get_settings()
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": effective.google_oauth_client_id,
                "client_secret": effective.google_oauth_client_secret,
                "redirect_uri": effective.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != 200:
        raise GoogleCalendarError(f"Token exchange failed: {response.status_code}")
    payload = response.json()
    if not payload.get("refresh_token"):
        # Without one the link works for an hour and then dies quietly, which is
        # worse than refusing now.
        raise GoogleCalendarError("Google did not return a refresh token")
    return payload


async def _refresh_access_token(
    refresh_token: str, *, settings: Settings | None = None
) -> dict[str, Any]:
    """Exchange the long-lived refresh token for a fresh access token."""
    effective = settings or get_settings()
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "refresh_token": refresh_token,
                "client_id": effective.google_oauth_client_id,
                "client_secret": effective.google_oauth_client_secret,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code != 200:
        raise GoogleCalendarError(f"Token refresh failed: {response.status_code}")
    return response.json()


async def access_token_for(
    db: AsyncSession, link: CalendarLink, *, settings: Settings | None = None
) -> str:
    """Return a usable access token, refreshing it first if it is close to expiry."""
    effective = settings or get_settings()
    now = datetime.now(UTC)

    if (
        link.access_token_encrypted
        and link.token_expires_at
        and link.token_expires_at - REFRESH_MARGIN > now
    ):
        return decrypt(link.access_token_encrypted, settings=effective)

    refreshed = await _refresh_access_token(
        decrypt(link.refresh_token_encrypted, settings=effective), settings=effective
    )
    token = refreshed["access_token"]
    link.access_token_encrypted = encrypt(token, settings=effective)
    link.token_expires_at = now + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
    await db.commit()
    return token


def _to_google_body(event: CalendarEvent) -> dict[str, Any]:
    """Render one stored entry in Google's event shape."""
    if event.all_day:
        start: dict[str, Any] = {"date": event.starts_at.date().isoformat()}
        end_date = (event.ends_at or event.starts_at).date()
        end: dict[str, Any] = {"date": end_date.isoformat()}
    else:
        start = {"dateTime": event.starts_at.isoformat()}
        if event.timezone:
            start["timeZone"] = event.timezone
        finish = event.ends_at or event.starts_at + timedelta(minutes=30)
        end = {"dateTime": finish.isoformat()}
        if event.timezone:
            end["timeZone"] = event.timezone

    body: dict[str, Any] = {"summary": event.title, "start": start, "end": end}
    if event.details:
        body["description"] = event.details
    if event.location:
        body["location"] = event.location
    if event.status == "cancelled":
        body["status"] = "cancelled"
    return body


def _parse_remote(payload: dict[str, Any]) -> RemoteEvent | None:
    """Read one Google event, or ``None`` if it is not one this product can hold."""
    event_id = payload.get("id")
    if not event_id:
        return None

    start = payload.get("start") or {}
    end = payload.get("end") or {}
    all_day = "date" in start

    def moment(part: dict[str, Any]) -> datetime | None:
        raw = part.get("dateTime") or part.get("date")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        # An all-day event arrives as a bare date. Anchored to UTC midnight so
        # it is comparable with everything else; `all_day` is what the interface
        # reads, so the invented time is never shown.
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    return RemoteEvent(
        google_event_id=event_id,
        etag=payload.get("etag"),
        title=payload.get("summary") or "(không có tiêu đề)",
        starts_at=moment(start),
        ends_at=moment(end),
        location=payload.get("location"),
        details=payload.get("description"),
        all_day=all_day,
        cancelled=payload.get("status") == "cancelled",
    )


async def push_event(
    db: AsyncSession,
    link: CalendarLink,
    event: CalendarEvent,
    *,
    settings: Settings | None = None,
) -> CalendarEvent:
    """Create or update this entry in Google Calendar.

    The returned etag is stored, and that is what makes the change recognisable
    when Google reports it back on the next poll — without it the two sides
    would trade the same event indefinitely.
    """
    effective = settings or get_settings()
    token = await access_token_for(db, link, settings=effective)
    body = _to_google_body(event)
    base = f"{CALENDAR_API}/calendars/{link.google_calendar_id}/events"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        if event.google_event_id:
            response = await client.put(
                f"{base}/{event.google_event_id}",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            response = await client.post(
                base, json=body, headers={"Authorization": f"Bearer {token}"}
            )

    if response.status_code not in (200, 201):
        raise GoogleCalendarError(f"Pushing the event failed: {response.status_code}")

    payload = response.json()
    event.google_event_id = payload.get("id") or event.google_event_id
    event.google_calendar_id = link.google_calendar_id
    event.google_etag = payload.get("etag")
    event.sync_state = "synced"
    await db.commit()
    return event


async def pull_changes(
    db: AsyncSession, link: CalendarLink, *, settings: Settings | None = None
) -> tuple[list[RemoteEvent], str | None]:
    """Fetch what changed on Google since the stored cursor.

    Raises:
        SyncTokenExpiredError: Google answered 410. The caller drops the cursor
            and takes one full pass; it is routine after a long gap, not a bug.
    """
    effective = settings or get_settings()
    token = await access_token_for(db, link, settings=effective)
    params: dict[str, Any] = {"maxResults": 250, "showDeleted": "true"}
    if link.sync_token:
        params["syncToken"] = link.sync_token
    else:
        # First pass. Bounded to a window rather than the whole history: a
        # calendar of ten years is not context anybody wants mirrored here.
        params["timeMin"] = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        params["singleEvents"] = "true"

    collected: list[RemoteEvent] = []
    next_sync_token: str | None = None
    page_token: str | None = None

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        while True:
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                f"{CALENDAR_API}/calendars/{link.google_calendar_id}/events",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 410:
                raise SyncTokenExpiredError("syncToken is no longer valid")
            if response.status_code != 200:
                raise GoogleCalendarError(f"Listing events failed: {response.status_code}")

            payload = response.json()
            for item in payload.get("items", []):
                parsed = _parse_remote(item)
                if parsed is not None:
                    collected.append(parsed)

            page_token = payload.get("nextPageToken")
            if not page_token:
                next_sync_token = payload.get("nextSyncToken")
                break

    return collected, next_sync_token


async def apply_remote_changes(
    db: AsyncSession,
    link: CalendarLink,
    remote_events: list[RemoteEvent],
) -> int:
    """Merge Google's changes into the local calendar.

    Three cases, and the first is the loop stop. An event whose etag matches the
    one stored is our own write coming home: skipped, so it does not mark the
    row as owing another push and start the two sides echoing each other.

    An event we know about is updated in place. An event created in Google is
    stored as `remote_only`, which the API and interface both treat as read-only
    — editing it here would fight whatever produced it there.
    """
    applied = 0
    for remote in remote_events:
        local = await db.scalar(
            select(CalendarEvent).where(
                CalendarEvent.user_id == link.user_id,
                CalendarEvent.google_event_id == remote.google_event_id,
            )
        )

        if local is not None and remote.etag and local.google_etag == remote.etag:
            continue

        if local is None:
            if remote.cancelled or remote.starts_at is None:
                # A deletion of something never mirrored here, or an event with
                # no usable time. Nothing to represent either way.
                continue
            local = CalendarEvent(
                user_id=link.user_id,
                source="google",
                title=remote.title[:255],
                details=remote.details,
                location=remote.location,
                starts_at=remote.starts_at,
                ends_at=remote.ends_at,
                all_day=remote.all_day,
                google_event_id=remote.google_event_id,
                google_calendar_id=link.google_calendar_id,
                google_etag=remote.etag,
                sync_state="remote_only",
            )
            db.add(local)
            applied += 1
            continue

        if remote.cancelled:
            local.status = "cancelled"
        else:
            local.title = remote.title[:255]
            local.details = remote.details
            local.location = remote.location
            if remote.starts_at is not None:
                local.starts_at = remote.starts_at
            local.ends_at = remote.ends_at
            local.all_day = remote.all_day
        local.google_etag = remote.etag
        # Deliberately not `pending_push`: this change came *from* Google, so
        # pushing it back is exactly the echo the etag check prevents.
        local.sync_state = "synced" if local.source != "google" else "remote_only"
        applied += 1

    await db.commit()
    return applied


async def sync_user(
    db: AsyncSession, user_id: str, *, settings: Settings | None = None
) -> dict[str, int]:
    """Run one full cycle for one account: push what is owed, then pull.

    Push first, deliberately. Pulling first would fetch a remote state that does
    not yet know about the local changes, and applying it could overwrite an
    entry the user just edited here.

    Never raises. A failure is recorded on the link so the interface can say why
    nothing moved — silence after a failed sync looks the same as a calendar
    with nothing in it.
    """
    effective = settings or get_settings()
    counts = {"pushed": 0, "pulled": 0}

    link = await db.get(CalendarLink, user_id)
    if link is None:
        raise GoogleCalendarNotLinkedError(user_id)
    if not link.sync_enabled:
        return counts

    try:
        pending = (
            await db.scalars(
                select(CalendarEvent).where(
                    CalendarEvent.user_id == user_id,
                    CalendarEvent.sync_state.in_(("local_only", "pending_push")),
                    CalendarEvent.source != "google",
                )
            )
        ).all()
        for event in pending:
            try:
                await push_event(db, link, event, settings=effective)
                counts["pushed"] += 1
            except GoogleCalendarError:
                # One event failing must not abandon the rest; it stays
                # `pending_push` and the next cycle tries again.
                logger.warning("Pushing calendar event %s failed", event.id, exc_info=True)
                event.sync_state = "pending_push"
                await db.commit()

        try:
            remote_events, next_token = await pull_changes(db, link, settings=effective)
        except SyncTokenExpiredError:
            link.sync_token = None
            await db.commit()
            remote_events, next_token = await pull_changes(db, link, settings=effective)

        counts["pulled"] = await apply_remote_changes(db, link, remote_events)
        if next_token:
            link.sync_token = next_token
        link.last_synced_at = datetime.now(UTC)
        link.last_sync_error = None
        await db.commit()
    except (GoogleCalendarError, TokenEncryptionError) as exc:
        logger.warning("Calendar sync failed for user %s", user_id, exc_info=True)
        link.last_sync_error = str(exc)[:500]
        await db.commit()

    return counts


async def sync_all_enabled_links(*, session_factory: Any = None) -> int:
    """Run a cycle for every account that has sync switched on.

    The scheduler's job. Sequential rather than concurrent: this is a handful of
    users on one instance, and firing every account's Google calls at once is
    how a quota gets spent in a burst instead of a trickle.

    Never raises, for the same reason the reminder scan does not — the next
    cycle is minutes away.
    """
    from src.database import get_async_session_maker

    if not is_configured_for_calendar():
        return 0

    factory = session_factory or get_async_session_maker()
    synced = 0
    try:
        async with factory() as session:
            user_ids = list(
                (
                    await session.scalars(
                        select(CalendarLink.user_id).where(CalendarLink.sync_enabled.is_(True))
                    )
                ).all()
            )
    except Exception:
        logger.warning("Listing calendar links failed", exc_info=True)
        return 0

    for user_id in user_ids:
        try:
            async with factory() as session:
                await sync_user(session, user_id)
                synced += 1
        except Exception:
            logger.warning("Calendar sync cycle failed for %s", user_id, exc_info=True)

    return synced
