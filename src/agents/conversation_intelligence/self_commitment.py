"""Proactive first-person self-commitment detection (B-10)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.conversation_intelligence.observability import build_runnable_config
from src.agents.conversation_intelligence.parsing import invoke_with_repair
from src.agents.conversation_intelligence.prompts import (
    SELF_COMMITMENT_SYSTEM_PROMPT,
    build_self_commitment_user_prompt,
)
from src.config import Settings, get_settings
from src.schemas.intelligence import (
    ActionCandidateDTO,
    ActionExtractionPayload,
)
from src.services.llm import get_intelligence_llm
from src.services.relative_time import mentions_relative_time


def _local_reference(reference: datetime, sender_timezone: str | None) -> str:
    """Describe when the message was sent, in the clock the sender was reading.

    The model resolves "mai" by counting a day from this string, so the date in
    it has to be the sender's date. Handing it the raw UTC instant was wrong for
    every message sent between midnight and 07:00 in Hanoi: UTC is still on the
    previous day there, so "mai" came back one day early and the appointment was
    booked for today. Nothing downstream could catch it -- a date is a date, and
    `normalize_action_time` only re-resolves the expressions in its own small
    grammar.

    An unknown timezone keeps UTC and says so, rather than silently implying the
    sender was reading a clock nobody has claimed.
    """
    zone = _valid_zone(sender_timezone)
    if zone is None:
        return f"{reference.astimezone(UTC).isoformat()} (UTC; the sender's own timezone is unknown)"
    local = reference.astimezone(zone)
    return f"{local.isoformat()} (local time for the sender, timezone {zone.key})"


def _valid_zone(name: str | None) -> ZoneInfo | None:
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


# A promise the sender makes in so many words.
_COMMITMENT_PHRASES = (
    "i'll", "i will", "i am going to", "let me ", "i can do", "i'm taking",
    "tôi sẽ", "mình sẽ", "em sẽ", "anh sẽ", "chị sẽ", "tớ sẽ", "tui sẽ",
    "để tôi", "để mình", "để em", "mình nhận", "em nhận", "mình lo", "em lo",
    "mình làm", "mình gửi", "sẽ gửi", "sẽ làm", "sẽ hoàn thành",
)

# Words that settle or name a meeting. Kept, but no longer the only way in.
_MEETING_WORDS = (
    "chốt", "hẹn", "họp", "gặp", "lịch", "deadline", "hạn chót",
    "meeting", "let's meet", "see you", "appointment", "schedule", "sync",
)

# A clock somebody read out: "6h", "6h30", "18 giờ", "3:30", "7pm". The same
# shape the relative-time grammar accepts, minus the day, because here it only
# has to answer "is a time being talked about at all".
_CLOCK_MENTION = re.compile(
    r"(?<![\d/])\d{1,2}\s*(?::\d{2}|h\d{0,2}|g\d{2}|giờ|(?<![a-z])[ap]m)\b",
    re.IGNORECASE,
)


# Phrasings that put the whole sentence in doubt rather than settling anything.
# Narrower than the list this replaces: only conditionals and hedges, no
# past-tense words. "hôm qua" used to sit here and cost "Hôm qua mình chưa
# chốt, mai 6h gặp nhé" its appointment -- a past reference inside a sentence
# that settles a future meeting is ordinary speech, and telling the two apart is
# reading, not substring matching. What is left is overridden by a stated day
# and clock anyway, so a hedge cannot swallow a concrete arrangement either.
_HYPOTHETICAL_PHRASES = (
    "if i ", "if we ", "maybe", "perhaps",
    "nếu ", "chắc là", "có thể là", "không biết có",
)


def _worth_examining(text: str) -> bool:
    """Whether this message is worth spending a model call on.

    A cheap gate, not a decision -- the model still judges everything that gets
    through, and rule 2 of its prompt is what actually rejects a request aimed
    at somebody else or an event already past.

    A *time* is a signal in its own right, and that is the part that used to be
    missing. The gate demanded a word from a keyword list, so an appointment
    settled the way people actually settle one -- "Ok 6h chiều mai nhé", "Vậy
    trưa thứ 5 lúc 12h nha" -- was thrown away before anything read it, purely
    for containing none of "chốt", "hẹn" or "họp". A named day together with a
    clock is close enough to arranging something to be worth a look, and it
    outranks every hedge in the sentence around it: somebody who names both has
    stopped speculating.
    """
    lowered = text.casefold()
    if mentions_relative_time(lowered) and _CLOCK_MENTION.search(lowered):
        return True
    if any(phrase in lowered for phrase in _HYPOTHETICAL_PHRASES):
        return False
    if any(phrase in lowered for phrase in _COMMITMENT_PHRASES):
        return True
    return any(word in lowered for word in _MEETING_WORDS)


async def detect_self_commitments(
    message_text: str,
    sender_id: str,
    sender_name: str,
    reference_timestamp: datetime | None,
    conversation_id: str,
    message_id: str,
    settings: Settings | None = None,
    provider: str | None = None,
    sender_timezone: str | None = None,
) -> list[ActionCandidateDTO]:
    """Detect proactive first-person commitments made by the sender (B-10)."""
    clean_text = message_text.strip()
    if not clean_text:
        return []
    if not _worth_examining(clean_text):
        return []

    settings = settings or get_settings()
    ref_time = reference_timestamp or datetime.now(UTC)
    ref_time_str = _local_reference(ref_time, sender_timezone)

    schema_json = json.dumps(ActionExtractionPayload.model_json_schema(), indent=2)
    system_prompt = SELF_COMMITMENT_SYSTEM_PROMPT.format(
        sender_id=sender_id,
        reference_timestamp=ref_time_str,
        schema_json=schema_json,
    )
    user_prompt = build_self_commitment_user_prompt(
        message_text=clean_text,
        sender_id=sender_id,
        sender_name=sender_name,
        reference_timestamp=ref_time_str,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    llm = get_intelligence_llm(settings=settings, provider=provider)
    timeout = float(settings.llm_timeout_seconds)

    runnable_config = build_runnable_config(
        operation="detect_self_commitments",
        conversation_id=conversation_id,
        message_id=message_id,
    )

    payload = await invoke_with_repair(
        llm=llm,
        messages=messages,
        schema=ActionExtractionPayload,
        operation="detect_self_commitments",
        timeout=timeout,
        provider=provider or settings.llm_provider,
        model=settings.llm_model,
        conversation_id=conversation_id,
        message_id=message_id,
        runnable_config=runnable_config,
    )

    # Invariant: Force owner_user_id to sender_id for self-commitments
    validated_candidates: list[ActionCandidateDTO] = []
    for candidate in payload.candidates:
        candidate.owner_user_id = sender_id
        validated_candidates.append(candidate)

    return validated_candidates
