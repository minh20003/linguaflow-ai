"""Tests for the secondary translation provider (ADR-07).

No test reaches the network: the blocking deep-translator call is patched out.
What matters here is that every failure mode returns None rather than raising,
because the caller treats None as "keep the original text" (NFR-02).

Fixtures live in this file rather than tests/conftest.py to avoid conflicting
with feature/f-01-2-auth-user-config, which rewrites conftest.
"""

from __future__ import annotations

import time

import pytest

from src.services.fallback_translator import translate_fallback

MODULE = "src.services.fallback_translator"


def make_settings(is_enabled: bool = True, timeout: int = 5):
    """Create a mock settings object for fallback translator tests."""
    class FakeSettings:
        fallback_translator_enabled = is_enabled
        fallback_translator_timeout_seconds = timeout

    return FakeSettings()



@pytest.fixture
def settings_enabled(monkeypatch):
    monkeypatch.setattr(f"{MODULE}.get_settings", make_settings)


@pytest.mark.asyncio
async def test_success(monkeypatch, settings_enabled):
    """Successful secondary translation returns the translated text."""
    monkeypatch.setattr(f"{MODULE}._translate_sync", lambda *a: "Have you deployed?")

    result = await translate_fallback("Deploy xong chưa?", "en", "vi")

    assert result == "Have you deployed?"


@pytest.mark.asyncio
async def test_provider_error(monkeypatch, settings_enabled):
    """A provider outage must be reported as None, never raised at the node."""

    def boom(*args):
        raise ConnectionError("google unreachable")

    monkeypatch.setattr(f"{MODULE}._translate_sync", boom)

    assert await translate_fallback("Chào bạn", "en", "vi") is None


@pytest.mark.asyncio
async def test_timeout(monkeypatch):
    """A slow provider must not hold the chat flow open indefinitely."""
    monkeypatch.setattr(f"{MODULE}.get_settings", lambda: make_settings(timeout=1))
    monkeypatch.setattr(f"{MODULE}._translate_sync", lambda *a: time.sleep(1.5))

    assert await translate_fallback("Chào bạn", "en", "vi") is None


@pytest.mark.asyncio
async def test_disabled(monkeypatch):
    """FALLBACK_TRANSLATOR_ENABLED=false restores the plain passthrough."""
    monkeypatch.setattr(f"{MODULE}.get_settings", lambda: make_settings(is_enabled=False))

    def fail(*args):
        raise AssertionError("provider must not be called when disabled")

    monkeypatch.setattr(f"{MODULE}._translate_sync", fail)

    assert await translate_fallback("Chào bạn", "en", "vi") is None


@pytest.mark.asyncio
async def test_same_language(monkeypatch, settings_enabled):
    """Secondary provider must not be called when source and target languages are the same."""

    def fail(*args):
        raise AssertionError("provider must not be called for identical languages")

    monkeypatch.setattr(f"{MODULE}._translate_sync", fail)

    assert await translate_fallback("Chào bạn", "vi", "vi") is None


@pytest.mark.asyncio
async def test_missing_input(monkeypatch, settings_enabled):
    """Secondary provider must not be called without text or target language."""

    def fail(*args):
        raise AssertionError("provider must not be called without text and target")

    monkeypatch.setattr(f"{MODULE}._translate_sync", fail)

    assert await translate_fallback("", "en", "vi") is None
    assert await translate_fallback("Chào bạn", "", "vi") is None


@pytest.mark.asyncio
async def test_empty_result(monkeypatch, settings_enabled):
    """deep-translator can return None or blank text; both mean 'no result'."""
    monkeypatch.setattr(f"{MODULE}._translate_sync", lambda *a: "   ")
    assert await translate_fallback("Chào bạn", "en", "vi") is None

    monkeypatch.setattr(f"{MODULE}._translate_sync", lambda *a: None)
    assert await translate_fallback("Chào bạn", "en", "vi") is None


@pytest.mark.asyncio
async def test_auto_detect_source(monkeypatch, settings_enabled):
    """When the agent's own detection failed, the provider detects source language instead."""
    captured = {}

    def capture(text, source_language, target_language):
        captured["source"] = source_language
        return "Hello"

    monkeypatch.setattr(f"{MODULE}._translate_sync", capture)

    assert await translate_fallback("Chào bạn", "en") == "Hello"
    assert captured["source"] == ""


