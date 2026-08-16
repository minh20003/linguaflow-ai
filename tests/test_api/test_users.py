"""Tests for the authenticated user directory search.

The endpoint deliberately answers two disjoint questions — "who do I already talk
to" and "is this exact address a user" — so these tests are mostly about what it
must *not* return.
"""

import pytest

from src.core.security import get_password_hash
from src.database.models import User


async def _create_user(
    test_db,
    *,
    email: str,
    username: str,
    display_name: str,
) -> User:
    """Create a named user; the shared fixtures carry neither name field."""
    user = User(
        email=email,
        username=username,
        display_name=display_name,
        password_hash=get_password_hash("searchpassword"),
        role="member",
        preferred_language="en",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_search_requires_authentication(client):
    """The directory is not public."""
    response = await client.get("/api/v1/users/search?q=anyone")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_empty_query_lists_contacts_without_the_caller(
    client,
    conversation_factory,
    test_db,
    test_user,
    test_user_headers,
):
    """A blank query is the contact list, which never contains yourself."""
    contact = await _create_user(
        test_db,
        email="contact@example.com",
        username="contact",
        display_name="Contact Person",
    )
    await conversation_factory(test_user, [contact])

    response = await client.get("/api/v1/users/search", headers=test_user_headers)

    assert response.status_code == 200
    data = response.json()
    assert [entry["id"] for entry in data] == [contact.id]
    assert data[0]["display_name"] == "Contact Person"
    assert "email" not in data[0]


@pytest.mark.asyncio
async def test_contact_search_matches_names_and_ignores_strangers(
    client,
    conversation_factory,
    test_db,
    test_user,
    test_user_headers,
):
    """Substring matching only ever reaches inside the caller's own contacts."""
    contact = await _create_user(
        test_db,
        email="lan@example.com",
        username="lannguyen",
        display_name="Lan Nguyen",
    )
    stranger = await _create_user(
        test_db,
        email="lan.stranger@example.com",
        username="lanstranger",
        display_name="Lan Stranger",
    )
    await conversation_factory(test_user, [contact])

    by_display_name = await client.get(
        "/api/v1/users/search?q=nguyen",
        headers=test_user_headers,
    )
    by_username = await client.get(
        "/api/v1/users/search?q=LANNGU",
        headers=test_user_headers,
    )
    shared_prefix = await client.get("/api/v1/users/search?q=lan", headers=test_user_headers)

    assert [entry["id"] for entry in by_display_name.json()] == [contact.id]
    # Matching is case-insensitive on both name columns.
    assert [entry["id"] for entry in by_username.json()] == [contact.id]
    returned = {entry["id"] for entry in shared_prefix.json()}
    assert returned == {contact.id}
    assert stranger.id not in returned


@pytest.mark.asyncio
async def test_a_stranger_is_reachable_only_by_their_full_email(
    client,
    test_db,
    test_user,
    test_user_headers,
):
    """Exact email is the one way to start a first conversation.

    A partial address returns nothing, so the endpoint cannot be walked to
    harvest the user list.
    """
    stranger = await _create_user(
        test_db,
        email="new.person@example.com",
        username="newperson",
        display_name="New Person",
    )

    exact = await client.get(
        "/api/v1/users/search?q=New.Person@Example.com",
        headers=test_user_headers,
    )
    partial = await client.get(
        "/api/v1/users/search?q=new.person@exam",
        headers=test_user_headers,
    )
    domain_only = await client.get(
        "/api/v1/users/search?q=@example.com",
        headers=test_user_headers,
    )
    own_email = await client.get(
        f"/api/v1/users/search?q={test_user.email}",
        headers=test_user_headers,
    )

    assert [entry["id"] for entry in exact.json()] == [stranger.id]
    assert partial.json() == []
    assert domain_only.json() == []
    assert own_email.json() == []


@pytest.mark.asyncio
async def test_search_limit_is_bounded(client, test_user_headers):
    """The limit is validated by FastAPI before the service sees it."""
    too_large = await client.get("/api/v1/users/search?limit=51", headers=test_user_headers)
    too_small = await client.get("/api/v1/users/search?limit=0", headers=test_user_headers)

    assert too_large.status_code == 422
    assert too_small.status_code == 422


