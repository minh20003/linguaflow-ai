"""Nodes of the Translation Agent.

Node chain per docs/architecture_diagram.md section 2:
    detect_language -> build_context -> translate -> validate_output
                                                  -> fallback_translate

Every node takes the full ``AgentState`` and returns a dict holding only the
fields it changed; LangGraph merges those partial updates. That convention is
stated here once rather than repeated in each node's docstring.

Hard rule: no node raises. Failures are recorded in ``state["error"]`` and the
graph continues down the fallback path that returns the original text, so an LLM
outage never blocks the chat flow (NFR-02).
"""

from __future__ import annotations

import logging
import re
import time

from src.agents.context_provider import (
    DEFAULT_CONTEXT_SIZE,
    ContextProvider,
    NullContextProvider,
)
from src.agents.guardrails import (
    MAX_INPUT_CHARS,
    detect_language_code,
    is_input_too_long,
    is_supported_language_code,
    is_untranslated_output,
)
from src.agents.prompts import (
    DETECT_LANGUAGE_PROMPT,
    TRANSLATE_SYSTEM_PROMPT,
    TRANSLATE_USER_PROMPT,
    build_context_block,
)
from src.agents.state import AgentState
from src.services.fallback_translator import FALLBACK_MODEL_NAME, translate_with_secondary_provider
from src.services.llm import extract_text, get_llm

logger = logging.getLogger(__name__)

# Text with no letters at all (emoji, digits, punctuation, URLs) needs no translation
_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

# Below this length neither langdetect nor the LLM is reliable (e.g. "Ok", "Yes"),
# so keep the provisional language instead of spending an LLM call on a guess.
_MIN_DETECT_CHARS = 5

# A translation longer than this is usually the model explaining itself instead of
# translating. Compared against max(len(original) * ratio, floor) so that very short
# inputs are not flagged just because the ratio is easy to exceed.
_MAX_TRANSLATION_RATIO = 4
_MAX_TRANSLATION_FLOOR = 200

# Only the first N characters are sent for language detection
_DETECT_SAMPLE_CHARS = 500


def _detect_local(text: str) -> str | None:
    """Detect the language of an incoming message (~2ms, no API call).

    A thin wrapper over :func:`guardrails.detect_language_code`, kept as a
    separate name on purpose: detecting the *input* language and verifying the
    *output* language are different decisions, and tests must be able to stub one
    without silently capturing the other. They share one implementation so the
    two can never disagree about what a language code looks like.
    """
    return detect_language_code(text)


async def _detect_with_llm(text: str) -> tuple[str | None, int]:
    """Detect the language with the LLM. Slower but reliable on short text.

    Returns the language code (None on failure) and the elapsed milliseconds, so
    the caller can account for this call in the reported latency.
    """
    started = time.perf_counter()
    try:
        llm = get_llm()
        response = await llm.ainvoke(
            DETECT_LANGUAGE_PROMPT.format(text=text[:_DETECT_SAMPLE_CHARS])
        )
        detected = extract_text(response).lower()
    except Exception as exc:
        logger.warning("LLM language detection failed: %s", exc)
        return None, int((time.perf_counter() - started) * 1000)

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if not is_supported_language_code(detected):
        logger.warning("LLM language detection returned an invalid code: %r", detected)
        return None, elapsed_ms

    return detected, elapsed_ms


