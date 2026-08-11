import pytest


@pytest.mark.asyncio
async def test_health(client):
    """Verify that the health check endpoint returns 200 and ok status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    """Verify that submitting an empty chat message returns a 422 validation error."""
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_agent_status(client):
    """Verify that the legacy agent status endpoint returns 200."""
    response = await client.get("/api/v1/status")
    assert response.status_code == 200

