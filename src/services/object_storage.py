"""Attachment storage abstraction for local development and S3-compatible production."""

import asyncio
import io
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from src.config import get_settings


class AttachmentStorage:
    """Store attachment bytes without exposing the backing provider to routes."""

    @staticmethod
    def key(conversation_id: str, attachment_id: str) -> str:
        return f"attachments/{conversation_id}/{attachment_id}"

    @staticmethod
    def _client():
        settings = get_settings()
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required when OBJECT_STORAGE_PROVIDER=s3")
        import boto3

        return boto3.client(
            "s3", endpoint_url=settings.s3_endpoint_url or None, region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    async def save(self, conversation_id: str, attachment_id: str, file: UploadFile) -> int:
        """Persist a checked-size upload and return its byte count."""
        settings = get_settings()
        written = 0
        buffer = io.BytesIO()
        try:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.max_upload_size_bytes:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Attachment exceeds the 20 MB limit")
                buffer.write(chunk)
            if settings.object_storage_provider == "s3":
                await asyncio.to_thread(self._client().put_object, Bucket=settings.s3_bucket, Key=self.key(conversation_id, attachment_id), Body=buffer.getvalue())
            else:
                root = Path(settings.upload_dir).resolve()
                destination = (root / conversation_id / attachment_id).resolve()
                if root not in destination.parents:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(buffer.getvalue())
            return written
        finally:
            await file.close()

    async def read(self, conversation_id: str, attachment_id: str) -> bytes:
        """Read an authorized attachment after the route has checked membership."""
        settings = get_settings()
        if settings.object_storage_provider == "s3":
            try:
                response = await asyncio.to_thread(self._client().get_object, Bucket=settings.s3_bucket, Key=self.key(conversation_id, attachment_id))
                return await asyncio.to_thread(response["Body"].read)
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found") from exc
        root = Path(settings.upload_dir).resolve()
        path = (root / conversation_id / attachment_id).resolve()
        if root not in path.parents or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
        return await asyncio.to_thread(path.read_bytes)
