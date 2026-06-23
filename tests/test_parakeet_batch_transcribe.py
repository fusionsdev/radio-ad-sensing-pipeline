from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit import parakeet_batch_transcribe as parakeet


def test_api_key_missing_exits_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    input_dir = tmp_path / "audio"
    input_dir.mkdir()

    with pytest.raises(SystemExit) as exc:
        parakeet.main(["--input", str(input_dir), "--output", str(tmp_path / "out.jsonl")])

    assert exc.value.code == 2


def test_existing_jsonl_skip_logic_reads_ok_records(tmp_path: Path) -> None:
    output = tmp_path / "transcripts.jsonl"
    done = tmp_path / "done.wav"
    failed = tmp_path / "failed.wav"
    output.write_text(
        "\n".join(
            [
                json.dumps({"audio_file": str(done), "status": "ok"}),
                json.dumps({"audio_file": str(failed), "status": "error"}),
                "{not json",
            ]
        ),
        encoding="utf-8",
    )

    assert parakeet.load_completed_ok(output) == {str(done)}


def test_keyword_hit_extraction() -> None:
    text = "Bills happen. Borrow with a personal loan, not a payday pitch."

    assert parakeet.keyword_hits(text) == [
        "personal loan",
        "bills happen",
        "borrow",
        "loan",
        "bills",
    ]


def test_output_record_shape_is_valid(tmp_path: Path) -> None:
    input_dir = tmp_path / "exports"
    audio_dir = input_dir / "wbap-am-820"
    audio_dir.mkdir(parents=True)
    audio = audio_dir / "wbap-am-820_chunk_123.wav"
    audio.write_bytes(b"RIFF")

    record = parakeet.build_record(
        audio,
        input_dir,
        duration_sec=30.1234,
        transcript="Apply for a personal loan today.",
        status="ok",
        error=None,
        include_keywords=True,
    )

    assert record == {
        "audio_file": str(audio),
        "audio_basename": "wbap-am-820_chunk_123.wav",
        "station_slug": "wbap-am-820",
        "chunk_id": "123",
        "duration_sec": 30.123,
        "transcript": "Apply for a personal loan today.",
        "transcript_len": 32,
        "engine": "nvidia_parakeet_tdt_0.6b_v2",
        "status": "ok",
        "error": None,
        "keyword_hits": ["personal loan", "loan"],
    }
