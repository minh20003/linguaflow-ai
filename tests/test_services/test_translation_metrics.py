"""Metrics coverage without high-cardinality request labels."""

from __future__ import annotations

import pytest

from src.services.language_resolver import LanguageResolver
from src.services.translation_metrics import TranslationMetrics


@pytest.mark.asyncio
async def test_language_detection_llm_counter_only_increments_for_arbitration():
    metrics = TranslationMetrics()

    async def llm_detector(_: str):
        return "en", 4

    resolver = LanguageResolver(lambda _: None, llm_detector, metrics)

    resolution = await resolver.resolve("This is enough text", "vi")

    assert resolution.language == "en"
    snapshot = metrics.snapshot()
    assert snapshot["language_detection_llm_total"] == 1
    assert "message_id" not in snapshot
    assert "user_id" not in snapshot
