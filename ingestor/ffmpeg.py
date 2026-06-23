"""ffmpeg command construction and execution for live stream chunks."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import wave
from pathlib import Path
from typing import Protocol

from shared.models import PipelineSettings, StationConfig

TIMEOUT_MARGIN_SEC = 60


def _is_hls_url(url: str) -> bool:
    """True for HLS playlists where segment EOF must not trigger reconnect."""
    lowered = url.lower()
    return ".m3u8" in lowered or lowered.endswith("/hls")


def _reconnect_input_flags(url: str) -> list[str]:
    """Reconnect flags for live HTTP streams.

    HLS segments end with EOF by design; ``-reconnect_at_eof`` traps ffmpeg in a
    reconnect loop on iHeart/revma playlists instead of advancing segments.
    """
    flags = [
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
    ]
    if not _is_hls_url(url):
        flags.extend(["-reconnect_at_eof", "1"])
    flags.extend(["-reconnect_delay_max", "30"])
    return flags


class ChunkRunner(Protocol):
    """Backend that records one station chunk to a path."""

    def record_chunk(
        self,
        station: StationConfig,
        output_path: Path,
        *,
        duration_sec: float,
    ) -> int: ...


def build_ffmpeg_command(
    station: StationConfig,
    output_path: Path,
    settings: PipelineSettings,
) -> list[str]:
    """Build an ffmpeg command for one bounded WAV chunk from a live stream.

    The supervisor owns looping/backoff. ffmpeg gets reconnect flags so transient
    HTTP stream stalls inside a chunk are retried before the process exits.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        *_reconnect_input_flags(station.url),
        "-i",
        station.url,
        "-t",
        str(settings.chunk_len),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        "-y",
        str(output_path),
    ]


def get_wav_duration_seconds(path: Path) -> float | None:
    """Return WAV duration in seconds, or None when the file is unreadable."""
    try:
        with wave.open(str(path), "rb") as handle:
            frame_rate = handle.getframerate()
            if frame_rate <= 0:
                return None
            return handle.getnframes() / float(frame_rate)
    except (wave.Error, OSError):
        return None


def is_valid_chunk_duration(
    path: Path,
    expected_sec: float,
    *,
    tolerance_sec: float = 2.0,
) -> bool:
    """True when WAV duration is within tolerance of the configured chunk length."""
    actual = get_wav_duration_seconds(path)
    if actual is None:
        return False
    return abs(actual - expected_sec) <= tolerance_sec


def _popen_with_process_group(command: list[str]) -> subprocess.Popen[bytes]:
    kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["preexec_fn"] = os.setsid
    return subprocess.Popen(command, **kwargs)  # type: ignore[call-overload]


def _kill_process_group(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            proc.kill()
        proc.wait(timeout=5)


def _reap_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        _kill_process_group(proc)
    try:
        proc.communicate(timeout=1)
    except (subprocess.TimeoutExpired, ValueError):
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def _stderr_tail(stderr: bytes | None, *, max_lines: int) -> str:
    if not stderr or max_lines <= 0:
        return ""
    text = stderr.decode("utf-8", errors="replace")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


class FfmpegChunkRunner:
    """Subprocess-backed chunk recorder with timeout and graceful termination."""

    def __init__(self, settings: PipelineSettings | None = None) -> None:
        self.settings = settings or PipelineSettings()
        self._active: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self.last_error_sample = ""

    def terminate_active(self) -> None:
        """Stop an in-flight ffmpeg chunk, if any."""
        with self._lock:
            proc = self._active
        if proc is not None:
            _kill_process_group(proc)

    def record_chunk(
        self,
        station: StationConfig,
        output_path: Path,
        *,
        duration_sec: float,
    ) -> int:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = build_ffmpeg_command(station, output_path, self.settings)
        timeout_sec = float(duration_sec) + TIMEOUT_MARGIN_SEC
        proc: subprocess.Popen[bytes] | None = None
        returncode = 1
        stderr: bytes | None = None
        self.last_error_sample = ""
        try:
            proc = _popen_with_process_group(command)
            with self._lock:
                self._active = proc
            try:
                _stdout, stderr = proc.communicate(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                _kill_process_group(proc)
                try:
                    _stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    _stdout, stderr = proc.communicate(timeout=5)
                returncode = 124
            else:
                returncode = proc.returncode if proc.returncode is not None else 1
        finally:
            self.last_error_sample = _stderr_tail(
                stderr,
                max_lines=int(self.settings.ffmpeg_error_sample_lines),
            )
            with self._lock:
                if self._active is proc:
                    self._active = None
            if proc is not None:
                _reap_process(proc)
        return returncode