async def detect_language(state: AgentState) -> dict:
    """Determine the true source language of the message.

    Two-tier strategy that keeps LLM calls off the common path (ADR-11). Measured
    with Groq: langdetect ~2ms versus ~1285ms for an LLM call.

    1. Too short, or no letters: keep the provisional value, detect nothing.
    2. langdetect agrees with the provisional value: trust it, no LLM call. This
       is the common case — users usually write in the language they configured.
    3. langdetect disagrees, or fails: ask the LLM to arbitrate. langdetect's own
       answer is discarded here because it is unreliable on short text ("Ok anh"
       is detected as Tagalog), which is exactly why the two disagree.

    The incoming ``source_language`` is the provisional value (the sender's
    preferred_language) per docs/CONTRACT.md section 4.3.
    """
    original_text = (state.get("original_text") or "").strip()
    provisional = state.get("source_language", "")

    if not original_text:
        return {"error": "original_text is empty, cannot detect language"}

    if not _HAS_LETTER.search(original_text) or len(original_text) < _MIN_DETECT_CHARS:
        return {"source_language": provisional}

    local = _detect_local(original_text)

    # Fast path: langdetect agrees with the language the sender configured
    if local and local == provisional:
        return {"source_language": local}

    if local:
        logger.info(
            "langdetect (%s) disagrees with preferred_language (%s), asking the LLM",
            local,
            provisional,
        )

    detected, elapsed_ms = await _detect_with_llm(original_text)
    if detected:
        return {"source_language": detected, "latency_ms": elapsed_ms}

    # The LLM failed too. Keep the provisional value rather than langdetect's
    # answer: reaching this point means the two disagreed, and CONTRACT section
    # 4.3 forbids using langdetect's result in that case.
    return {"source_language": provisional, "latency_ms": elapsed_ms}


def make_build_context(
    context_provider: ContextProvider | None = None,
    limit: int = DEFAULT_CONTEXT_SIZE,
):
    """Create a build_context node bound to a specific context source.

    Uses a closure rather than a module global so several graphs can run side by
    side with different sources (a real one in production, a fake one in tests).

    Args:
        context_provider: Source of recent messages. Defaults to no context.
        limit: How many recent messages to request from the provider.

    Returns:
        The build_context node function, ready to add to a graph.
    """
    provider = context_provider or NullContextProvider()

    async def build_context(state: AgentState) -> dict:
        """Load recent conversation history, degrading to none on failure."""
        conversation_id = state.get("conversation_id", "")
        if not conversation_id:
            return {"context_messages": []}

        try:
            messages = await provider.get_recent_messages(conversation_id, limit)
        except Exception as exc:
            # Missing context degrades translation quality but must not block it
            logger.warning("build_context failed: %s", exc)
            return {"context_messages": []}

        return {"context_messages": list(messages)}

    return build_context


async def translate(state: AgentState) -> dict:
    """Translate the message with the LLM, including conversation context."""
    original_text = (state.get("original_text") or "").strip()
    target_language = state.get("target_language", "")

    if not original_text:
        return {"error": "original_text is empty, nothing to translate"}
    if not target_language:
        return {"error": "target_language was not provided"}

    # target_language is interpolated into the *system* prompt below, and it
    # originates from a user-editable profile field. Anything that is not a bare
    # ISO code could append arbitrary instructions there (ADR-12).
    if not is_supported_language_code(target_language):
        logger.warning("Rejected malformed target_language: %r", target_language)
        return {"error": "target_language is not a valid ISO 639-1 code"}

    if is_input_too_long(original_text):
        # Not truncated on purpose: half a translated message is worse than none,
        # and NFR-02 means the recipient still reads the original either way.
        logger.warning(
            "Rejected oversized message: %d chars, limit %d",
            len(original_text),
            MAX_INPUT_CHARS,
        )
        return {"error": "original_text exceeds the guardrail length limit"}

    system_prompt = TRANSLATE_SYSTEM_PROMPT.format(target_language=target_language)
    user_prompt = TRANSLATE_USER_PROMPT.format(
        context_block=build_context_block(state.get("context_messages", [])),
        original_text=original_text,
    )

    # Any latency already recorded by detect_language is carried forward so the
    # reported figure covers the whole agent run, not just this call
    detect_ms = state.get("latency_ms", 0)
    started = time.perf_counter()

    def total_latency_ms() -> int:
        """Elapsed time for this call plus whatever detection already spent."""
        return detect_ms + int((time.perf_counter() - started) * 1000)

    try:
        llm = get_llm()
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as exc:
        logger.warning("translate failed: %s", exc)
        return {
            "error": f"LLM call failed: {type(exc).__name__}",
            "latency_ms": total_latency_ms(),
        }

    model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "")

    return {
        "translated_text": extract_text(response),
        "model": str(model_name),
        "latency_ms": total_latency_ms(),
    }


