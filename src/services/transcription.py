"""Provider-neutral speech-to-text boundary for stored voice attachments.

This module performs transcription only. It does not persist message state,
publish realtime events, or invoke any translation or language-model service.
"""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from src.config import Settings, get_settings
from src.database.models import Attachment
from src.services.attachment_storage import AttachmentStorage, StoredAttachment
from src.services.audio_conversion import (
    AudioConversionError,
    AudioConversionTimeoutError,
    FFmpegAudioConverter,
    PreparedAudio,
)

logger = logging.getLogger(__name__)

# Gemini's documented direct inputs plus browser-native containers that are
# converted to a temporary supported representation before provider upload.
_SUPPORTED_EXTENSIONS_BY_CONTENT_TYPE = {
    "audio/aac": frozenset({".aac"}),
    "audio/aiff": frozenset({".aif", ".aiff"}),
    "audio/flac": frozenset({".flac"}),
    "audio/mp3": frozenset({".mp3"}),
    "audio/mp4": frozenset({".m4a", ".mp4"}),
    "audio/mpeg": frozenset({".mp3"}),
    "audio/ogg": frozenset({".ogg"}),
    "audio/wav": frozenset({".wav"}),
    "audio/webm": frozenset({".webm"}),
}
_ALLOWED_CODECS_BY_CONTENT_TYPE: dict[str, frozenset[str]] = {
    "audio/mp4": frozenset({"mp4a.40.2", "opus"}),
    "audio/ogg": frozenset({"opus", "vorbis"}),
    "audio/webm": frozenset({"opus"}),
}
_DIRECT_GEMINI_CONTENT_TYPES = frozenset({"audio/aac", "audio/aiff", "audio/flac", "audio/mp3", "audio/wav"})
SUPPORTED_AUDIO_CONTENT_TYPES = frozenset(_SUPPORTED_EXTENSIONS_BY_CONTENT_TYPE)
SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    extension for extensions in _SUPPORTED_EXTENSIONS_BY_CONTENT_TYPE.values() for extension in extensions
)


class TranscriptionError(RuntimeError):
    """Base class for controlled transcription failures."""


class TranscriptionConfigurationError(TranscriptionError):
    """The selected STT provider cannot be constructed safely."""


class InvalidAudioError(TranscriptionError):
    """The attachment is empty, too large, or not a supported audio input."""


class TranscriptionTimeoutError(TranscriptionError):
    """The provider did not finish inside the configured deadline."""


class TranscriptionProviderError(TranscriptionError):
    """The provider rejected the request or returned an unusable response."""


class BlankTranscriptError(TranscriptionError):
    """The provider returned no meaningful original-language transcript."""


def _parse_content_type(content_type: str) -> tuple[str, dict[str, str]]:
    content_type_parts = [part.strip().lower() for part in content_type.split(";")]
    parameters = {
        key.strip(): value.strip().strip('"')
        for part in content_type_parts[1:]
        if "=" in part
        for key, value in (part.split("=", 1),)
    }
    return content_type_parts[0], parameters


def requires_audio_conversion(content_type: str) -> bool:
    """Return whether a valid browser input needs STT-only preprocessing."""
    normalized_content_type, parameters = _parse_content_type(content_type)
    if normalized_content_type in _DIRECT_GEMINI_CONTENT_TYPES:
        return False
    return not (normalized_content_type == "audio/ogg" and parameters.get("codecs") == "vorbis")


def validate_audio_attachment(
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    max_size_bytes: int,
) -> str:
    """Validate persisted audio metadata and return its normalized MIME type.

    The send lifecycle and the provider boundary share this function so an
    attachment accepted as a voice message cannot be rejected later by a
    duplicated, drifting MIME/container policy.
    """
    normalized_content_type, parameters = _parse_content_type(content_type)
    extension = Path(filename).suffix.lower()

    if size_bytes <= 0:
        raise InvalidAudioError("Audio attachment is empty")
    if size_bytes > max_size_bytes:
        raise InvalidAudioError("Audio attachment exceeds the configured size limit")
    supported_extensions = _SUPPORTED_EXTENSIONS_BY_CONTENT_TYPE.get(normalized_content_type)
    if supported_extensions is None:
        raise InvalidAudioError("Audio attachment type is not supported")
    codec = parameters.get("codecs")
    allowed_codecs = _ALLOWED_CODECS_BY_CONTENT_TYPE.get(normalized_content_type)
    if allowed_codecs is not None and codec is not None and codec not in allowed_codecs:
        raise InvalidAudioError("Audio attachment codec is not supported")
    if extension not in supported_extensions:
        raise InvalidAudioError("Audio attachment container is not supported")
    return normalized_content_type


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """The full original-language transcript and safe provider metadata."""

    text: str
    detected_language: str | None
    model: str
    latency_ms: int


