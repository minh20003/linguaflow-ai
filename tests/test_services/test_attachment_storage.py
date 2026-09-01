"""Focused tests for the attachment byte-storage seam."""

from __future__ import annotations

import httpx
import pytest

from src.config import Settings
from src.database.models import Attachment
from src.services.attachment_storage import (
    AttachmentStorage,
    AttachmentStorageError,
    AttachmentStorageNotFoundError,
)

VALID_SECRET = "x" * 48


def _settings(tmp_path, **overrides) -> Settings:
    values = {
        "jwt_secret": VALID_SECRET,
        "upload_dir": str(tmp_path),
        "supabase_url": "",
        "supabase_service_role_key": "",
    }
    values.update(overrides)
    return Settings(**values)


def _attachment(**overrides) -> Attachment:
    values = {
        "id": "attachment-1",
        "conversation_id": "conversation-1",
        "uploader_id": "user-1",
        "filename": "recording.webm",
        "content_type": "audio/webm",
        "size": 11,
    }
    values.update(overrides)
    return Attachment(**values)


@pytest.mark.asyncio
async def test_local_storage_round_trip_preserves_record_metadata(tmp_path):
    storage = AttachmentStorage(_settings(tmp_path))
    attachment = _attachment()

    await storage.write(
        conversation_id=attachment.conversation_id,
        attachment_id=attachment.id,
        data=b"audio-bytes",
        content_type=attachment.content_type,
    )
    stored = await storage.read(attachment)

    assert stored.data == b"audio-bytes"
    assert stored.filename == "recording.webm"
    assert stored.content_type == "audio/webm"


@pytest.mark.asyncio
async def test_local_storage_reports_a_missing_object(tmp_path):
    storage = AttachmentStorage(_settings(tmp_path))

    with pytest.raises(AttachmentStorageNotFoundError, match="not found"):
        await storage.read(_attachment())


@pytest.mark.asyncio
async def test_supabase_storage_round_trip_uses_existing_object_key_and_headers(tmp_path):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert await request.aread() == b"audio-bytes"
            return httpx.Response(200)
        return httpx.Response(200, content=b"stored-audio")

    settings = _settings(
        tmp_path,
        supabase_url="https://storage.example.test",
        supabase_service_role_key="service-key",
        supabase_storage_bucket="attachments",
    )
    storage = AttachmentStorage(settings, transport=httpx.MockTransport(handler))
    attachment = _attachment()

    await storage.write(
        conversation_id=attachment.conversation_id,
        attachment_id=attachment.id,
        data=b"audio-bytes",
        content_type=attachment.content_type,
    )
    stored = await storage.read(attachment)

    assert stored.data == b"stored-audio"
    assert [request.method for request in requests] == ["POST", "GET"]
    assert all(request.url.path == "/storage/v1/object/attachments/conversation-1/attachment-1" for request in requests)
    assert requests[0].headers["content-type"] == "audio/webm"
    assert requests[0].headers["authorization"] == "Bearer service-key"
    assert requests[1].headers["apikey"] == "service-key"


@pytest.mark.asyncio
async def test_supabase_missing_and_provider_failures_are_controlled(tmp_path):
    responses = iter(
        [
            httpx.Response(400, json={"code": "NoSuchKey"}),
            httpx.Response(503, text="raw storage provider detail"),
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    settings = _settings(
        tmp_path,
        supabase_url="https://storage.example.test",
        supabase_service_role_key="service-key",
    )
    storage = AttachmentStorage(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(AttachmentStorageNotFoundError, match="not found"):
        await storage.read(_attachment())
    with pytest.raises(AttachmentStorageError, match="Unable to retrieve") as exc_info:
        await storage.read(_attachment())

    assert "raw storage provider detail" not in str(exc_info.value)
