"""Owner-scoped ActionProposal persistence, temporal safety, and HITL transitions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ActionProposal, Message
from src.schemas.intelligence import ActionCandidateDTO

MAX_CLARIFICATION_ROUNDS = 2
_ACTIVE_STATUSES = ("needs_clarification", "pending_confirmation")
_RELATIVE_TIME = re.compile(
    r"\b(?:mai|ngày mai|tomorrow)\b(?:\s+(?:lúc|at))?\s*(?P<hour>\d{1,2})(?:[:h](?P<minute>\d{2})?)?",
    re.IGNORECASE,
)
_TOMORROW_MORNING = re.compile(r"\b(?:tomorrow morning|sáng mai)\b", re.IGNORECASE)
_NEXT_FRIDAY = re.compile(r"\bnext friday\b", re.IGNORECASE)


class ActionProposalError(Exception):
    """Base proposal lifecycle error."""


class ActionProposalNotFoundError(ActionProposalError):
    """The proposal does not exist."""


class ActionProposalOwnershipError(ActionProposalError):
    """The authenticated user is not the proposal owner."""


class ActionProposalStatusError(ActionProposalError):
    """The requested transition is not valid for the current state."""


@dataclass(frozen=True)
class TemporalResolution:
    """Server-side temporal result; model datetimes are never authoritative."""

    scheduled_start_at: datetime | None
    raw_time_expression: str | None
    resolved_timezone: str | None
    missing_fields: tuple[str, ...]


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        parsed = _parse_explicit_offset(value)
        if parsed is None:
            raise ValueError("Datetime must be ISO 8601 with an explicit timezone")
        return parsed
    if value.tzinfo is None:
        raise ValueError("Datetime must include an explicit timezone")
    return value.astimezone(UTC)


def _valid_timezone(value: str | None) -> ZoneInfo | None:
    if not value:
        return None
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return None


def _parse_explicit_offset(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed) if parsed.tzinfo else None


def _relative_time_expression(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    return bool(
        _RELATIVE_TIME.search(lowered)
        or _TOMORROW_MORNING.search(lowered)
        or _NEXT_FRIDAY.search(lowered)
    )


def _resolve_relative_time(raw: str, reference: datetime, timezone: ZoneInfo) -> datetime | None:
    """Resolve the deliberately small, execution-safe relative-time grammar."""

    local_reference = _as_utc(reference).astimezone(timezone)
    match = _RELATIVE_TIME.search(raw)
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        if hour > 23 or minute > 59:
            return None
        local = datetime.combine(
            local_reference.date() + timedelta(days=1), time(hour=hour, minute=minute), timezone
        )
        return local.astimezone(UTC)
    if _TOMORROW_MORNING.search(raw):
        local = datetime.combine(local_reference.date() + timedelta(days=1), time(hour=9), timezone)
        return local.astimezone(UTC)
    if _NEXT_FRIDAY.search(raw):
        days = (4 - local_reference.weekday()) % 7 or 7
        local = datetime.combine(local_reference.date() + timedelta(days=days), time(hour=9), timezone)
        return local.astimezone(UTC)
    return None


def normalize_action_time(
    *,
    raw_time_expression: str | None,
    reference_timestamp: datetime | None,
    trusted_timezone: str | None,
    candidate_datetime: datetime | None = None,
    trusted_candidate_datetime: bool = False,
    clarification_answer: str | None = None,
    existing_missing_fields: list[str] | None = None,
) -> TemporalResolution:
    """Normalize temporal data without guessing a locale, timezone, or current time.

    An ISO value with an explicit offset is self-contained.  A relative value
    requires an explicit trusted IANA timezone and the source message timestamp;
    an LLM supplied UTC value cannot fill that gap.
    """

    raw = (raw_time_expression or "").strip() or None
    answer = (clarification_answer or "").strip() or None
    missing = set(existing_missing_fields or [])
    explicit = _parse_explicit_offset(answer) or _parse_explicit_offset(raw)
    if explicit is not None:
        missing.discard("time")
        missing.discard("timezone")
        return TemporalResolution(explicit, raw, None, tuple(sorted(missing)))

    # A timezone can be explicitly supplied in the trusted request field.  A
    # bare IANA timezone answer is also a direct answer to an existing timezone
    # question; it is validated with zoneinfo before being trusted.
    timezone_name = trusted_timezone
    if timezone_name is None and "timezone" in missing and answer and _valid_timezone(answer):
        timezone_name = answer
    timezone = _valid_timezone(timezone_name)

    # A confirm payload is authenticated owner input, unlike model candidate
    # data. Its offset-bearing datetime is a complete representation of an
    # instant and may resolve a prior relative-time ambiguity without guessing
    # a locale or timezone.
    if candidate_datetime is not None and trusted_candidate_datetime:
        try:
            canonical_candidate = _as_utc(candidate_datetime)
        except ValueError:
            missing.add("time")
        else:
            missing.discard("time")
            missing.discard("timezone")
            return TemporalResolution(canonical_candidate, raw, None, tuple(sorted(missing)))

    if raw and _relative_time_expression(raw):
        if timezone is None or reference_timestamp is None:
            missing.update({"timezone", "time"})
            return TemporalResolution(None, raw, None, tuple(sorted(missing)))
        resolved = _resolve_relative_time(raw, reference_timestamp, timezone)
        if resolved is None:
            missing.add("time")
            return TemporalResolution(None, raw, timezone.key, tuple(sorted(missing)))
        missing.discard("time")
        missing.discard("timezone")
        return TemporalResolution(resolved, raw, timezone.key, tuple(sorted(missing)))

    # Candidate datetime is admissible only when it is not standing in for an
    # ambiguous relative expression.  This preserves explicit/manual candidate
    # data while refusing fabricated UTC for phrases such as "mai 9h".
    if candidate_datetime is not None:
        try:
            canonical_candidate = _as_utc(candidate_datetime)
            return TemporalResolution(
                canonical_candidate, raw, None, tuple(sorted(missing))
            )
        except ValueError:
            missing.add("time")
    return TemporalResolution(None, raw, None, tuple(sorted(missing)))


def compute_proposal_idempotency_key(
    owner_user_id: str,
    source_message_id: str,
    action_type: str,
    title: str,
    scheduled_time: datetime | str | None = None,
    source_mode: str = "on_demand",
    raw_time_expression: str | None = None,
) -> str:
    """Stable logical-action identity including the complete canonical time."""

    if isinstance(scheduled_time, datetime):
        stamp = _as_utc(scheduled_time).isoformat()
    elif scheduled_time:
        stamp = str(scheduled_time)
    else:
        # Two unresolved relative expressions are not the same logical action.
        # Collapse harmless whitespace/casing differences, never weekday/hour.
        stamp = "raw:" + " ".join((raw_time_expression or "").casefold().split())
    value = ":".join(
        (
            owner_user_id,
            source_message_id,
            source_mode,
            action_type.casefold(),
            title.strip().casefold(),
            stamp,
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_missing(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return ["manual_correction_required"]
    return [item for item in parsed if isinstance(item, str)]


def _dump_missing(values: list[str] | tuple[str, ...] | set[str]) -> str:
    return json.dumps(sorted(set(values)))


class ActionProposalService:
    """Transactional proposal service.  The caller owns the outer session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_proposal(self, proposal_id: str) -> ActionProposal:
        proposal = await self.db.scalar(select(ActionProposal).where(ActionProposal.id == proposal_id))
        if proposal is None:
            raise ActionProposalNotFoundError("Action proposal not found")
        return proposal

    async def _get_owned(self, proposal_id: str, user_id: str) -> ActionProposal:
        proposal = await self.get_proposal(proposal_id)
        if proposal.owner_user_id != user_id:
            raise ActionProposalOwnershipError("Only the assigned owner may access this proposal")
        return proposal

    async def list_for_owner(
        self,
        user_id: str,
        status_filter: str | None = None,
        conversation_id: str | None = None,
    ) -> list[ActionProposal]:
        statement = select(ActionProposal).where(ActionProposal.owner_user_id == user_id)
        if status_filter:
            statement = statement.where(ActionProposal.status == status_filter)
        if conversation_id:
            statement = statement.where(ActionProposal.conversation_id == conversation_id)
        return list((await self.db.scalars(statement.order_by(ActionProposal.created_at.desc()))).all())

    async def create_proposals_from_candidates(
        self,
        conversation_id: str,
        source_message_id: str,
        candidates: list[ActionCandidateDTO],
        *,
        owner_user_id: str,
        source_mode: str,
        created_by_user_id: str | None = None,
    ) -> list[ActionProposal]:
        """Persist candidates with one savepoint per insert conflict.

        A duplicate cannot roll back an earlier successful candidate in the same
        outer transaction.  Candidate-provided owners are deliberately ignored.
        """

        source = await self.db.get(Message, source_message_id)
        if source is None or source.conversation_id != conversation_id:
            raise ActionProposalNotFoundError("Source message not found")

        saved: list[ActionProposal] = []
        for candidate in candidates:
            normalized = normalize_action_time(
                raw_time_expression=candidate.raw_time_expression,
                reference_timestamp=source.created_at,
                trusted_timezone=None,
                candidate_datetime=candidate.scheduled_time,
                existing_missing_fields=candidate.missing_fields,
            )
            key = compute_proposal_idempotency_key(
                owner_user_id,
                source_message_id,
                candidate.action_type,
                candidate.title,
                normalized.scheduled_start_at,
                source_mode,
                normalized.raw_time_expression,
            )
            existing = await self.db.scalar(
                select(ActionProposal).where(ActionProposal.idempotency_key == key)
            )
            if existing is not None:
                saved.append(existing)
                continue

            missing = list(normalized.missing_fields)
            proposal = ActionProposal(
                conversation_id=conversation_id,
                source_message_id=source_message_id,
                owner_user_id=owner_user_id,
                created_by_user_id=created_by_user_id,
                source_mode=source_mode,
                action_type=candidate.action_type,
                status="needs_clarification" if missing else "pending_confirmation",
                title=candidate.title,
                details=candidate.details,
                location=getattr(candidate, "location", None),
                raw_time_expression=normalized.raw_time_expression,
                scheduled_start_at=normalized.scheduled_start_at,
                # Retained for legacy clients; it is always mirrored from the
                # canonical start time and never independently normalized.
                scheduled_time=normalized.scheduled_start_at,
                resolved_timezone=normalized.resolved_timezone,
                confidence_score=candidate.confidence_score,
                clarification_prompt=candidate.clarification_prompt,
                clarification_question=candidate.clarification_prompt,
                missing_fields=_dump_missing(missing),
                idempotency_key=key,
            )
            try:
                async with self.db.begin_nested():
                    self.db.add(proposal)
                    await self.db.flush()
                saved.append(proposal)
            except IntegrityError:
                existing = await self.db.scalar(
                    select(ActionProposal).where(ActionProposal.idempotency_key == key)
                )
                if existing is None:
                    raise
                saved.append(existing)

        await self.db.commit()
        return saved

    async def confirm_proposal(
        self,
        proposal_id: str,
        user_id: str,
        corrections: dict[str, Any] | None = None,
    ) -> ActionProposal:
        proposal = await self._get_owned(proposal_id, user_id)
        if proposal.status not in _ACTIVE_STATUSES:
            raise ActionProposalStatusError("Proposal is not confirmable")

        allowed = {
            "title",
            "details",
            "location",
            "scheduled_start_at",
            "scheduled_end_at",
            "due_at",
            "resolved_timezone",
            "timezone",
        }
        values = {key: value for key, value in (corrections or {}).items() if key in allowed}
        if "timezone" in values:
            values["resolved_timezone"] = values.pop("timezone")
        for temporal_field in ("scheduled_start_at", "scheduled_end_at", "due_at"):
            if temporal_field in values:
                values[temporal_field] = _as_utc(values[temporal_field])
        if "scheduled_start_at" in values:
            values["scheduled_time"] = values["scheduled_start_at"]

        missing = _load_missing(proposal.missing_fields)
        if proposal.status == "needs_clarification":
            source = await self.db.get(Message, proposal.source_message_id)
            if source is None:
                raise ActionProposalStatusError("Source message is unavailable")
            timezone = values.get("resolved_timezone")
            resolution = normalize_action_time(
                raw_time_expression=proposal.raw_time_expression,
                reference_timestamp=source.created_at,
                trusted_timezone=timezone,
                candidate_datetime=values.get("scheduled_start_at"),
                trusted_candidate_datetime=True,
                existing_missing_fields=missing,
            )
            remaining = set(resolution.missing_fields)
            for field in ("title", "details", "location"):
                if field in remaining and values.get(field):
                    remaining.remove(field)
            missing = list(remaining)
            if resolution.scheduled_start_at is not None:
                values["scheduled_start_at"] = resolution.scheduled_start_at
                values["scheduled_time"] = resolution.scheduled_start_at
            if resolution.resolved_timezone is not None:
                values["resolved_timezone"] = resolution.resolved_timezone
            if missing:
                raise ActionProposalStatusError("Proposal still has unresolved required fields")
            values["missing_fields"] = "[]"
        elif missing:
            raise ActionProposalStatusError("Proposal still has unresolved required fields")
        now = datetime.now(UTC)
        values.update(
            status="confirmed",
            confirmed_by_user_id=user_id,
            confirmed_at=now,
            updated_at=now,
        )
        result = await self.db.execute(
            update(ActionProposal)
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.owner_user_id == user_id,
                ActionProposal.status == proposal.status,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise ActionProposalStatusError("Proposal was already transitioned")
        await self.db.commit()
        return await self.get_proposal(proposal_id)

    async def reject_proposal(self, proposal_id: str, user_id: str) -> ActionProposal:
        proposal = await self._get_owned(proposal_id, user_id)
        if proposal.status not in _ACTIVE_STATUSES:
            raise ActionProposalStatusError("Proposal is not rejectable")
        result = await self.db.execute(
            update(ActionProposal)
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.owner_user_id == user_id,
                ActionProposal.status.in_(_ACTIVE_STATUSES),
            )
            .values(status="rejected", rejected_at=datetime.now(UTC))
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise ActionProposalStatusError("Proposal was already transitioned")
        await self.db.commit()
        return await self.get_proposal(proposal_id)

    async def clarify(
        self,
        proposal_id: str,
        user_id: str,
        answer: str,
        timezone: str | None,
    ) -> ActionProposal:
        """Resolve only missing fields; clarification can never confirm a proposal."""

        proposal = await self._get_owned(proposal_id, user_id)
        if proposal.status != "needs_clarification":
            raise ActionProposalStatusError("Proposal does not need clarification")
        if proposal.clarification_rounds >= MAX_CLARIFICATION_ROUNDS:
            raise ActionProposalStatusError("manual_correction_required")
        source = await self.db.get(Message, proposal.source_message_id)
        if source is None:
            raise ActionProposalStatusError("Source message is unavailable")

        missing = _load_missing(proposal.missing_fields)
        temporal_missing = {"time", "timezone"}.intersection(missing)
        if temporal_missing or _relative_time_expression(proposal.raw_time_expression):
            resolution = normalize_action_time(
                raw_time_expression=proposal.raw_time_expression,
                reference_timestamp=source.created_at,
                trusted_timezone=timezone,
                clarification_answer=answer,
                candidate_datetime=None,
                existing_missing_fields=missing,
            )
            remaining = set(resolution.missing_fields)
        else:
            resolution = TemporalResolution(None, proposal.raw_time_expression, None, tuple(missing))
            remaining = set(missing)

        # Deterministic structured clarification: an answer can fill only a
        # field that the persisted proposal explicitly marked as missing.
        non_temporal = [field for field in ("location", "title", "details") if field in remaining]
        resolved_non_temporal: dict[str, str] = {}
        if len(non_temporal) == 1 and answer.strip():
            field = non_temporal[0]
            resolved_non_temporal[field] = answer.strip()
            remaining.remove(field)
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "clarification_rounds": proposal.clarification_rounds + 1,
            "missing_fields": _dump_missing(remaining),
            "clarification_prompt": (
                None
                if not remaining
                else "Please provide the remaining execution details."
            ),
            "updated_at": now,
        }
        values["clarification_question"] = values["clarification_prompt"]
        values.update(resolved_non_temporal)
        if resolution.scheduled_start_at is not None:
            values["scheduled_start_at"] = resolution.scheduled_start_at
            values["scheduled_time"] = resolution.scheduled_start_at
        if resolution.resolved_timezone is not None:
            values["resolved_timezone"] = resolution.resolved_timezone
        values["status"] = (
            "pending_confirmation" if not remaining else "needs_clarification"
        )
        result = await self.db.execute(
            update(ActionProposal)
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.owner_user_id == user_id,
                ActionProposal.status == "needs_clarification",
                ActionProposal.clarification_rounds == proposal.clarification_rounds,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise ActionProposalStatusError("Proposal was already transitioned")
        await self.db.commit()
        return await self.get_proposal(proposal_id)

    async def mark_proposals_stale_for_message(self, message_id: str, *, commit: bool = True) -> int:
        result = await self.db.execute(
            update(ActionProposal)
            .where(
                ActionProposal.source_message_id == message_id,
                ActionProposal.status.in_(_ACTIVE_STATUSES),
            )
            .values(status="stale", stale_at=datetime.now(UTC))
        )
        if commit:
            await self.db.commit()
        return result.rowcount or 0
