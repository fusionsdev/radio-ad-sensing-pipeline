"""Batch-transcribe exported audio chunks with NVIDIA Parakeet/Riva for audit.

This script is intentionally separate from the live RadioSense pipeline. It
reads exported audio files, sends temporary 16 kHz mono PCM audio to NVIDIA
NVCF Riva, and appends JSONL audit records for offline comparison.

Example:
    python scripts/audit/parakeet_batch_transcribe.py --input exports/parakeet_audit_audio --output exports/parakeet_transcripts.jsonl --workers 2 --recursive
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ENGINE = "nvidia_parakeet_tdt_0.6b_v2"
DEFAULT_URI = "grpc.nvcf.nvidia.com:443"
DEFAULT_FUNCTION_ID = "d3fe9151-442b-4204-a70d-5fcc597fd610"
SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".ogg",
    ".opus",
    ".flac",
    ".aac",
}
AUDIT_KEYWORDS = (
    "personal loan",
    "cash advance",
    "bills happen",
    "installment",
    "borrow",
    "credit",
    "payment",
    "loans",
    "loan",
    "debt",
    "bills",
)


@dataclass(frozen=True)
class ConvertedAudio:
    raw_bytes: bytes
    duration_sec: float


def validate_api_key(env: dict[str, str] | None = None) -> str:
    env = env or os.environ
    api_key = env.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY is required. Set it in your environment; do not put API keys in source files."
        )
    return api_key


def masked_key(api_key: str) -> str:
    return f"...{api_key[-4:]}" if len(api_key) >= 4 else "...****"


def find_audio_files(input_dir: Path, recursive: bool) -> list[Path]:
    iterator = input_dir.rglob("*") if recursive else input_dir.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    )


def load_completed_ok(output_path: Path) -> set[str]:
    completed: set[str] = set()
    if not output_path.exists():
        return completed

    with output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("status") == "ok" and record.get("audio_file"):
                completed.add(str(record["audio_file"]))
    return completed


def infer_station_slug(audio_path: Path, input_dir: Path) -> str | None:
    candidates = [audio_path.stem]
    try:
        candidates.extend(part for part in audio_path.relative_to(input_dir).parts[:-1])
    except ValueError:
        candidates.extend(audio_path.parts[:-1])

    chunk_pattern = re.compile(r"(?P<station>[a-z0-9]+(?:-[a-z0-9]+)+)[_-]chunk[_-]?[a-z0-9-]+", re.IGNORECASE)
    slug_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$", re.IGNORECASE)

    for candidate in candidates:
        match = chunk_pattern.search(candidate)
        if match:
            return match.group("station").lower()
        if slug_pattern.match(candidate):
            return candidate.lower()
    return None


def infer_chunk_id(audio_path: Path) -> str | None:
    stem = audio_path.stem
    patterns = (
        r"(?:^|[_-])chunk[_-]?(?P<chunk>[a-z0-9-]+)",
        r"(?:^|[_-])chunkid[_-]?(?P<chunk>[a-z0-9-]+)",
        r"(?:^|[_-])id[_-]?(?P<chunk>\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if match:
            return match.group("chunk")
    return None


def keyword_hits(transcript: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", transcript.lower())
    hits: list[str] = []
    for keyword in AUDIT_KEYWORDS:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        if re.search(pattern, normalized):
            hits.append(keyword)
    return hits


def build_record(
    audio_path: Path,
    input_dir: Path,
    duration_sec: float,
    transcript: str,
    status: str,
    error: str | None,
    include_keywords: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "audio_file": str(audio_path),
        "audio_basename": audio_path.name,
        "station_slug": infer_station_slug(audio_path, input_dir),
        "chunk_id": infer_chunk_id(audio_path),
        "duration_sec": round(duration_sec, 3),
        "transcript": transcript,
        "transcript_len": len(transcript),
        "engine": ENGINE,
        "status": status,
        "error": error,
    }
    if include_keywords:
        record["keyword_hits"] = keyword_hits(transcript)
    return record


def convert_audio_to_pcm(audio_path: Path) -> ConvertedAudio:
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError(
            "pydub is required for audio conversion. Install it with ffmpeg available on PATH."
        ) from exc

    audio = AudioSegment.from_file(audio_path)
    duration_sec = len(audio) / 1000.0
    pcm = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    return ConvertedAudio(raw_bytes=pcm.raw_data, duration_sec=duration_sec)


def transcribe_pcm_with_riva(
    raw_bytes: bytes,
    api_key: str,
    uri: str = DEFAULT_URI,
    function_id: str = DEFAULT_FUNCTION_ID,
) -> str:
    try:
        import riva.client
    except ImportError as exc:
        raise RuntimeError(
            "riva.client is required for NVIDIA Parakeet transcription. Install NVIDIA Riva client packages in the audit environment."
        ) from exc

    auth = riva.client.Auth(
        use_ssl=True,
        uri=uri,
        metadata_args=[
            ["function-id", function_id],
            ["authorization", f"Bearer {api_key}"],
        ],
    )
    client = riva.client.ASRService(auth)
    config = riva.client.RecognitionConfig(
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hertz=16000,
        language_code="en-US",
        max_alternatives=1,
        enable_automatic_punctuation=True,
    )

    response = client.offline_recognize(raw_bytes, config)
    parts: list[str] = []
    for result in getattr(response, "results", []) or []:
        alternatives = getattr(result, "alternatives", []) or []
        if alternatives:
            parts.append(getattr(alternatives[0], "transcript", "").replace("<unk>", ""))
    return " ".join(part.strip() for part in parts if part.strip()).strip()


def transcribe_file(
    audio_path: Path,
    input_dir: Path,
    api_key: str,
    include_keywords: bool,
    uri: str,
    function_id: str,
    max_attempts: int = 3,
) -> dict[str, Any]:
    duration_sec = 0.0
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            converted = convert_audio_to_pcm(audio_path)
            duration_sec = converted.duration_sec
            transcript = transcribe_pcm_with_riva(
                converted.raw_bytes,
                api_key=api_key,
                uri=uri,
                function_id=function_id,
            )
            status = "ok" if transcript else "empty"
            return build_record(
                audio_path,
                input_dir,
                duration_sec,
                transcript,
                status,
                None,
                include_keywords,
            )
        except Exception as exc:  # noqa: BLE001 - each file should fail independently.
            last_error = str(exc)
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 8))

    return build_record(
        audio_path,
        input_dir,
        duration_sec,
        "",
        "error",
        last_error or "unknown transcription error",
        include_keywords,
    )


def append_jsonl(output_path: Path, records: Iterable[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-transcribe exported RadioSense audio chunks with NVIDIA Parakeet/Riva for offline audit.",
        epilog=(
            "Example:\n"
            "  python scripts/audit/parakeet_batch_transcribe.py --input exports/parakeet_audit_audio "
            "--output exports/parakeet_transcripts.jsonl --workers 2 --recursive"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True, type=Path, help="Directory containing exported audio chunks")
    parser.add_argument("--output", required=True, type=Path, help="JSONL transcript output path")
    parser.add_argument("--recursive", action="store_true", help="Scan input directory recursively")
    parser.add_argument("--workers", type=int, default=2, help="Parallel transcription workers (default: 2)")
    parser.add_argument("--force", action="store_true", help="Reprocess files even if an ok record already exists")
    parser.add_argument("--keywords", action="store_true", help="Include broad audit keyword_hits in each JSONL record")
    parser.add_argument("--uri", default=DEFAULT_URI, help=argparse.SUPPRESS)
    parser.add_argument("--function-id", default=DEFAULT_FUNCTION_ID, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        api_key = validate_api_key()
    except RuntimeError as exc:
        parser.exit(2, f"error: {exc}\n")

    input_dir = args.input
    if not input_dir.is_dir():
        parser.exit(2, f"error: input directory does not exist: {input_dir}\n")
    if args.workers < 1:
        parser.exit(2, "error: --workers must be >= 1\n")

    audio_files = find_audio_files(input_dir, args.recursive)
    completed = set() if args.force else load_completed_ok(args.output)
    pending = [path for path in audio_files if str(path) not in completed]

    print(
        f"Using NVIDIA_API_KEY {masked_key(api_key)}; found {len(audio_files)} audio files, "
        f"skipping {len(audio_files) - len(pending)}, processing {len(pending)}."
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_path = {
            executor.submit(
                transcribe_file,
                path,
                input_dir,
                api_key,
                args.keywords,
                args.uri,
                args.function_id,
            ): path
            for path in pending
        }
        for future in concurrent.futures.as_completed(future_to_path):
            record = future.result()
            append_jsonl(args.output, [record])
            print(f"{record['status']}: {record['audio_basename']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
