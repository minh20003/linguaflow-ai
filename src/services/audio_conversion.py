"""Bounded STT-only conversion of browser-native audio.

The durable attachment remains untouched. FFmpeg receives bytes through stdin
and returns a temporary Gemini-supported FLAC representation through stdout;
no user-controlled path or converter diagnostics cross the service boundary.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from imageio_ffmpeg import get_ffmpeg_exe

_READ_CHUNK_BYTES = 64 * 1024
_FFMPEG_CONCURRENCY = asyncio.Semaphore(2)


class AudioConversionError(RuntimeError):
    """Browser audio could not be converted safely for transcription."""


class AudioConversionTimeoutError(AudioConversionError):
    """Audio conversion exceeded its configured deadline."""


@dataclass(frozen=True, slots=True)
class PreparedAudio:
    """Temporary provider input; never the application's canonical audio."""

    data: bytes
    filename: str
    content_type: str


ConversionRunner = Callable[[bytes], Awaitable[bytes]]


class FFmpegAudioConverter:
    """Convert one bounded in-memory input to mono 16 kHz FLAC."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_input_bytes: int,
        max_output_bytes: int,
        executable: str | None = None,
        runner: ConversionRunner | None = None,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise ValueError("Audio conversion timeout must be between 1 and 300 seconds")
        if max_input_bytes <= 0 or max_output_bytes <= 0:
            raise ValueError("Audio conversion byte limits must be positive")
        resolved_executable = executable if executable is not None else get_ffmpeg_exe()
        if not resolved_executable.strip():
            raise ValueError("Audio converter executable is not configured")
        self._timeout_seconds = timeout_seconds
        self._max_input_bytes = max_input_bytes
        self._max_output_bytes = max_output_bytes
        self._executable = resolved_executable.strip()
        self._runner = runner

    def command(self) -> tuple[str, ...]:
        """Return the fixed, shell-free conversion command for audit/tests."""
        return (
            self._executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-map_metadata",
            "-1",
            "-vn",
            "-sn",
            "-dn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "flac",
            "-compression_level",
            "5",
            "-f",
            "flac",
            "pipe:1",
        )

    async def convert(self, audio_bytes: bytes) -> PreparedAudio:
        if not audio_bytes:
            raise AudioConversionError("Audio preprocessing failed")
        if len(audio_bytes) > self._max_input_bytes:
            raise AudioConversionError("Audio preprocessing failed")
        try:
            output = (
                await self._runner(audio_bytes) if self._runner is not None else await self._run_ffmpeg(audio_bytes)
            )
        except AudioConversionError:
            raise
        except TimeoutError:
            raise AudioConversionTimeoutError("Audio preprocessing timed out") from None
        except Exception:  # noqa: BLE001 - converter details and paths stay private
            raise AudioConversionError("Audio preprocessing failed") from None
        if not output or len(output) > self._max_output_bytes:
            raise AudioConversionError("Audio preprocessing failed")
        return PreparedAudio(
            data=output,
            filename="voice-transcription.flac",
            content_type="audio/flac",
        )

    async def _run_ffmpeg(self, audio_bytes: bytes) -> bytes:
        process: asyncio.subprocess.Process | None = None
        feed_task: asyncio.Task[None] | None = None
        async with _FFMPEG_CONCURRENCY:
            try:
                process = await asyncio.create_subprocess_exec(
                    *self.command(),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                if process.stdin is None or process.stdout is None:
                    raise AudioConversionError("Audio preprocessing failed")
                feed_task = asyncio.create_task(self._write_input(process.stdin, audio_bytes))
                async with asyncio.timeout(self._timeout_seconds):
                    output = await self._read_limited(process.stdout)
                    await feed_task
                    return_code = await process.wait()
                if return_code != 0:
                    raise AudioConversionError("Audio preprocessing failed")
                return output
            except TimeoutError:
                await self._stop_process(process)
                raise AudioConversionTimeoutError("Audio preprocessing timed out") from None
            except AudioConversionError:
                await self._stop_process(process)
                raise
            except Exception:  # noqa: BLE001 - FFmpeg details stay private
                await self._stop_process(process)
                raise AudioConversionError("Audio preprocessing failed") from None
            finally:
                if feed_task is not None and not feed_task.done():
                    feed_task.cancel()

    async def _read_limited(self, stream: asyncio.StreamReader) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = self._max_output_bytes - total
            chunk = await stream.read(min(_READ_CHUNK_BYTES, remaining + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > self._max_output_bytes:
                raise AudioConversionError("Audio preprocessing failed")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _write_input(
        stream: asyncio.StreamWriter,
        audio_bytes: bytes,
    ) -> None:
        stream.write(audio_bytes)
        await stream.drain()
        stream.close()
        await stream.wait_closed()

    @staticmethod
    async def _stop_process(process: asyncio.subprocess.Process | None) -> None:
        if process is None or process.returncode is not None:
            return
        process.kill()
        await process.wait()
