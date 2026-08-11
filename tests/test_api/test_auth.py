"""Tests for authentication API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    """Test successful login with valid credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Token should be a non-empty JWT string
    assert len(data["access_token"]) > 20


@pytest.mark.asyncio
async def test_login_invalid_email(client, test_user):
    """Test login with non-existent email."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "testpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_invalid_password(client, test_user):
    """Test login with wrong password."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_missing_fields(client):
    """Test login with missing fields."""
    # Missing password
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com"},
    )
    assert response.status_code == 422  # Validation error

    # Missing email
    response = await client.post(
        "/api/v1/auth/login",
        json={"password": "testpassword"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_current_user_success(client, test_user, test_user_headers):
    """Test getting current user with valid token."""
    response = await client.get("/api/v1/auth/me", headers=test_user_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "member"
    assert data["preferred_language"] == "en"
    assert "id" in data
    assert "created_at" in data
    # Ensure password hash is not exposed
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_current_user_no_token(client):
    """Test getting current user without token."""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(client):
    """Test getting current user with invalid token."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token_here"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_get_current_user_malformed_auth_header(client):
    """Test getting current user with malformed Authorization header."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "NotBearer token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_language_success(client, test_user, test_user_headers):
    """Test updating preferred language."""
    response = await client.put(
        "/api/v1/auth/me/language",
        headers=test_user_headers,
        json={"preferred_language": "vi"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preferred_language"] == "vi"
    assert data["email"] == "test@example.com"  # Other fields unchanged


@pytest.mark.asyncio
async def test_update_language_persistence(client, test_user, test_user_headers):
    """Test that language preference persists after update."""
    # Update language
    await client.put(
        "/api/v1/auth/me/language",
        headers=test_user_headers,
        json={"preferred_language": "ja"},
    )

    # Get user again
    response = await client.get("/api/v1/auth/me", headers=test_user_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["preferred_language"] == "ja"


@pytest.mark.asyncio
async def test_update_language_invalid_code(client, test_user, test_user_headers):
    """Test updating with unsupported language code."""
    response = await client.put(
        "/api/v1/auth/me/language",
        headers=test_user_headers,
        json={"preferred_language": "invalid_code"},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_language_case_insensitive(client, test_user, test_user_headers):
    """Test that language code is normalized to lowercase."""
    response = await client.put(
        "/api/v1/auth/me/language",
        headers=test_user_headers,
        json={"preferred_language": "EN"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preferred_language"] == "en"


@pytest.mark.asyncio
async def test_update_language_no_auth(client):
    """Test updating language without authentication."""
    response = await client.put(
        "/api/v1/auth/me/language",
        json={"preferred_language": "vi"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_not_in_response(client, test_user, test_user_headers):
    """Test that password_hash is never exposed in any response."""
    # Check get user response
    response = await client.get("/api/v1/auth/me", headers=test_user_headers)
    data = response.json()

    # Ensure sensitive fields are not in response
    assert "password" not in data
    assert "password_hash" not in data

    # Check all fields are strings or expected types
    for key, value in data.items():
        assert not key.lower().startswith("password"), f"Found password field: {key}"


@pytest.mark.asyncio
async def test_user_id_from_token_not_request(client, test_user, test_admin, test_admin_headers):
    """Test that user identity comes from JWT token, not request body."""
    # Use admin's token to get user info
    response = await client.get("/api/v1/auth/me", headers=test_admin_headers)

    assert response.status_code == 200
    data = response.json()
    # Should return admin's info, not test_user's
    assert data["email"] == "admin@example.com"
    assert data["role"] == "admin"