async def validate_output(state: AgentState) -> dict:
    """Check the translation and decide whether to fall back.

    The fallback returns the original text verbatim: the recipient still reads
    the message, only untranslated. Required by NFR-02.
    """
    original_text = (state.get("original_text") or "").strip()
    translated_text = (state.get("translated_text") or "").strip()

    def fallback(reason: str) -> dict:
        """Build the state update that returns the original text unchanged."""
        logger.info("Falling back to the original text: %s", reason)
        update = {
            "translated_text": original_text,
            "is_valid": False,
            "is_fallback": True,
        }
        # ``error`` carries only reasons the request could not be processed —
        # an LLM outage, or input the guardrails rejected outright. A healthy
        # response that merely failed validation (too long, still in the source
        # language) is deliberately left out, so callers alerting on the field
        # don't page someone over a verbose translation. is_fallback already
        # flags the branch either way, and the reason above is logged.
        if state.get("error"):
            update["error"] = state["error"]
        return update

    if state.get("error"):
        return fallback(state["error"])
    if not translated_text:
        return fallback("the LLM returned empty content")

    max_length = max(
        len(original_text) * _MAX_TRANSLATION_RATIO, _MAX_TRANSLATION_FLOOR
    )
    if len(translated_text) > max_length:
        return fallback(
            f"translation is {len(translated_text)} chars, over the "
            f"{max_length} limit — the model likely explained instead of translating"
        )

    # A refusal, an untranslated echo, and the model answering instead of
    # translating all leave source-language text in the output. The length rule
    # above misses all three when the response is short — "I can't help with
    # that." is 24 characters, far under the 200-char floor (ADR-13).
    source_language = state.get("source_language", "")
    target_language = state.get("target_language", "")
    if is_untranslated_output(translated_text, source_language, target_language):
        return fallback(
            f"translation still reads as {source_language}, not {target_language} — "
            "the model likely refused, echoed the source, or answered instead"
        )

    return {"is_valid": True, "is_fallback": False}


async def fallback_translate(state: AgentState) -> dict:
    """Try the secondary provider before giving up on translating (ADR-07).

    Only reached after validate_output has already written the original text into
    the state, so returning nothing here simply leaves that safe value in place —
    the recipient still receives the message either way (NFR-02).

    ``is_fallback`` deliberately stays True even when this succeeds: the result
    did not come from the configured LLM, and the client should keep showing the
    degraded-quality indicator. ``model`` records which provider produced it.
    """
    original_text = (state.get("original_text") or "").strip()
    source_language = state.get("source_language", "")
    target_language = state.get("target_language", "")

    # The same guardrails the LLM path enforces. Without them an oversized or
    # malformed request would still reach Google's endpoint (ADR-15).
    if not is_supported_language_code(target_language):
        return {}
    if is_input_too_long(original_text):
        return {}

    # This branch is the slowest path in the graph, so leaving it out of
    # latency_ms would under-report exactly the case NFR-01 needs to see.
    elapsed_ms = state.get("latency_ms", 0)
    started = time.perf_counter()

    translated = await translate_with_secondary_provider(
        original_text,
        target_language=target_language,
        # Empty when detection itself failed; the provider then detects its own
        source_language=source_language,
    )
    elapsed_ms += int((time.perf_counter() - started) * 1000)

    if not translated:
        return {"latency_ms": elapsed_ms}

    # This output reaches the recipient without passing back through
    # validate_output, so it is verified here or not at all.
    if is_untranslated_output(translated, source_language, target_language):
        logger.warning("Discarded secondary translation: still reads as the source")
        return {"latency_ms": elapsed_ms}

    logger.info("Secondary provider translated the message after the LLM path failed")
    return {
        "translated_text": translated,
        "model": FALLBACK_MODEL_NAME,
        "latency_ms": elapsed_ms,
    }


async def passthrough(state: AgentState) -> dict:
    """Branch taken when the source and target languages match.

    Skips the LLM entirely (the "yes" branch of the agent flow).
    """
    return {
        "translated_text": state.get("original_text", ""),
        "is_valid": True,
        "is_fallback": False,
        "latency_ms": state.get("latency_ms", 0),
    }
