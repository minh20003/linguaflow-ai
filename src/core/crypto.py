"""Symmetric encryption for secrets this application stores on a user's behalf.

Exactly one thing needs it today: the Google refresh token. That token is not
application data — it is standing permission to read and write somebody's real
calendar, and it stays valid until they revoke it. A database dump that leaks
message text is bad; one that leaks refresh tokens hands an attacker an account
elsewhere, which is a different order of harm and deserves a different defence.

Fernet rather than a hand-rolled scheme. It is authenticated (AES-CBC plus
HMAC), so a tampered ciphertext fails loudly instead of decrypting to rubbish,
and `cryptography` is already installed as a dependency of `python-jose`.

Missing key means the feature is off, never that tokens are stored in the clear.
`is_configured()` exists so callers can say so plainly rather than discovering it
at the moment they try to encrypt.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TokenEncryptionError(Exception):
    """The key is missing or malformed, or the ciphertext did not verify."""


def is_configured(settings: Settings | None = None) -> bool:
    """Whether a usable key is present.

    Validates the key rather than only checking it is non-empty. A malformed key
    fails on first use otherwise, which in practice means at the end of a user's
    Google consent flow — after they have already granted access.
    """
    key = (settings or get_settings()).token_encryption_key
    if not key:
        return False
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        logger.warning("TOKEN_ENCRYPTION_KEY is set but is not a valid Fernet key")
        return False
    return True


def _cipher(settings: Settings | None = None) -> Fernet:
    key = (settings or get_settings()).token_encryption_key
    if not key:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt(plaintext: str, *, settings: Settings | None = None) -> str:
    """Encrypt a secret for storage."""
    return _cipher(settings).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, *, settings: Settings | None = None) -> str:
    """Decrypt a stored secret.

    Raises:
        TokenEncryptionError: The key changed, or the value was tampered with.
            Both are worth failing on: silently treating an unreadable token as
            absent would send the user back through a consent flow without
            anyone noticing the key had rotated.
    """
    try:
        return _cipher(settings).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenEncryptionError("Stored secret could not be decrypted") from exc
