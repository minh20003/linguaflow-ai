"""Summarization logic for on-demand conversation summary (B-03)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.conversation_intelligence.observability import build_runnable_config
from src.agents.conversation_intelligence.parsing import invoke_with_repair
from src.agents.conversation_intelligence.prompts import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)
from src.config import Settings, get_settings
from src.schemas.intelligence import (
    ConversationSummaryPayload,
    ConversationSummaryResponse,
)
from src.services.llm import get_llm


def format_transcript_line(created_at_str: str, speaker_name: str, text: str) -> str:
    """Format one message line for summarization grounding."""
    clean_text = text.replace("\r", " ").replace("\n", " ").strip()
    return f"[{created_at_str}] {speaker_name}: {clean_text}"


async def generate_conversation_summary(
    transcript: str,
    target_language: str,
    message_count: int,
    window_start_at: Any | None,
    window_end_at: Any | None,
    conversation_id: str,
    settings: Settings | None = None,
    provider: str | None = None,
) -> ConversationSummaryResponse:
    """Generate structured conversation summary with LLM grounding and repair retry."""
    settings = settings or get_settings()

    # Fast bypass for empty conversation
    if not transcript.strip() or message_count == 0:
        return ConversationSummaryResponse(
            summary="",
            key_points=[],
            decisions=[],
            open_items=[],
            message_count=0,
            target_language=target_language,
            window_start_at=None,
            window_end_at=None,
        )

    schema_json = json.dumps(ConversationSummaryPayload.model_json_schema(), indent=2)
    system_prompt = SUMMARY_SYSTEM_PROMPT.format(
        target_language=target_language,
        schema_json=schema_json,
    )
    user_prompt = build_summary_user_prompt(
        transcript=transcript,
        target_language=target_language,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    llm = get_llm(settings=settings, provider=provider)
    timeout = float(settings.llm_timeout_seconds)

    runnable_config = build_runnable_config(
        operation="conversation_summary",
        conversation_id=conversation_id,
        target_language=target_language,
        message_count=message_count,
    )

    payload = await invoke_with_repair(
        llm=llm,
        messages=messages,
        schema=ConversationSummaryPayload,
        operation="conversation_summary",
        timeout=timeout,
        provider=provider or settings.llm_provider,
        model=settings.llm_model,
        conversation_id=conversation_id,
        runnable_config=runnable_config,
    )

    return ConversationSummaryResponse(
        summary=payload.summary,
        key_points=payload.key_points,
        decisions=payload.decisions,
        open_items=payload.open_items,
        message_count=message_count,
        target_language=target_language,
        window_start_at=window_start_at,
        window_end_at=window_end_at,
    )
