"""Schemas package."""

from src.schemas.auth import (
    SUPPORTED_LANGUAGES,
    LoginRequest,
    TokenResponse,
    UpdateLanguageRequest,
    UserResponse,
)

__all__ = [
    "LoginRequest",
    "SUPPORTED_LANGUAGES",
    "TokenResponse",
    "UpdateLanguageRequest",
    "UserResponse",
]
