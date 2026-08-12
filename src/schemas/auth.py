"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Supported languages based on ISO 639-1 codes
SUPPORTED_LANGUAGES = {
    "en",  # English
    "vi",  # Vietnamese
    "ja",  # Japanese
    "zh",  # Chinese
    "ko",  # Korean
    "fr",  # French
    "de",  # German
    "es",  # Spanish
    "th",  # Thai
    "pt",  # Portuguese
    "ru",  # Russian
    "ar",  # Arabic
    "hi",  # Hindi
}


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: str = Field(..., min_length=1, max_length=255, description="User email")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """Response schema for successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Response schema for user data (excludes sensitive fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    preferred_language: str
    created_at: datetime


class UpdateLanguageRequest(BaseModel):
    """Request schema for updating preferred language."""

    preferred_language: str = Field(
        ...,
        description="ISO 639-1 language code",
        min_length=2,
        max_length=10,
        examples=["en", "vi", "ja"],
    )

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that the language code is supported."""
        normalized = v.lower()
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language code: {v}. "
                f"Supported codes: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            )
        return normalized
