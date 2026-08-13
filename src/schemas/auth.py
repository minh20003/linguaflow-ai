"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    "id",  # Indonesian
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
    remember: bool = False

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email address")
        return value


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)
    preferred_language: str = Field(default="vi", min_length=2, max_length=10)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens and underscores")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_register_email(cls, value: str) -> str:
        return LoginRequest.normalize_email(value)

    @field_validator("preferred_language")
    @classmethod
    def validate_registration_language(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError("Unsupported language code")
        return normalized


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=32)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=32)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_forgot_email(cls, value: str) -> str:
        return LoginRequest.normalize_email(value)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=32)
    new_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Response schema for successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Response schema for user data (excludes sensitive fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str | None = None
    display_name: str | None = None
    role: str
    preferred_language: str
    created_at: datetime

    @model_validator(mode="after")
    def fill_legacy_profile_names(self) -> "UserResponse":
        """Keep profiles usable for accounts created before name fields existed."""
        fallback = self.email.split("@", 1)[0]
        self.username = self.username or fallback
        self.display_name = self.display_name or self.username
        return self


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


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
