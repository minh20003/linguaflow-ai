"""Embedding factory — selects a provider through the EMBEDDING_PROVIDER setting.

The same arrangement `llm.py` uses, for the same reason: free tiers differ, and
a provider that throttles mid-demo has to be swapped from `.env` rather than
from the code (ADR-25).

pgvector stores the vectors and measures the distance between them; it does not
produce them. The requirement that decides the choice here is multilingual
reach — unless "staging env" and "môi trường stg" land near each other, grouping
corrections by meaning achieves nothing.

Every provider must return vectors of `EMBEDDING_DIM` dimensions, because that
is the width of the columns. Changing provider to one with a different width is
a migration plus a pass to re-embed everything, never a configuration change,
and `embed` refuses rather than writing a vector the column cannot hold.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import Settings, get_settings
from src.database.models import EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Model used when EMBEDDING_MODEL is left empty. All three are multilingual;
# the widths differ, which is exactly why the width is pinned in the schema and
# checked below rather than trusted.
DEFAULT_MODELS: dict[str, str] = {
    # `models/text-embedding-004` was withdrawn and now answers 404. Its
    # replacement returns 3072 dimensions by default, which is why the width is
    # requested explicitly below rather than accepted.
    "gemini": "models/gemini-embedding-001",
    "openai": "text-embedding-3-small",
    # MiniLM-L12-v2 sat here and returns 384 dimensions, which the
    # `vector(768)` columns reject — the same shape of mistake as the two
    # above, and the reason `local` had never actually run.
    "local": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
}

# Which settings field carries each provider's key, and so — since
# pydantic-settings upper-cases field names — which variable to name in the
# error. `local` needs none: that is the point of it.
PROVIDER_KEY_FIELD: dict[str, str] = {
    "gemini": "google_api_key",
    "openai": "openai_api_key",
}


class EmbeddingConfigError(RuntimeError):
    """Raised when the provider is unknown, or its API key is missing."""


# Clients already built, keyed on the configuration that shapes them. The API
# key is deliberately not part of the key, exactly as in `llm.py`: it would put
# the secret into a module-level structure that any traceback dumping locals
# would render.
_CLIENTS: dict[tuple[str, str], Any] = {}


def _build_client(provider: str, model: str, api_key: str) -> Any:
    """Import and construct one provider's client.

    Imported inside the function so a provider nobody uses does not have to be
    installed — `sentence-transformers` in particular pulls in torch, which is
    several hundred megabytes and has no place in an image that will never call
    it (ADR-18).

    The key is passed in rather than left to the provider package to find. Both
    packages fall back to reading the environment, and this project keeps its
    keys in `.env`, which pydantic-settings reads *without* exporting — so the
    client would raise for a missing key that `get_embedder` had just confirmed
    was present. `embed` swallows every failure by design, so the visible effect
    was not an error but silence: both retrieval flags could be switched on and
    do nothing at all.
    """
    # The width is asked for, not accepted. `message_embeddings.embedding` and
    # `glossary_entries.embedding` are `vector(768)` columns, and both current
    # hosted models return something wider unless told otherwise — a vector of
    # the wrong width is rejected by the column, so this is the difference
    # between retrieval working and every insert failing.
    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=model, google_api_key=api_key, output_dimensionality=EMBEDDING_DIM
        )
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model, api_key=api_key, dimensions=EMBEDDING_DIM)

    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=model)


def get_embedder(settings: Settings | None = None) -> Any:
    """Return the embedding client for the configured provider.

    Args:
        settings: configuration to read. Defaults to the process settings.

    Raises:
        EmbeddingConfigError: unknown provider, or its API key is missing.
    """
    settings = settings or get_settings()
    provider = settings.embedding_provider

    if provider not in DEFAULT_MODELS:
        raise EmbeddingConfigError(
            f"Unknown EMBEDDING_PROVIDER: {provider}. "
            f"Expected one of: {', '.join(sorted(DEFAULT_MODELS))}"
        )

    # Checked before the provider package is imported, so a missing key reports
    # itself rather than surfacing as an ImportError about an absent package.
    key_field = PROVIDER_KEY_FIELD.get(provider)
    api_key = getattr(settings, key_field, "") if key_field else ""
    if key_field and not api_key:
        raise EmbeddingConfigError(
            f"EMBEDDING_PROVIDER={provider} but {key_field.upper()} is not set. "
            f"Add {key_field.upper()} to .env, or set EMBEDDING_PROVIDER=local "
            "to embed in-process without an API key."
        )

    model = settings.embedding_model or DEFAULT_MODELS[provider]
    cached = _CLIENTS.get((provider, model))
    if cached is None:
        cached = _build_client(provider, model, api_key)
        _CLIENTS[(provider, model)] = cached
    return cached


def embedding_model_name(settings: Settings | None = None) -> str:
    """Name the model an embedding came from, for the `embedding_model` column.

    Stored beside every vector so one produced by another model is recognisable
    instead of being compared in the wrong space — which returns a confident
    wrong answer rather than an error.
    """
    settings = settings or get_settings()
    return settings.embedding_model or DEFAULT_MODELS.get(
        settings.embedding_provider, ""
    )


async def embed(text: str, *, settings: Settings | None = None) -> list[float] | None:
    """Turn one piece of text into a vector, or return None.

    None on every failure, never an exception. Callers are a graph node that
    must not fail a translation and a background miner nobody is watching;
    neither has anything useful to do with an error, and both degrade to the
    behaviour they had before embeddings existed.

    Args:
        text: The text to embed. Blank text returns None without a call.
        settings: configuration to read. Defaults to the process settings.

    Returns:
        A vector of `EMBEDDING_DIM` floats, or None.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    try:
        client = get_embedder(settings)
        vector = await client.aembed_query(cleaned)
    except Exception as exc:
        logger.warning("Embedding %d characters failed: %s", len(cleaned), exc)
        return None

    if not vector:
        return None
    if len(vector) != EMBEDDING_DIM:
        # Refused rather than truncated or padded. The column has a fixed width,
        # and a vector reshaped to fit it would be silently meaningless: every
        # distance computed against it would be wrong and nothing would say so.
        logger.error(
            "Embedding provider returned %d dimensions, schema expects %d. "
            "Changing provider needs a migration and a re-embedding pass.",
            len(vector),
            EMBEDDING_DIM,
        )
        return None
    return list(vector)
