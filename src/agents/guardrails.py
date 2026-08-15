"""Input and output guardrails for the Translation Agent (ADR-12, ADR-13).

Kept out of the node module so each check is unit-testable without compiling a
graph, and so `validate_output` and `fallback_translate` can share one
implementation rather than drifting apart.

Two rules govern how a failing check behaves, and they differ on purpose:

* **Checks with no dependency fail closed.** Length limits and the ISO-code shape
  check are pure arithmetic and string work; when they reject, the caller routes
  into the fallback chain.
* **Checks that depend on a library fail open.** If `langdetect` is missing or
  raises, `detect_language_code` returns None and the caller accepts the
  translation. Failing closed here would push every message onto the secondary
  provider the moment one dependency broke — the opposite of NFR-02.

Nothing in this module raises. That is what lets the nodes keep their own
no-raise guarantee without wrapping every call in try/except.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ISO 639-1: exactly two lowercase letters. Used to gate `target_language`
# before it is interpolated into the system prompt — a string of this shape
# cannot carry an injection payload.
ISO_639_1 = re.compile(r"^[a-z]{2}$")

# Anything longer is not a chat message. Bounds generation cost, latency and the
# injection surface at once, while sitting far above real traffic.
MAX_INPUT_CHARS = 2000

# Per context line. Five of these plus the message must stay a sane prompt size.
MAX_CONTEXT_MESSAGE_CHARS = 500

# Below this, langdetect says more about itself than about the text. ADR-11
# documents the same weakness at the input side, where the limit is 5 characters
# (_MIN_DETECT_CHARS); the output side sets its own, higher bar because a wrong
# answer there discards a finished translation rather than skipping a step.
MIN_VERIFY_CHARS = 20

# Newlines and control characters are what let a context line forge prompt
# structure; collapsing them to a space removes the capability entirely.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def is_supported_language_code(code: str) -> bool:
    """Report whether `code` has the shape of an ISO 639-1 code.

    A shape check, not an allowlist. The real allowlist (`SUPPORTED_LANGUAGES`)
    lives in `src/schemas/auth.py` on the auth branch and cannot be imported
    here yet; two lowercase letters is nonetheless enough to close the
    system-prompt injection channel.

    TODO(auth merge): tighten to SUPPORTED_LANGUAGES once src/schemas/ lands.
    """
    return bool(code) and bool(ISO_639_1.match(code))


def is_input_too_long(text: str) -> bool:
    """Report whether `text` exceeds the per-message input limit."""
    return len(text) > MAX_INPUT_CHARS


def sanitize_context_message(message: str) -> str:
    """Neutralise one context line so it cannot forge prompt structure.

    Conversation context is written by *other* participants, so this is the
    cross-user channel: without it, A could plant a line that closes the history
    section and opens a second message section, hijacking B's translation.

    Two transforms, and both are needed. Collapsing newlines stops the forged
    tags from starting their own line; escaping the angle brackets stops them
    from reading as tags at all, which flattening alone does not achieve.

    Escaping is free here because context lines are only ever *read* by the
    model — they are never echoed into the translation, so the entities cannot
    reach the recipient.

    Args:
        message: Raw context line as supplied by the ContextProvider.

    Returns:
        A single-line, length-capped, tag-free version safe to interpolate.
    """
    flattened = _CONTROL_CHARS.sub(" ", message)
    collapsed = " ".join(flattened.split())
    # Truncate on the real text, before escaping. Escaping expands `<` to four
    # characters and `&` to five, so cutting afterwards would drop context the
    # model was meant to read and could slice an entity in half.
    if len(collapsed) > MAX_CONTEXT_MESSAGE_CHARS:
        collapsed = collapsed[:MAX_CONTEXT_MESSAGE_CHARS].rstrip() + "…"
    return collapsed.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def detect_language_code(text: str) -> str | None:
    """Detect the language of `text` locally with langdetect (~2ms, no API call).

    The canonical implementation shared by input detection and output
    verification. Returns None when detection is unavailable or the result is not
    a usable ISO 639-1 code — langdetect emits region-qualified codes such as
    ``zh-cn`` and the contract only uses the base code.
    """
    try:
        from langdetect import DetectorFactory, detect

        # langdetect samples randomly; a fixed seed keeps results reproducible
        DetectorFactory.seed = 0
        code = detect(text).lower().split("-")[0]
    except Exception:
        return None

    return code if ISO_639_1.match(code) else None


def is_untranslated_output(
    translated_text: str,
    source_language: str,
    target_language: str,
) -> bool:
    """Report whether the model returned source-language text instead of a translation.

    Catches the refusal case this guard exists for — ``"I can't help with that."``
    is 24 characters, well under the length rule's 200-char floor, so it would
    otherwise be delivered to the recipient as though it were the translation —
    along with the model echoing the input untranslated or answering it.

    **The rule deliberately does not ask "is this text in the target language?"**
    langdetect is confidently wrong on the exact register this product targets:
    ``"Hotfix merged, CI green now"`` is reported as Dutch at 0.86, and
    ``"Docker Kubernetes Jenkins CI/CD pipeline"`` as German at 0.9999. Rejecting
    on ``detected != target`` therefore discarded correct translations of
    jargon-dense chat and served the untranslated original instead — the opposite
    of the intended effect. Raising the length gate does not help, because the
    German misfire is 40 characters, and neither does a confidence margin.

    Instead the detector is only ever asked to *agree with a value already
    known*: the source language established by ``detect_language``. A
    misclassification into some unrelated third language now proves nothing and
    changes nothing, while the failure modes above still produce output that
    matches the source. False negatives are the acceptable direction here — a
    missed refusal is one bad message, a false positive silently degrades every
    technical message in the conversation.

    Args:
        translated_text: Candidate translation to check.
        source_language: ISO 639-1 code the message was written in.
        target_language: ISO 639-1 code the translation should be in.

    Returns:
        True only when the text is long enough to judge and its detected
        language matches the source while differing from the target.
    """
    if len(translated_text) < MIN_VERIFY_CHARS:
        return False
    if not is_supported_language_code(source_language):
        return False
    if not is_supported_language_code(target_language):
        return False
    if source_language == target_language:
        return False

    detected = detect_language_code(translated_text)
    if detected is None:
        return False

    if detected == source_language:
        logger.info(
            "Translation still looks like %s, the source language, not %s",
            source_language,
            target_language,
        )
        return True

    return False
