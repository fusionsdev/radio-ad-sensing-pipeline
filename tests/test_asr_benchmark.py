"""Tests for the ASR benchmark CLI (no GPU / faster-whisper load)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from shared.models import PipelineSettings
from worker.asr_benchmark import main, run_benchmark


class _FakeWhisperModel:
    def __init__(self, model_name: str, compute_type: str) -> None:
        self.model_name = model_name
        self.compute_type = compute_type

    def transcribe(self, audio_path: str) -> tuple[Any, Any]:
        class _Info:
            duration = 90.0

        class _Segment:
            start = 0.0
            end = 1.0
            text = f"heard on {Path(audio_path).name}"

        return iter([_Segment()]), _Info()


def _fake_factory(model_name: str, compute_type: str) -> _FakeWhisperModel:
    return _FakeWhisperModel(model_name, compute_type)


def test_run_benchmark_returns_rtf_rows(tmp_path: Path) -> None:
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"RIFF")

    settings = PipelineSettings(asr_model="medium.en", asr_compute_type="int8_float16")
    rows = run_benchmark(
        wav,
        ["medium.en", "distil-large-v3"],
        "int8_float16",
        settings=settings,
        model_factory=_fake_factory,
    )

    assert len(rows) == 2
    assert rows[0]["model"] == "medium.en"
    assert rows[1]["model"] == "distil-large-v3"
    assert rows[0]["audio_duration_sec"] == pytest.approx(90.0)
    assert rows[0]["rtf"] >= 0.0
    assert rows[0]["text_length"] > 0


def test_main_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"RIFF")

    import worker.asr_benchmark as benchmark_module

    original = benchmark_module.run_benchmark

    def patched(audio_path, models, compute_type, **kwargs):
        return [
            {
                "model": models[0],
                "compute_type": compute_type,
                "audio_duration_sec": 10.0,
                "wall_time_sec": 0.5,
                "rtf": 0.05,
                "text_length": 12,
            }
        ]

    benchmark_module.run_benchmark = patched  # type: ignore[assignment]
    try:
        exit_code = main(
            ["--audio", str(wav), "--models", "medium.en", "--json"]
        )
    finally:
        benchmark_module.run_benchmark = original

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert '"model": "medium.en"' in captured
    assert '"rtf": 0.05' in captured
