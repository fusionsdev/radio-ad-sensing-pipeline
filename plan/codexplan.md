# **Production Hardening Plan — SQLite WAL, Storage, ASR Benchmark**

## **Summary**

- Baseline confirmed: pytest -q passes 90/90 and docker compose config --quiet passes.
- Treat the 6 recommendations as hardening, not rework. Already satisfied: short-lived dashboard/metrics reads, chunks tmpfs + janitor cleanup, fingerprint threshold 0.88, and Ollama temperature=0.
- Implement the real remaining gaps: WAL checkpoint maintenance/metrics, production named-volume storage, and benchmark-first ASR upgrade path.

## **Key Changes**

- Add WAL maintenance in H:\DEV\projects\radio-ad-sensing-pipeline\shared\[db.py](http://db.py): WalCheckpointResult plus checkpoint_wal(db_path, mode="PASSIVE"), returning busy, log_frames, and checkpointed_frames.
- Keep read-only DB connections truly read-oriented: writable connections set WAL; read-only connections keep busy_timeout/row factory and avoid journal-mode writes.
- Call passive checkpoint from H:\DEV\projects\radio-ad-sensing-pipeline\worker\[janitor.py](http://janitor.py) during existing janitor sweeps; log and continue if busy/failing.
- Add Prometheus gauges in H:\DEV\projects\radio-ad-sensing-pipeline\shared\[metrics.py](http://metrics.py): pipeline_sqlite_wal_log_frames, pipeline_sqlite_wal_checkpointed_frames, pipeline_sqlite_wal_busy.
- Add [docker-compose.prod](http://docker-compose.prod).yml that switches /app/data from ./data bind mount to named volume pipeline_data for app services and migrate; keep chunk-tmpfs unchanged.
- Keep medium.en as default, add ASR_MODEL / ASR_COMPUTE_TYPE env overrides, and add python -m worker.asr_benchmark --audio <wav> --models medium.en,distil-large-v3 --compute-type int8_float16 --json.

## **Test Plan**

- Unit tests for WAL checkpoint result, read-only connection behavior, janitor checkpoint continuation, metric updates, and ASR env overrides.
- Benchmark module test uses fake model factory so CI never loads GPU/faster-whisper.
- Run pytest -q.
- Run docker compose config --quiet.
- Run docker compose -f docker-compose.yml -f [docker-compose.prod](http://docker-compose.prod).yml config --quiet.
- Operator-only GPU smoke: verify /app/data named volume, /app/chunks tmpfs, then benchmark real 5–10 minute samples before changing ASR default.

## **Assumptions**

- User-selected defaults: production override for named volume, benchmark-first for distil-large-v3.
- No DB schema migration is needed.
- Do not change fingerprint threshold, Ollama temperature, or default ASR model in this hardening pass.
- Closing report goes to H:\DEV\projects\radio-ad-sensing-pipeline\plan\[wp13-hardening-report.md](http://wp13-hardening-report.md).

