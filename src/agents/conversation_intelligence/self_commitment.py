"""Proactive first-person self-commitment detection (B-10)."""

from __future__ import annotations

import json
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
    # Deterministic gate, ahead of the model. Two jobs: keep questions,
    # conditionals and finished actions out, and keep the cost of scanning every
    # message down by not calling a model on the great majority that commit to
    # nothing.
    #
    # The positive list covers appointments as well as first-person promises.
    # Restricted to "sẽ"/"I will" it rejected the commonest way a time actually
    # gets settled in chat -- "Ok chốt nhé, 3h chiều thứ Sáu họp ở phòng A"
    # contains no "sẽ" at all -- so nothing in a real conversation was ever
    # examined. The list stays a cheap pre-filter, not the decision: the model
    # still judges every message that gets past it, and rule 2 of its prompt is
    # what actually rejects a request aimed at somebody else.
    lowered = clean_text.casefold()
    negatives = (
        "maybe", "if i ", "i sent", "john will", "bạn gửi", "you send", "nếu tôi", "đã gửi",
        "hôm qua", "vừa xong", "yesterday", "đã họp",
    )
    positives = (
        # A promise the sender makes.
        "i'll", "i will", "i am going to", "let me ",
        "tôi sẽ", "mình sẽ", "em sẽ", "anh sẽ", "tớ sẽ", "để tôi", "để mình", "mình nhận",
        # A time being settled. These carry the appointments the old list missed.
        "chốt", "hẹn", "họp", "gặp", "lịch", "meeting", "let's meet", "see you",
        "appointment", "schedule",
    )
    if any(token in lowered for token in negatives) or not any(token in lowered for token in positives):
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
