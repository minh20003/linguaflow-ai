"""Tests for registration, user lookup and the language list (PR-4).

Fixtures live in this file rather than tests/conftest.py, which is shared
across all feature areas.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_registration_returns_a_token_that_authenticates(client):
    """The client lands in the chat straight after registering, so it needs a session."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "a-good-password", "preferred_language": "vi"},
    )

    assert response.status_code == 201
    token = response.json()["access_token"]

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "new@example.com"
    assert profile.json()["preferred_language"] == "vi"
    assert profile.json()["role"] == "member"


@pytest.mark.asyncio
async def test_registration_defaults_to_english(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "default@example.com", "password": "a-good-password"},
    )
    token = response.json()["access_token"]

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile.json()["preferred_language"] == "en"


@pytest.mark.asyncio
async def test_registration_never_grants_a_role_from_the_request(client):
    """A client must not be able to make itself an admin."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky@example.com",
            "password": "a-good-password",
            "role": "admin",
        },
    )
    token = response.json()["access_token"]

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile.json()["role"] == "member"


@pytest.mark.asyncio
async def test_duplicate_email_is_rejected(client, test_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": test_user.email, "password": "a-good-password"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_email_case_resolves_to_one_account(client):
    """Registering as Mixed@Case must not create an account login cannot reach."""
    created = await client.post(
        "/api/v1/auth/register",
        json={"email": "Mixed@Example.com", "password": "a-good-password"},
    )
    assert created.status_code == 201

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"email": "mixed@example.com", "password": "another-password"},
    )
    assert duplicate.status_code == 409

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "MIXED@EXAMPLE.COM", "password": "a-good-password"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_unsupported_language_is_rejected(client):
    """`id` is offered by the frontend today and is not in the allowlist."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "a-good-password", "preferred_language": "id"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_short_password_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_lookup_finds_an_account_by_email(client, test_user, test_user_headers):
    response = await client.get(
        "/api/v1/users", params={"email": test_user.email}, headers=test_user_headers
    )

    assert response.status_code == 200
    assert [u["id"] for u in response.json()] == [test_user.id]


@pytest.mark.asyncio
async def test_user_lookup_returns_an_empty_list_when_unknown(client, test_user_headers):
    """Empty rather than 404, which would read as a broken route."""
    response = await client.get(
        "/api/v1/users", params={"email": "nobody@example.com"}, headers=test_user_headers
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_user_lookup_requires_authentication(client, test_user):
    response = await client.get("/api/v1/users", params={"email": test_user.email})

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_language_list_is_served_from_the_allowlist(client):
    """Serving it is what lets the frontend stop keeping its own copy."""
    from src.schemas.auth import SUPPORTED_LANGUAGES

    response = await client.get("/api/v1/languages")

    assert response.status_code == 200
    assert response.json() == sorted(SUPPORTED_LANGUAGES)
