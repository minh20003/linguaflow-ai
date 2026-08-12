"""State schema for the Translation Agent.

Defined by docs/CONTRACT.md section 2. Field names are shared across Frontend,
Backend and Agent — do not rename them here without updating the contract first.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """State passed between nodes of the translation graph.

    ``total=False`` lets each node return only the fields it changes; LangGraph
    merges those partial updates into the shared state.
    """

    # Identifiers supplied by the Chat Service
    conversation_id: str
    message_id: str
    sender_id: str

    # Input
    original_text: str
    source_language: str  # ISO 639-1; provisional on entry, overwritten by detection
    target_language: str  # Taken from users.preferred_language of the recipient

    # Conversation context
    context_messages: list[str]  # 3-5 recent messages, preformatted for the prompt

    # Output
    translated_text: str
    translation_id: str  # Row id in translation_results, required by F-05
    is_valid: bool  # Result of the validate_output node
    is_fallback: bool  # True when the original text is returned after a failure

    # Measurements persisted to translation_results and reported to Langfuse
    model: str
    latency_ms: int

    error: str
