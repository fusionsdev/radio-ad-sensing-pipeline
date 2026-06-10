"""Operator CLI to compare ASR model RTF on a sample WAV file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from shared.config import load_settings
from shared.models import PipelineSettings
from worker.transcribe import Transcriber, TranscriptionResult


def run_benchmark(
    audio_path: Path,
    models: list[str],
    compute_type: str,
    *,
    settings: PipelineSettings | None = None,
    model_factory: Callable[[str, str], Any] | None = None,
) -> list[dict[str, float | str | int]]:
    """Transcribe *audio_path* with each model and return timing rows."""
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")

    base_settings = settings or load_settings()
    rows: list[dict[str, float | str | int]] = []
    for model_name in models:
        model_settings = base_settings.model_copy(
            update={"asr_model": model_name, "asr_compute_type": compute_type}
        )
        transcriber = Transcriber(model_settings, model_factory=model_factory)
        result: TranscriptionResult = transcriber.transcribe(audio_path)
        rows.append(
            {
                "model": model_name,
                "compute_type": compute_type,
                "audio_duration_sec": result.audio_duration_sec,
                "wall_time_sec": result.wall_time_sec,
                "rtf": result.rtf,
                "text_length": len(result.text),
            }
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark faster-whisper ASR models.")
    parser.add_argument("--audio", type=Path, required=True, help="Path to a WAV file.")
    parser.add_argument(
        "--models",
        default="medium.en",
        help="Comma-separated model names (default: medium.en).",
    )
    parser.add_argument(
        "--compute-type",
        default="int8_float16",
        help="faster-whisper compute type (default: int8_float16).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print JSON instead of a human-readable table.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    models = [part.strip() for part in args.models.split(",") if part.strip()]
    if not models:
        print("At least one model name is required.", file=sys.stderr)
        return 2

    rows = run_benchmark(
        args.audio,
        models,
        args.compute_type,
    )
    if args.as_json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(
                f"{row['model']}: rtf={row['rtf']:.4f} "
                f"wall={row['wall_time_sec']:.2f}s "
                f"audio={row['audio_duration_sec']:.2f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
