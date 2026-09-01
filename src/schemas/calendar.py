"""Request and response bodies for the personal calendar (`CONTRACT.md` §3.16)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.chat import UtcDatetime


class CalendarEventResponse(BaseModel):
    """One entry as the calendar page renders it."""

    model_config = ConfigDict(from_attributes=True)

    # Read-only, for the same reason as `ActionProposalResponse`: the
    # calendar page PATCHes `title` back when a task is dragged, so a
    # translated `title` in the response would be written to the row.
    display_title: str | None = None

    id: str
    title: str
    details: str | None = None
    location: str | None = None
    starts_at: UtcDatetime
    ends_at: UtcDatetime | None = None
    all_day: bool = False
    timezone: str | None = None
    source: str
    status: str
    # Present when the entry came from, or reached, Google. The client uses it
    # to mark an entry read-only rather than to decide anything about it.
    sync_state: str
    google_event_id: str | None = None
    # Which proposal this grew from, so the inbox can show that an approved item
    # actually landed somewhere.
    action_proposal_id: str | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class CalendarEventCreateRequest(BaseModel):
    """A manually added entry."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    starts_at: UtcDatetime
    ends_at: UtcDatetime | None = None
    details: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=500)
    all_day: bool = False
    timezone: str | None = Field(default=None, max_length=64)
    # Minutes before the start. `None` means no reminder, which is a real
    # choice and distinct from "use the default".
    reminder_minutes_before: int | None = Field(default=15, ge=0, le=10080)

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> CalendarEventCreateRequest:
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not be earlier than starts_at")
        return self


class CalendarEventUpdateRequest(BaseModel):
    """Partial update; only the named fields change."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: UtcDatetime | None = None
    ends_at: UtcDatetime | None = None
    details: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=500)
    all_day: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def require_a_change(self) -> CalendarEventUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class ReminderResponse(BaseModel):
    """One nudge owed against an entry."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    calendar_event_id: str
    remind_at: UtcDatetime
    delivered_at: UtcDatetime | None = None
    dismissed_at: UtcDatetime | None = None


class ReminderDueEvent(BaseModel):
    """The WebSocket event pushed when a reminder comes due.

    A schema rather than a bare dict, because `docs/CONTRACT.md` §4 makes the
    `Literal` default on a Pydantic model the source of truth for an event name
    — `action_proposal_created` was the one exception and it should not gain a
    second.
    """

    type: str = "reminder_due"
    reminder: dict


class CalendarEventUpdatedEvent(BaseModel):
    """Pushed when an entry changed somewhere other than in this client."""

    type: str = "calendar_event_updated"
    event: CalendarEventResponse


class ActionProposalConfirmedEvent(BaseModel):
    """Pushed when a proposal was approved and, if timed, scheduled."""

    type: str = "action_proposal_confirmed"
    proposal_id: str
    calendar_event: CalendarEventResponse | None = None


def default_reminder_at(starts_at: datetime, minutes_before: int | None) -> datetime | None:
    """Work out when to nudge, or ``None`` when the caller asked for silence."""
    if minutes_before is None:
        return None
    from datetime import timedelta

    return starts_at - timedelta(minutes=minutes_before)


class GoogleAuthorizeResponse(BaseModel):
    """Where to send the user to grant calendar access."""

    authorization_url: str


class GoogleCalendarCallbackRequest(BaseModel):
    """What the browser hands back after the consent screen."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=2048)
    # Echoed by Google verbatim. Signed on the way out and verified against the
    # authenticated caller on the way back, so a replayed callback cannot attach
    # one person's authorization to another person's account.
    state: str = Field(min_length=1, max_length=4096)


class CalendarLinkResponse(BaseModel):
    """The connection's state, with no token material in it.

    Deliberately carries neither token nor cursor: this is rendered in a browser
    and logged by proxies, and nothing here needs them to describe the link.
    """

    model_config = ConfigDict(from_attributes=True)

    google_calendar_id: str
    sync_enabled: bool
    last_synced_at: UtcDatetime | None = None
    last_sync_error: str | None = None
    created_at: UtcDatetime


class CalendarSyncResultResponse(BaseModel):
    """What one sync cycle did."""

    pushed: int
    pulled: int
    last_synced_at: UtcDatetime | None = None
    # Surfaced rather than swallowed: silence after a failed sync looks exactly
    # like a calendar with nothing to sync.
    last_sync_error: str | None = None


class CalendarCapabilityResponse(BaseModel):
    """Whether Google Calendar is usable here, and how far this account got.

    The interface needs three separate facts, and collapsing them loses the one
    that matters. `configured` is about the deployment — no credentials means
    the feature does not exist here and its controls should not be drawn at all.
    `consented` is about permission. `linked` is about whether they finished the
    Google flow. Showing a "Sync now" button for any of the three missing states
    promises something that will answer with an error.
    """

    configured: bool
    consented: bool
    linked: bool
    sync_enabled: bool = False
    last_synced_at: UtcDatetime | None = None
    last_sync_error: str | None = None
