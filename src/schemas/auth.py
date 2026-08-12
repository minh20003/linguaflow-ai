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


def normalize_language(value: str) -> str:
    """Lower-case a language code and reject anything unsupported.

    Shared by every schema that accepts a language, so the allowlist is checked
    in exactly one place (docs/CONTRACT.md section 1).

    Raises:
        ValueError: The code is not in SUPPORTED_LANGUAGES.
    """
    normalized = value.lower()
    if normalized not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language code: {value}. "
            f"Supported codes: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
        )
    return normalized


def normalize_email(value: str) -> str:
    """Trim and lower-case an email so one address means one account.

    Applied on both registration and login; without it, registering as
    `Foo@x.com` would create an account that `foo@x.com` cannot reach.
    """
    return value.strip().lower()


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: str = Field(..., min_length=1, max_length=255, description="User email")
    password: str = Field(..., min_length=1, description="User password")

    @field_validator("email")
    @classmethod
    def normalize(cls, v: str) -> str:
        """Match the normalisation registration applies."""
        return normalize_email(v)


class RegisterRequest(BaseModel):
    """Request schema for creating an account."""

    email: str = Field(..., min_length=3, max_length=255, description="User email")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    preferred_language: str = Field(
        default="en",
        description="ISO 639-1 code the user wants to READ messages in",
        min_length=2,
        max_length=10,
    )

    @field_validator("email")
    @classmethod
    def normalize(cls, v: str) -> str:
        """Trim and lower-case so one address means one account."""
        return normalize_email(v)

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that the language code is supported."""
        return normalize_language(v)


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
        return normalize_language(v)
