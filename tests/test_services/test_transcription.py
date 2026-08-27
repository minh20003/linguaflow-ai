"""Unit tests for isolated, original-language Gemini transcription."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from src.config import Settings
from src.database.models import Attachment
from src.services.attachment_storage import StoredAttachment
from src.services.audio_conversion import (
    AudioConversionTimeoutError,
    PreparedAudio,
)
from src.services.transcription import (
    BlankTranscriptError,
    GeminiTranscriptionProvider,
    InvalidAudioError,
    TranscriptionProviderError,
    TranscriptionResult,
    TranscriptionService,
    TranscriptionTimeoutError,
    get_transcription_service,
    requires_audio_conversion,
    validate_audio_attachment,
)

VALID_SECRET = "x" * 48
FULL_TRANSCRIPT = "Ừm, tôi... tôi sẽ giữ nguyên mọi chi tiết, nhé.\nMã là VF 8-A17 và tổng tiền là 1.250.000 đồng."


def _attachment(**overrides) -> Attachment:
    values = {
        "id": "attachment-1",
        "conversation_id": "conversation-1",
        "uploader_id": "user-1",
        "filename": "recording.ogg",
        "content_type": "audio/ogg; codecs=vorbis",
        "size": 11,
    }
    values.update(overrides)
    return Attachment(**values)


@dataclass
class _FakeStorage:
    stored: StoredAttachment

    async def read(self, attachment: Attachment) -> StoredAttachment:
        return self.stored


class _FakeProvider:
    def __init__(self, result: TranscriptionResult) -> None:
        self.result = result
        self.calls: list[tuple[bytes, str, str]] = []

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> TranscriptionResult:
        self.calls.append((audio_bytes, filename, content_type))
        return self.result


class _FakeConverter:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[bytes] = []

    async def convert(self, audio_bytes: bytes) -> PreparedAudio:
        self.calls.append(audio_bytes)
        if self.error is not None:
            raise self.error
        return PreparedAudio(
            data=b"temporary-flac",
            filename="voice-transcription.flac",
            content_type="audio/flac",
        )


class _FakeFiles:
    def __init__(
        self,
        *,
        upload_error: Exception | None = None,
        delete_error: Exception | None = None,
        uploaded_name: str | None = "files/provider-private-id",
        uploaded_uri: str | None = "https://provider.invalid/private-file-uri",
    ) -> None:
        self.upload_error = upload_error
        self.delete_error = delete_error
        self.uploaded_name = uploaded_name
        self.uploaded_uri = uploaded_uri
        self.upload_calls: list[dict] = []
        self.delete_calls: list[str] = []

    async def upload(self, *, file, config):
        self.upload_calls.append(
            {
                "bytes": file.read(),
                "filename": file.name,
                "config": dict(config),
            }
        )
        if self.upload_error is not None:
            raise self.upload_error
        return SimpleNamespace(
            name=self.uploaded_name,
            uri=self.uploaded_uri,
            mime_type=config["mime_type"],
        )

    async def delete(self, *, name: str):
        self.delete_calls.append(name)
        if self.delete_error is not None:
            raise self.delete_error


class _FakeInteractions:
    def __init__(
        self,
        *,
        output_text: object = FULL_TRANSCRIPT,
        error: Exception | None = None,
    ) -> None:
        self.output_text = output_text
        self.error = error
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class _FakeAio:
    def __init__(self, files: _FakeFiles, interactions: _FakeInteractions) -> None:
        self.files = files
        self.interactions = interactions
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _FakeClient:
    def __init__(
        self,
        *,
        files: _FakeFiles | None = None,
        interactions: _FakeInteractions | None = None,
    ) -> None:
        self.aio = _FakeAio(
            files or _FakeFiles(),
            interactions or _FakeInteractions(),
        )


def _service(
    *,
    data: bytes = b"audio-bytes",
    filename: str = "recording.ogg",
    content_type: str = "audio/ogg; codecs=vorbis",
    max_size: int = 20 * 1024 * 1024,
    converter=None,
) -> tuple[TranscriptionService, _FakeProvider]:
    provider = _FakeProvider(
        TranscriptionResult(
            text=FULL_TRANSCRIPT,
            detected_language=None,
            model="gemini-3.5-transcribe",
            latency_ms=12,
        )
    )
    storage = _FakeStorage(
        StoredAttachment(
            data=data,
            filename=filename,
            content_type=content_type,
        )
    )
    return (
        TranscriptionService(
            provider=provider,
            storage=storage,
            max_audio_size_bytes=max_size,
            converter=converter,
        ),
        provider,
    )


def _gemini_provider(client: _FakeClient) -> GeminiTranscriptionProvider:
    return GeminiTranscriptionProvider(
        api_key="provider-secret-key",
        model="gemini-3.5-transcribe",
        timeout_seconds=30,
        client_factory=lambda: client,
    )


@pytest.mark.asyncio
async def test_service_transcribes_stored_audio_without_rewriting_text():
    service, provider = _service()
    result = await service.transcribe_attachment(_attachment())
    assert result.text == FULL_TRANSCRIPT
    assert result.detected_language is None
    assert provider.calls == [(b"audio-bytes", "recording.ogg", "audio/ogg")]


@pytest.mark.asyncio
async def test_service_rejects_a_blank_result_from_any_provider():
    provider = _FakeProvider(
        TranscriptionResult(
            text=" \n ",
            detected_language=None,
            model="fake-model",
            latency_ms=1,
        )
    )
    service = TranscriptionService(
        provider=provider,
        storage=_FakeStorage(
            StoredAttachment(
                data=b"audio-bytes",
                filename="recording.ogg",
                content_type="audio/ogg; codecs=vorbis",
            )
        ),
        max_audio_size_bytes=20,
    )
    with pytest.raises(BlankTranscriptError, match="blank transcript"):
        await service.transcribe_attachment(_attachment())


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("recording.aac", "audio/aac"),
        ("recording.aif", "audio/aiff"),
        ("recording.aiff", "audio/aiff"),
        ("recording.flac", "audio/flac"),
        ("recording.mp3", "audio/mp3"),
        ("recording.ogg", "audio/ogg; codecs=vorbis"),
        ("recording.ogg", "audio/ogg; codecs=opus"),
        ("recording.ogg", "audio/ogg"),
        ("recording.wav", "audio/wav"),
        ("recording.webm", "audio/webm; codecs=opus"),
        ("recording.webm", "audio/webm"),
        ("recording.mp4", "audio/mp4; codecs=mp4a.40.2"),
        ("recording.m4a", "audio/mp4"),
    ],
)
def test_gemini_documented_audio_mime_and_container_pairs_are_allowed(
    filename,
    content_type,
):
    assert (
        validate_audio_attachment(
            filename=filename,
            content_type=content_type,
            size_bytes=10,
            max_size_bytes=20,
        )
        == content_type.split(";", 1)[0]
    )


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("recording.m4a", "audio/m4a"),
        ("recording.webm", "audio/webm; codecs=vorbis"),
        ("recording.mp4", "audio/mp4; codecs=vp9"),
        ("recording.ogg", "audio/ogg; codecs=aac"),
        ("recording.wav", "audio/ogg"),
        ("recording.ogg", "audio/wav"),
    ],
)
def test_unsupported_or_mismatched_audio_mime_and_container_is_rejected(
    filename,
    content_type,
):
    with pytest.raises(InvalidAudioError):
        validate_audio_attachment(
            filename=filename,
            content_type=content_type,
            size_bytes=10,
            max_size_bytes=20,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "filename", "content_type", "max_size"),
    [
        (b"", "recording.ogg", "audio/ogg", 20),
        (b"too-large", "recording.ogg", "audio/ogg", 2),
        (b"bytes", "recording.ogg", "application/octet-stream", 20),
        (b"bytes", "recording.aac", "audio/ogg", 20),
    ],
)
async def test_service_rejects_empty_oversized_or_unsupported_audio(
    data,
    filename,
    content_type,
    max_size,
):
    service, provider = _service(
        data=data,
        filename=filename,
        content_type=content_type,
        max_size=max_size,
    )
    with pytest.raises(InvalidAudioError):
        await service.transcribe_attachment(_attachment())
    assert provider.calls == []


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("audio/wav", False),
        ("audio/flac", False),
        ("audio/ogg; codecs=vorbis", False),
        ("audio/webm; codecs=opus", True),
        ("audio/mp4; codecs=mp4a.40.2", True),
        ("audio/ogg; codecs=opus", True),
        ("audio/ogg", True),
    ],
)
def test_only_browser_native_non_gemini_inputs_require_conversion(
    content_type,
    expected,
):
    assert requires_audio_conversion(content_type) is expected


@pytest.mark.asyncio
async def test_service_converts_browser_native_audio_without_changing_storage():
    converter = _FakeConverter()
    service, provider = _service(
        data=b"durable-original-webm",
        filename="recording.webm",
        content_type="audio/webm; codecs=opus",
        converter=converter,
    )

    result = await service.transcribe_attachment(
        _attachment(filename="recording.webm", content_type="audio/webm; codecs=opus")
    )

    assert result.text == FULL_TRANSCRIPT
    assert converter.calls == [b"durable-original-webm"]
    assert provider.calls == [(b"temporary-flac", "voice-transcription.flac", "audio/flac")]


@pytest.mark.asyncio
async def test_conversion_timeout_is_controlled_and_provider_is_not_called():
    converter = _FakeConverter(error=AudioConversionTimeoutError("private ffmpeg timeout details"))
    service, provider = _service(
        filename="recording.webm",
        content_type="audio/webm; codecs=opus",
        converter=converter,
    )

    with pytest.raises(TranscriptionTimeoutError, match="preprocessing timed out") as exc_info:
        await service.transcribe_attachment(_attachment())

    assert "private ffmpeg" not in str(exc_info.value)
    assert provider.calls == []


@pytest.mark.asyncio
async def test_gemini_uploads_file_and_requests_verbatim_auto_detect_transcription():
    client = _FakeClient(interactions=_FakeInteractions(output_text=f"  {FULL_TRANSCRIPT}\n"))
    result = await _gemini_provider(client).transcribe(
        b"audio-bytes",
        "recording.ogg",
        "audio/ogg",
    )
    assert result.text == FULL_TRANSCRIPT
    assert result.detected_language is None
    assert result.model == "gemini-3.5-transcribe"
    assert result.latency_ms >= 0
    assert client.aio.files.upload_calls == [
        {
            "bytes": b"audio-bytes",
            "filename": "recording.ogg",
            "config": {
                "mime_type": "audio/ogg",
                "display_name": "voice-message-audio",
            },
        }
    ]
    assert client.aio.interactions.calls == [
        {
            "model": "gemini-3.5-transcribe",
            "input": [
                {
                    "type": "audio",
                    "uri": "https://provider.invalid/private-file-uri",
                    "mime_type": "audio/ogg",
                }
            ],
            "generation_config": {
                "transcription_config": {
                    "language_codes": [],
                    "mode": {"type": "verbatim"},
                }
            },
        }
    ]
    request = repr(client.aio.interactions.calls[0]).lower()
    assert "smart" not in request
    assert "diarization" not in request
    assert "timestamp" not in request
    assert "live" not in request
    assert client.aio.files.delete_calls == ["files/provider-private-id"]
    assert client.aio.closed is True


@pytest.mark.asyncio
async def test_blank_output_is_rejected_after_temporary_file_cleanup():
    client = _FakeClient(interactions=_FakeInteractions(output_text="  \n "))
    with pytest.raises(BlankTranscriptError, match="blank transcript"):
        await _gemini_provider(client).transcribe(
            b"audio-bytes",
            "recording.ogg",
            "audio/ogg",
        )
    assert client.aio.files.delete_calls == ["files/provider-private-id"]
    assert client.aio.closed is True


@pytest.mark.asyncio
async def test_upload_timeout_is_mapped_and_does_not_attempt_unknown_file_cleanup():
    timeout = httpx.ReadTimeout("raw upload timeout")
    client = _FakeClient(files=_FakeFiles(upload_error=timeout))
    with pytest.raises(TranscriptionTimeoutError, match="timed out") as exc_info:
        await _gemini_provider(client).transcribe(
            b"secret-audio-bytes",
            "recording.ogg",
            "audio/ogg",
        )
    assert "raw upload timeout" not in str(exc_info.value)
    assert client.aio.files.delete_calls == []
    assert client.aio.closed is True


@pytest.mark.asyncio
async def test_interaction_timeout_is_mapped_after_temporary_file_cleanup():
    timeout = httpx.ReadTimeout("raw interaction timeout")
    client = _FakeClient(interactions=_FakeInteractions(error=timeout))
    with pytest.raises(TranscriptionTimeoutError, match="timed out") as exc_info:
        await _gemini_provider(client).transcribe(
            b"secret-audio-bytes",
            "recording.ogg",
            "audio/ogg",
        )
    assert "raw interaction timeout" not in str(exc_info.value)
    assert client.aio.files.delete_calls == ["files/provider-private-id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["upload", "interaction"])
async def test_provider_errors_are_controlled_and_cleanup_when_possible(
    failure_stage,
    caplog,
):
    raw = RuntimeError(
        "provider-secret-key files/provider-private-id "
        "https://provider.invalid/private-file-uri raw body "
        f"{FULL_TRANSCRIPT}"
    )
    files = _FakeFiles(upload_error=raw if failure_stage == "upload" else None)
    interactions = _FakeInteractions(error=raw if failure_stage == "interaction" else None)
    client = _FakeClient(files=files, interactions=interactions)
    with pytest.raises(TranscriptionProviderError, match="request failed") as exc_info:
        await _gemini_provider(client).transcribe(
            b"secret-audio-bytes",
            "recording.ogg",
            "audio/ogg",
        )
    combined = f"{exc_info.value} {caplog.text}"
    assert "provider-secret-key" not in combined
    assert "provider-private-id" not in combined
    assert "private-file-uri" not in combined
    assert "raw body" not in combined
    assert "secret-audio-bytes" not in combined
    assert FULL_TRANSCRIPT not in combined
    assert files.delete_calls == ([] if failure_stage == "upload" else ["files/provider-private-id"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("files", "interactions"),
    [
        (_FakeFiles(uploaded_uri=None), _FakeInteractions()),
        (_FakeFiles(), _FakeInteractions(output_text={"unexpected": "shape"})),
    ],
)
async def test_malformed_gemini_response_is_a_controlled_provider_error(
    files,
    interactions,
):
    client = _FakeClient(files=files, interactions=interactions)
    with pytest.raises(TranscriptionProviderError, match="invalid response"):
        await _gemini_provider(client).transcribe(
            b"audio-bytes",
            "recording.ogg",
            "audio/ogg",
        )
    assert files.delete_calls == ["files/provider-private-id"]


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_destroy_success_or_leak_identifier(caplog):
    files = _FakeFiles(delete_error=RuntimeError("files/provider-private-id raw cleanup body"))
    client = _FakeClient(files=files)
    result = await _gemini_provider(client).transcribe(
        b"audio-bytes",
        "recording.ogg",
        "audio/ogg",
    )
    assert result.text == FULL_TRANSCRIPT
    assert "Gemini temporary STT file cleanup failed" in caplog.text
    assert "provider-private-id" not in caplog.text
    assert "raw cleanup body" not in caplog.text


@pytest.mark.asyncio
async def test_gemini_stt_uses_existing_key_and_is_independent_from_llm_provider(
    monkeypatch,
):
    settings = Settings(
        _env_file=None,
        jwt_secret=VALID_SECRET,
        llm_provider="openai",
        openai_api_key="translation-role-key",
        GOOGLE_API_KEY="gemini-stt-key",
        GROQ_API_KEY="",
    )
    storage = _FakeStorage(
        StoredAttachment(
            data=b"audio-bytes",
            filename="recording.ogg",
            content_type="audio/ogg; codecs=vorbis",
        )
    )
    client = _FakeClient()
    constructed: dict = {}

    def build_client(**kwargs):
        constructed.update(kwargs)
        return client

    monkeypatch.setattr("src.services.transcription.genai.Client", build_client)
    service = get_transcription_service(settings, storage=storage)
    result = await service.transcribe_attachment(_attachment())
    assert result.text == FULL_TRANSCRIPT
    assert result.model == "gemini-3.5-transcribe"
    assert constructed["api_key"] == "gemini-stt-key"
    assert constructed["http_options"].timeout == 60_000
    assert settings.llm_provider == "openai"
    assert settings.openai_api_key == "translation-role-key"
    assert settings.groq_api_key == ""


def test_existing_google_and_gemini_key_alias_precedence_is_preserved():
    gemini_alias = Settings(
        _env_file=None,
        jwt_secret=VALID_SECRET,
        GEMINI_API_KEY="gemini-alias-key",
    )
    google_precedence = Settings(
        _env_file=None,
        jwt_secret=VALID_SECRET,
        GOOGLE_API_KEY="google-key",
        GEMINI_API_KEY="gemini-alias-key",
    )
    assert gemini_alias.google_api_key == "gemini-alias-key"
    assert google_precedence.google_api_key == "google-key"


def test_stt_defaults_and_timeout_bound_are_configuration_contracts():
    assert Settings.model_fields["stt_provider"].default == "gemini"
    assert Settings.model_fields["stt_model"].default == "gemini-3.5-transcribe"
    assert Settings.model_fields["stt_timeout_seconds"].default == 60
    with pytest.raises(ValidationError):
        Settings(jwt_secret=VALID_SECRET, stt_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(jwt_secret=VALID_SECRET, stt_timeout_seconds=301)
