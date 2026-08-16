"""Persistence repositories with explicit concurrency semantics."""

from src.repositories.translations import TranslationClaim, TranslationRepository

__all__ = ["TranslationClaim", "TranslationRepository"]
