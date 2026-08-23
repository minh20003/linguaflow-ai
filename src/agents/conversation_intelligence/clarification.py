"""Ambiguity analysis and clarification prompt generation (B-08)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.conversation_intelligence.observability import build_runnable_config
from src.agents.conversation_intelligence.parsing import invoke_with_repair
from src.agents.conversation_intelligence.prompts import (
    CLARIFICATION_SYSTEM_PROMPT,
    build_clarification_user_prompt,
)
from src.config import Settings, get_settings
from src.schemas.intelligence import (
    ClarificationAnalysisPayload,
    ClarificationAnalysisResponse,
)
from src.services.llm import get_llm


async def analyze_message_ambiguity(
    message_text: str,
    sender_name: str,
    reference_timestamp: datetime | None,
    conversation_id: str,
    message_id: str,
    settings: Settings | None = None,
    provider: str | None = None,
) -> ClarificationAnalysisResponse:
    """Analyze whether a message contains execution-relevant ambiguity (B-08)."""
    clean_text = message_text.strip()
    if not clean_text:
        return ClarificationAnalysisResponse(
            is_ambiguous=False,
            needs_clarification=False,
            reason="Message is empty",
            suggested_clarification_prompt=None,
        )

    settings = settings or get_settings()
    ref_time = reference_timestamp or datetime.now(UTC)
    ref_time_str = ref_time.isoformat()

    schema_json = json.dumps(ClarificationAnalysisPayload.model_json_schema(), indent=2)
    system_prompt = CLARIFICATION_SYSTEM_PROMPT.format(schema_json=schema_json)
    user_prompt = build_clarification_user_prompt(
        message_text=clean_text,
        sender_name=sender_name,
        reference_timestamp=ref_time_str,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    llm = get_llm(settings=settings, provider=provider)
    timeout = float(settings.llm_timeout_seconds)

    runnable_config = build_runnable_config(
        operation="analyze_clarification",
        conversation_id=conversation_id,
        message_id=message_id,
    )

    payload = await invoke_with_repair(
        llm=llm,
        messages=messages,
        schema=ClarificationAnalysisPayload,
        operation="analyze_clarification",
        timeout=timeout,
        provider=provider or settings.llm_provider,
        model=settings.llm_model,
        conversation_id=conversation_id,
        message_id=message_id,
        runnable_config=runnable_config,
    )

    return ClarificationAnalysisResponse(
        is_ambiguous=payload.is_ambiguous,
        needs_clarification=payload.needs_clarification,
        reason=payload.reason,
        suggested_clarification_prompt=payload.suggested_clarification_prompt,
    )
