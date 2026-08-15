"""Tests for registration, user lookup and the language list (PR-4).

Fixtures live in this file rather than tests/conftest.py, which is shared
across all feature areas.
"""

from __future__ import annotations

import itertools

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_password_hash
from src.database.models import User

_next_username = itertools.count()


def register_body(**overrides) -> dict:
    """A valid registration payload, with a unique username unless overridden.

    Every field is supplied even when a test only cares about one of them: a
    request rejected for a missing username would return 422 just like a
    request rejected for a short password, and the test would pass while
    measuring nothing.
    """
    body = {
        "username": f"user{next(_next_username)}",
        "email": "new@example.com",
        "password": "a-good-password",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_registration_returns_a_session_that_authenticates(client):
    """The client lands in the chat straight after registering, so it needs a session."""
    response = await client.post(
        "/api/v1/auth/register",
        json=register_body(email="new@example.com", preferred_language="vi"),
    )

    assert response.status_code == 201
    body = response.json()
    # A refresh token is what makes the session survive the access token
    # expiring, and revocable at logout.
    assert body["refresh_token"]
    assert body["user"]["email"] == "new@example.com"

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "new@example.com"
    assert profile.json()["preferred_language"] == "vi"
    assert profile.json()["role"] == "member"


@pytest.mark.asyncio
async def test_registration_defaults_to_vietnamese(client):
    """The product is Vietnamese-first; an omitted preference means Vietnamese."""
    response = await client.post(
        "/api/v1/auth/register", json=register_body(email="default@example.com")
    )
    token = response.json()["access_token"]

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile.json()["preferred_language"] == "vi"


@pytest.mark.asyncio
async def test_registration_never_grants_a_role_from_the_request(client):
    """A client must not be able to make itself an admin."""
    response = await client.post(
        "/api/v1/auth/register",
        json=register_body(email="sneaky@example.com", role="admin"),
    )
    token = response.json()["access_token"]

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile.json()["role"] == "member"


@pytest.mark.asyncio
async def test_duplicate_email_is_rejected(client, test_user):
    response = await client.post(
        "/api/v1/auth/register", json=register_body(email=test_user.email)
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_email_case_resolves_to_one_account(client):
    """Registering as Mixed@Case must not create an account login cannot reach."""
    created = await client.post(
        "/api/v1/auth/register", json=register_body(email="Mixed@Example.com")
    )
    assert created.status_code == 201

    # A different username, so a 409 can only be about the email.
    duplicate = await client.post(
        "/api/v1/auth/register",
        json=register_body(email="mixed@example.com", password="another-password"),
    )
    assert duplicate.status_code == 409

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "MIXED@EXAMPLE.COM", "password": "a-good-password"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_unsupported_language_is_rejected(client):
    """`preferred_language` is an allowlist, not a free-text field.

    The value reaches the translation prompt, so anything outside the list is
    refused at the edge rather than interpolated and hoped for (ADR-12). `tl`
    is a real ISO 639-1 code the product does not offer, which is a sharper
    test than a made-up one.
    """
    response = await client.post(
        "/api/v1/auth/register",
        json=register_body(email="x@example.com", preferred_language="tl"),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_short_password_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/register", json=register_body(email="x@example.com", password="short")
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_malformed_username_is_rejected(client):
    """Usernames are restricted to letters, numbers, hyphens and underscores."""
    response = await client.post(
        "/api/v1/auth/register",
        json=register_body(username="not a username!", email="y@example.com"),
    )

    assert response.status_code == 422


@pytest_asyncio.fixture
async def named_user(test_db: AsyncSession) -> User:
    """An account with both name fields filled, unlike the shared fixtures."""
    user = User(
        email="an.nguyen@example.com",
        username="annguyen",
        display_name="Nguyễn An",
        password_hash=get_password_hash("a-good-password"),
        role="member",
        preferred_language="vi",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_user_search_finds_an_account_by_email_prefix(
    client, test_user_two, test_user_headers
):
    response = await client.get(
        "/api/v1/users", params={"q": "second@"}, headers=test_user_headers
    )

    assert response.status_code == 200
    assert [u["id"] for u in response.json()] == [test_user_two.id]


@pytest.mark.asyncio
async def test_user_search_finds_an_account_by_username_prefix(
    client, named_user, test_user_headers
):
    response = await client.get("/api/v1/users", params={"q": "anng"}, headers=test_user_headers)

    assert response.status_code == 200
    assert [u["id"] for u in response.json()] == [named_user.id]


@pytest.mark.asyncio
async def test_user_search_matches_any_word_of_a_display_name(
    client, named_user, test_user_headers
):
    """Searching a person by the part of their name you know is the normal case."""
    response = await client.get("/api/v1/users", params={"q": "an"}, headers=test_user_headers)

    assert response.status_code == 200
    assert named_user.id in [u["id"] for u in response.json()]


@pytest.mark.asyncio
async def test_user_search_ignores_case(client, named_user, test_user_headers):
    response = await client.get(
        "/api/v1/users", params={"q": "NGUYỄN"}, headers=test_user_headers
    )

    assert [u["id"] for u in response.json()] == [named_user.id]


@pytest.mark.asyncio
async def test_user_search_never_returns_the_caller(client, test_user, test_user_headers):
    """Offering a conversation with yourself is the one result never wanted."""
    response = await client.get(
        "/api/v1/users", params={"q": test_user.email}, headers=test_user_headers
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_user_search_treats_a_wildcard_as_literal_text(
    client, named_user, test_user_two, test_user_headers
):
    """`%` is a LIKE wildcard; unescaped it would list the whole user table."""
    response = await client.get("/api/v1/users", params={"q": "%%"}, headers=test_user_headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_user_search_returns_an_empty_list_when_nobody_matches(client, test_user_headers):
    """Empty rather than 404, which would read as a broken route."""
    response = await client.get(
        "/api/v1/users", params={"q": "nobody@example.com"}, headers=test_user_headers
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_user_search_rejects_a_query_too_short_to_narrow_anything(
    client, test_user_headers
):
    response = await client.get("/api/v1/users", params={"q": "a"}, headers=test_user_headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_search_requires_authentication(client, test_user):
    response = await client.get("/api/v1/users", params={"q": test_user.email})

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_language_list_is_served_from_the_allowlist(client):
    """Serving it is what lets the frontend stop keeping its own copy."""
    from src.schemas.auth import SUPPORTED_LANGUAGES

    response = await client.get("/api/v1/languages")

    assert response.status_code == 200
    assert response.json() == sorted(SUPPORTED_LANGUAGES)