class TranscriptionProvider(Protocol):
    """Provider contract consumed by the service layer."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language_hint: str | None = None,
    ) -> TranscriptionResult: ...


class AttachmentReader(Protocol):
    """Minimal storage capability required by isolated transcription."""

    async def read(self, attachment: Attachment) -> StoredAttachment: ...


class AudioConverter(Protocol):
    """Minimal STT-only browser-audio conversion seam."""

    async def convert(self, audio_bytes: bytes) -> PreparedAudio: ...


class GeminiTranscriptionProvider:
    """Gemini Files + Interactions adapter for non-live verbatim STT."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise TranscriptionConfigurationError("STT provider is not configured")
        if not model.strip():
            raise TranscriptionConfigurationError("STT model is not configured")
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise TranscriptionConfigurationError("STT timeout must be between 1 and 300 seconds")
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory

    def _create_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        return genai.Client(
            api_key=self._api_key,
            http_options=genai_types.HttpOptions(timeout=round(self._timeout_seconds * 1000)),
        )

    @staticmethod
    def _is_timeout(exc: Exception) -> bool:
        return isinstance(exc, (TimeoutError, httpx.TimeoutException)) or (
            isinstance(exc, genai_errors.APIError) and exc.code in {408, 504}
        )

    @staticmethod
    async def _close_client(client: Any) -> None:
        try:
            await client.aio.aclose()
        except Exception:  # noqa: BLE001 - close errors carry provider internals
            logger.warning("Gemini STT client cleanup failed")

    @staticmethod
    async def _delete_temporary_file(client: Any, file_name: str) -> None:
        try:
            await client.aio.files.delete(name=file_name)
        except Exception:  # noqa: BLE001 - identifiers/provider payloads stay private
            logger.warning("Gemini temporary STT file cleanup failed")

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe one prepared audio buffer.

        ``language_hint`` is a hint, not a constraint: the provider still
        transcribes whatever language it hears. Measured on a Vietnamese sample,
        an empty list — pure auto-detection — misheard the opening clause
        outright ("Chào Bob, chiều mai" came back as "Chị ơi, khi nào bao giờ"),
        and naming the language fixed it. Naming the *wrong* language costs
        almost nothing: the same English sample transcribed word-for-word under
        a `vi` hint, differing from auto-detection only in writing "3:00" where
        it had written "three".
        """
        started = time.perf_counter()
        client: Any | None = None
        uploaded_file_name: str | None = None
        try:
            client = self._create_client()
            upload = io.BytesIO(audio_bytes)
            upload.name = filename
            uploaded_file = await client.aio.files.upload(
                file=upload,
                config={
                    "mime_type": content_type,
                    "display_name": "voice-message-audio",
                },
            )
            raw_name = getattr(uploaded_file, "name", None)
            raw_uri = getattr(uploaded_file, "uri", None)
            uploaded_file_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
            file_uri = raw_uri.strip() if isinstance(raw_uri, str) and raw_uri.strip() else None
            if uploaded_file_name is None or file_uri is None:
                raise TranscriptionProviderError("STT provider returned an invalid response")
            interaction = await client.aio.interactions.create(
                model=self._model,
                input=[
                    {
                        "type": "audio",
                        "uri": file_uri,
                        "mime_type": content_type,
                    }
                ],
                generation_config={
                    "transcription_config": {
                        "language_codes": [language_hint] if language_hint else [],
                        "mode": {"type": "verbatim"},
                    }
                },
            )
            raw_text = getattr(interaction, "output_text", None)
        except (BlankTranscriptError, TranscriptionProviderError):
            raise
        except Exception as exc:  # noqa: BLE001 - normalize every SDK/provider failure
            if self._is_timeout(exc):
                raise TranscriptionTimeoutError("STT provider timed out") from None
            raise TranscriptionProviderError("STT provider request failed") from None
        finally:
            if client is not None and uploaded_file_name is not None:
                await self._delete_temporary_file(client, uploaded_file_name)
            if client is not None:
                await self._close_client(client)

        if not isinstance(raw_text, str):
            raise TranscriptionProviderError("STT provider returned an invalid response")
        text = raw_text.strip()
        if not text:
            raise BlankTranscriptError("STT provider returned a blank transcript")

        return TranscriptionResult(
            text=text,
            # Interactions output_text currently has no reliable language field,
            # and the hint sent with the request is the sender's setting rather
            # than anything observed in the audio — so there is still nothing
            # here worth reporting as a detected language. Do not infer a code.
            detected_language=None,
            model=self._model,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )


class TranscriptionService:
    """Validate and transcribe an already-authorized stored attachment."""

    def __init__(
        self,
        *,
        provider: TranscriptionProvider,
        storage: AttachmentReader,
        max_audio_size_bytes: int,
        converter: AudioConverter | None = None,
    ) -> None:
        if max_audio_size_bytes <= 0:
            raise TranscriptionConfigurationError("Maximum audio size must be positive")
        self._provider = provider
        self._storage = storage
        self._max_audio_size_bytes = max_audio_size_bytes
        self._converter = converter

    async def transcribe_attachment(
        self, attachment: Attachment, language_hint: str | None = None
    ) -> TranscriptionResult:
        """Read and fully transcribe a stored audio attachment without side effects.

        ``language_hint`` is the sender's `preferred_language`, passed through to
        the provider. People rarely record a voice message in a language other
        than the one they have set, and the hint is not binding, so the rare
        mismatch costs far less than leaving the provider to guess.
        """
        stored = await self._storage.read(attachment)
        normalized_content_type = validate_audio_attachment(
            filename=stored.filename,
            content_type=stored.content_type,
            size_bytes=len(stored.data),
            max_size_bytes=self._max_audio_size_bytes,
        )

        provider_audio = PreparedAudio(
            data=stored.data,
            filename=stored.filename,
            content_type=normalized_content_type,
        )
        if requires_audio_conversion(stored.content_type):
            if self._converter is None:
                raise TranscriptionConfigurationError("Audio preprocessing is not configured")
            try:
                provider_audio = await self._converter.convert(stored.data)
            except AudioConversionTimeoutError:
                raise TranscriptionTimeoutError("Audio preprocessing timed out") from None
            except AudioConversionError:
                raise TranscriptionProviderError("Audio preprocessing failed") from None

        result = await self._provider.transcribe(
            provider_audio.data,
            provider_audio.filename,
            provider_audio.content_type,
            language_hint,
        )
        text = result.text.strip()
        if not text:
            raise BlankTranscriptError("STT provider returned a blank transcript")
        return TranscriptionResult(
            text=text,
            detected_language=result.detected_language,
            model=result.model,
            latency_ms=result.latency_ms,
        )


def get_transcription_service(
    settings: Settings | None = None,
    *,
    storage: AttachmentReader | None = None,
    client_factory: Callable[[], Any] | None = None,
) -> TranscriptionService:
    """Build the configured STT service independently of ``LLM_PROVIDER``."""
    resolved = settings or get_settings()
    if resolved.stt_provider != "gemini":
        raise TranscriptionConfigurationError("Unsupported STT provider")

    provider = GeminiTranscriptionProvider(
        api_key=resolved.google_api_key,
        model=resolved.stt_model,
        timeout_seconds=resolved.stt_timeout_seconds,
        client_factory=client_factory,
    )
    return TranscriptionService(
        provider=provider,
        storage=storage or AttachmentStorage(resolved),
        max_audio_size_bytes=resolved.max_upload_size_bytes,
        converter=FFmpegAudioConverter(
            timeout_seconds=resolved.stt_timeout_seconds,
            max_input_bytes=resolved.max_upload_size_bytes,
            max_output_bytes=resolved.max_upload_size_bytes,
        ),
    )
