"""Thin faster-whisper wrapper — GPU deps live here, not in shared/."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from shared.models import PipelineSettings


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    segments: list[TranscriptSegment]
    audio_duration_sec: float
    wall_time_sec: float

    @property
    def rtf(self) -> float:
        if self.audio_duration_sec <= 0:
            return 0.0
        return self.wall_time_sec / self.audio_duration_sec


class WhisperBackend(Protocol):
    def transcribe(self, audio_path: Path) -> TranscriptionResult: ...


def _default_model_factory(model_name: str, compute_type: str) -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, compute_type=compute_type)


class Transcriber:
    """Lazy-loaded WhisperModel wrapper returning text, segments, and timing."""

    def __init__(
        self,
        settings: PipelineSettings,
        *,
        model_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._model_name = settings.asr_model
        self._compute_type = settings.asr_compute_type
        self._model_factory = model_factory or _default_model_factory
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self._model_factory(self._model_name, self._compute_type)
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        *,
        audio_duration_sec: float | None = None,
    ) -> TranscriptionResult:
        model = self._get_model()
        started = time.perf_counter()
        segments_iter, info = model.transcribe(str(audio_path))
        segments: list[TranscriptSegment] = []
        parts: list[str] = []
        for segment in segments_iter:
            text = segment.text.strip()
            if text:
                parts.append(text)
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text,
                )
            )
        wall_time_sec = time.perf_counter() - started
        duration = audio_duration_sec
        if duration is None:
            duration = float(getattr(info, "duration", 0.0) or 0.0)
        return TranscriptionResult(
            text=" ".join(parts).strip(),
            segments=segments,
            audio_duration_sec=duration,
            wall_time_sec=wall_time_sec,
        )
