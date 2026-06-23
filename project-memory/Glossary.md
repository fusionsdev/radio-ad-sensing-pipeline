# Glossary

| Term | Meaning |
|---|---|
| **RadioSense** | Operator name for the radio ad-sensing pipeline + dashboard |
| **Chunk** | 60–120s WAV segment from ffmpeg ingest; row in `chunks` table |
| **Detection** | One LLM extraction result linked to a chunk; may attach to canonical ad |
| **Canonical ad** | Deduped ad entity with airing count and archived audio |
| **true_loan** | Ops classifier label — high-confidence consumer personal loan signal |
| **loan_possible** | Classifier label — loan phrase present but exclusion conflict |
| **excluded_noise** | Classifier label — loan-like phrase overridden by exclusion (auto, tax, etc.) |
| **Harvest** | Controlled overnight batch ingest session (`scripts/harvest_control.py`) |
| **Watchdog** | `watchdog/` service — stale detection, pool promotion, recovery commands |
| **Hermes** | Local AI gateway for Telegram ops; loads `.hermes.md` in this repo |
| **Project memory** | This Obsidian vault under `project-memory/` |
| **Harness** | `tools/harness/` — post-change verification, no prod DB writes |
| **WAL** | SQLite Write-Ahead Logging — concurrent ingestor/worker/alerter writes |
| **Chromaprint vector** | BLOB audio fingerprint features — not a hash |
| **zvec** | Phase 2 candidate semantic index (Alibaba) — hooks only in Phase 1 |

## Related notes

- [[00_Project_Overview]]
- [[Decisions/Memory OS Phase 1]]