"""Shared byte storage for conversation attachments.

Authorization deliberately does not live here. Callers must first establish
that the attachment record is visible to the current operation, then pass that
known record to :meth:`AttachmentStorage.read`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import Settings, get_settings
from src.database.models import Attachment

_STORAGE_TIMEOUT_SECONDS = 60


class AttachmentStorageError(RuntimeError):
    """The configured attachment store could not complete an operation."""


class AttachmentStorageNotFoundError(AttachmentStorageError):
    """The authorized attachment record has no corresponding stored object."""


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    """Attachment bytes paired with the metadata already stored in the database."""

    data: bytes
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class AttachmentDownload:
    """A route-ready local path or remote payload with persisted metadata."""

    filename: str
    content_type: str
    local_path: Path | None = None
    data: bytes | None = None


class AttachmentStorage:
    """Read and write attachment bytes using the configured storage backend."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    @property
    def uses_supabase(self) -> bool:
        """Whether both credentials required by the existing remote path exist."""
        return bool(self._settings.supabase_url and self._settings.supabase_service_role_key)

    def _local_path(self, conversation_id: str, attachment_id: str) -> Path:
        root = Path(self._settings.upload_dir).resolve()
        candidate = (root / conversation_id / attachment_id).resolve()
        if root not in candidate.parents:
            raise AttachmentStorageNotFoundError("Attachment was not found")
        return candidate

    @staticmethod
    def _object_path(conversation_id: str, attachment_id: str) -> str:
        return f"{conversation_id}/{attachment_id}"

    def _object_url(self, object_path: str) -> str:
        return (
            f"{self._settings.supabase_url.rstrip('/')}/storage/v1/object/"
            f"{self._settings.supabase_storage_bucket}/{object_path}"
        )

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
            "apikey": self._settings.supabase_service_role_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    @staticmethod
    def _object_is_missing(response: httpx.Response) -> bool:
        """Supabase may encode NoSuchKey as HTTP 400 with an inner status."""
        if response.status_code == 404:
            return True
        if response.status_code != 400:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        if not isinstance(payload, dict):
            return False
        return payload.get("code") == "NoSuchKey" or payload.get("error") == "not_found"

    async def write(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        data: bytes,
        content_type: str,
    ) -> None:
        """Store bytes under the existing conversation/attachment key."""
        if self.uses_supabase:
            try:
                async with httpx.AsyncClient(
                    timeout=_STORAGE_TIMEOUT_SECONDS,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        self._object_url(self._object_path(conversation_id, attachment_id)),
                        content=data,
                        headers=self._headers(content_type),
                    )
                response.raise_for_status()
            except httpx.HTTPError:
                raise AttachmentStorageError("Unable to store attachment") from None
            return

        destination = self._local_path(conversation_id, attachment_id)
        try:
            await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(destination.write_bytes, data)
        except OSError:
            raise AttachmentStorageError("Unable to store attachment") from None

    async def download(self, attachment: Attachment) -> AttachmentDownload:
        """Resolve route-ready content without moving authorization into storage."""
        if self.uses_supabase:
            try:
                async with httpx.AsyncClient(
                    timeout=_STORAGE_TIMEOUT_SECONDS,
                    transport=self._transport,
                ) as client:
                    response = await client.get(
                        self._object_url(
                            self._object_path(
                                attachment.conversation_id,
                                attachment.id,
                            )
                        ),
                        headers=self._headers(),
                    )
                if self._object_is_missing(response):
                    raise AttachmentStorageNotFoundError("Attachment was not found")
                response.raise_for_status()
            except AttachmentStorageNotFoundError:
                raise
            except httpx.HTTPError:
                raise AttachmentStorageError("Unable to retrieve attachment") from None

            return AttachmentDownload(
                data=response.content,
                filename=attachment.filename,
                content_type=attachment.content_type,
            )

        path = self._local_path(attachment.conversation_id, attachment.id)
        if not await asyncio.to_thread(path.is_file):
            raise AttachmentStorageNotFoundError("Attachment was not found")
        return AttachmentDownload(
            local_path=path,
            filename=attachment.filename,
            content_type=attachment.content_type,
        )

    async def read(self, attachment: Attachment) -> StoredAttachment:
        """Read bytes for an attachment record already authorized by the caller."""
        download = await self.download(attachment)
        if download.local_path is not None:
            try:
                data = await asyncio.to_thread(download.local_path.read_bytes)
            except FileNotFoundError:
                raise AttachmentStorageNotFoundError("Attachment was not found") from None
            except OSError:
                raise AttachmentStorageError("Unable to retrieve attachment") from None
        else:
            data = download.data if download.data is not None else b""

        return StoredAttachment(
            data=data,
            filename=download.filename,
            content_type=download.content_type,
        )
