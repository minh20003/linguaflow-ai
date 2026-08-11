"""Tests for the Langfuse integration (F-03.4).

Focus: neither missing configuration nor a failed init may break the
translation flow.
"""

from __future__ import annotations

from unittest.mock import patch

from src.agents import observability
from src.agents.observability import build_runnable_config, get_langfuse_handler

MODULE = "src.agents.observability"


def setup_function() -> None:
    """Clear the cache between tests — the handler is memoised with lru_cache."""
    observability._init_langfuse_handler.cache_clear()


def make_settings(public_key: str = "", secret_key: str = ""):
    """Create a mock settings object for observability tests."""
    class FakeSettings:
        langfuse_public_key = public_key
        langfuse_secret_key = secret_key
        langfuse_host = "https://cloud.langfuse.com"

    return FakeSettings()


def test_no_keys():
    """Missing both keys must skip tracing and return None."""
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        assert get_langfuse_handler() is None


def test_single_key():
    """A missing secret_key must also skip tracing, not half-initialise it."""
    with patch(f"{MODULE}.get_settings", return_value=make_settings(public_key="pk")):
        assert get_langfuse_handler() is None


def test_tracing_disabled():
    """When tracing is disabled, runnable config must be empty."""
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        assert build_runnable_config() == {}


def test_metadata():
    """Provided metadata keys must be attached under config metadata."""
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        config = build_runnable_config(conversation_id="c1", message_id="m1")

    assert config["metadata"] == {"conversation_id": "c1", "message_id": "m1"}
    assert "callbacks" not in config


def test_none_metadata():
    """None values in metadata arguments must be filtered out."""
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        config = build_runnable_config(conversation_id="c1", translation_id=None)

    assert config["metadata"] == {"conversation_id": "c1"}


def test_init_failure():
    """A Langfuse failure (bad key, no connection) must still let the agent run."""
    settings = make_settings(public_key="pk", secret_key="sk")

    with (
        patch(f"{MODULE}.get_settings", return_value=settings),
        patch("langfuse.Langfuse", side_effect=RuntimeError("connection refused")),
    ):
        assert get_langfuse_handler() is None
        assert build_runnable_config() == {}


