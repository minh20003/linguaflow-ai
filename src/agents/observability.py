"""Langfuse tracing for the Translation Agent (F-03.4).

Verified against langfuse 4.14.3: `CallbackHandler` lives in
`langfuse.langchain` and only accepts `public_key`; `secret_key` and `host` are
configured on the `Langfuse` client. Versions 2.x and 3.x expose a different
API — re-check this module if the pinned major version changes.

Tracing is optional and degrades silently: a missing key, a missing package or a
failed client init all return None and leave the translation flow untouched.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _init_langfuse_handler() -> Any | None:
    """Build the Langfuse callback handler once per process."""
    settings = get_settings()

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info(
            "LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY not set, skipping tracing"
        )
        return None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.info("langfuse package not installed, skipping tracing")
        return None

    try:
        # Initialise the singleton client the handler will reuse
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return CallbackHandler(public_key=settings.langfuse_public_key)
    except Exception as exc:
        logger.warning("Langfuse init failed, skipping tracing: %s", exc)
        return None


def get_langfuse_handler() -> Any | None:
    """Return the Langfuse callback handler, or None when unavailable."""
    return _init_langfuse_handler()


def build_runnable_config(**metadata: Any) -> dict[str, Any]:
    """Build the config to pass to ``graph.ainvoke()``.

    Attaches the Langfuse callback when available, plus per-request metadata
    (conversation_id, message_id, ...) used to filter traces in the Langfuse UI.

    Example:
        config = build_runnable_config(conversation_id=cid, message_id=mid)
        result = await graph.ainvoke(state, config=config)
    """
    config: dict[str, Any] = {}

    handler = get_langfuse_handler()
    if handler is not None:
        config["callbacks"] = [handler]

    if metadata:
        config["metadata"] = {k: v for k, v in metadata.items() if v is not None}

    return config
