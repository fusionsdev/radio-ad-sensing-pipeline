# Parakeet Audit Workflow

Use this workflow to validate exported RadioSense audio chunks with NVIDIA
Parakeet/Riva without changing the live pipeline.

## Select Audio

Export 100-150 representative chunks from the stations under review, for
example KLIF and WBAP. Prefer a mix across dayparts and include chunks that
current Whisper transcripts or keyword exports marked as possible loan-ad
candidates. Put copies under:

```powershell
exports/parakeet_audit_audio
```

Do not point the audit script at live chunk storage, and do not delete source
audio after export.

## Run

Set the NVIDIA key in the shell environment. Do not commit it.

```powershell
$env:NVIDIA_API_KEY = "..."
python scripts/audit/parakeet_batch_transcribe.py --input exports/parakeet_audit_audio --output exports/parakeet_transcripts.jsonl --workers 2 --recursive --keywords
```

The script appends JSONL records and skips audio files that already have
`status: "ok"` unless `--force` is passed.

## Interpret Results

- Parakeet finds loan terms but Whisper did not: likely ASR recall issue.
- Parakeet also finds no loan terms: likely station inventory issue for the
  sampled period.
- Parakeet transcript has loan terms but the classifier rejects it: likely
  classifier rule or taxonomy issue, requiring tests and before/after deltas.

This audit does not promote, disable, or rotate stations automatically.
