"""ADR-11 source-language resolution, independent of LangGraph nodes."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from src.services.translation_metrics import TranslationMetrics, get_translation_metrics

_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_MIN_DETECT_CHARS = 5

LocalDetector = Callable[[str], str | None]
LlmDetector = Callable[[str], Awaitable[tuple[str | None, int]]]


@dataclass(frozen=True)
class LanguageResolution:
    """Resolved language plus latency spent on LLM arbitration."""

    language: str
    latency_ms: int = 0


class LanguageResolver:
    """Resolve a source language with the two-tier ADR-11 policy."""

    def __init__(
        self,
        local_detector: LocalDetector,
        llm_detector: LlmDetector,
        metrics: TranslationMetrics | None = None,
    ) -> None:
        self._local_detector = local_detector
        self._llm_detector = llm_detector
        self._metrics = metrics or get_translation_metrics()

    async def resolve(self, text: str, language_hint: str) -> LanguageResolution:
        """Return the confirmed language, falling back safely to the hint.

        Short/non-alphabetic content keeps the hint. A matching local result is
        accepted. Any disagreement or local failure is arbitrated by the LLM;
        an arbitration failure also retains the hint.
        """
        if not text or not _HAS_LETTER.search(text) or len(text) < _MIN_DETECT_CHARS:
            return LanguageResolution(language_hint)

        local = self._local_detector(text)
        if local and local == language_hint:
            return LanguageResolution(local)

        self._metrics.increment("language_detection_llm_total")
        detected, latency_ms = await self._llm_detector(text)
        return LanguageResolution(detected or language_hint, latency_ms)
