# Batch 1 — Handoff Prompts (4 sessions ขนาน)

อ้างอิง: `plan/work-dispatch-6165b3.md`, `plan/opus-review-plan-6165b3.md`

คัดลอก prompt ด้านล่างไปวางใน session ใหม่ทีละอัน — ไม่แตะไฟล์ที่ session อื่นกำลังแก้

---

## Session 1 — GPT mini → WP-2 Ingestor fix-then-ship

```
You are fixing WP-2 (Ingestor) per Opus review fix-then-ship. Read first:
- PLAN.md Phase 2
- plan/work-dispatch-6165b3.md (สาย A, F1–F7)
- ingestor/ffmpeg.py, ingestor/supervisor.py, ingestor/__main__.py
- tests/test_ingestor.py

Do NOT start WP-3/4/5/6/7/9. Scope = ingestor hardening only.

## Fixes (all required)

F1 — subprocess timeout
- FfmpegChunkRunner.record_chunk uses subprocess.run with NO timeout.
- EOF-reconnect can hang forever; supervisor never reaches backoff/gap.
- Use Popen (or run with timeout = chunk_len + margin, e.g. chunk_len + 60s).
- On timeout: kill process group, return non-zero.

F2 — graceful shutdown
- SIGTERM/SIGINT must interrupt an in-flight ffmpeg chunk.
- Track active Popen in runner or supervisor; terminate on shutdown.
- ingestor/__main__.py must propagate stop to all station threads + kill children.

F3 — partial chunk rejection
- Before enqueue: validate WAV duration ≈ settings.chunk_len (±2s).
- Use stdlib wave module or ffprobe — no new heavy deps if wave suffices.
- Undersized/partial file → log_gap (reason empty_chunk or stream_down), do NOT enqueue.

F4 — zombie reap
- subprocess cleanup in finally on every path (success, timeout, kill, error).

F5 — stride test with real audio
- Add test proving 83s stride (90−7) using fixture WAV, not only FakeClock.sleep assertion.
- FakeRunner can still be used for DB paths; duration validation test needs real bytes.

F6 — live smoke (document in report)
- If a test stream URL available in stations.yaml, run ingestor ~5 min.
- Record chunk count + gap count in report. If no live stream, note "skipped" + why.

F7 — deliverable
- Write plan/wp2-report.md (deliverables, test results, deviations, smoke notes).

## Constraints
- shared/ stays import-light (no ffmpeg import in shared/)
- Use shared/db.py retry_on_busy, short transactions
- TDD: red→green for new behavior

## Verify before done
.venv\Scripts\pytest tests/test_ingestor.py -v
.venv\Scripts\pytest -q
```

---

## Session 2 — Composer 2.5 → WP-3 G1–G4 + WP-9 F8

```
You are fixing two fix-then-ship items for the same repo. Read first:
- plan/work-dispatch-6165b3.md (สาย B + สาย D)
- plan/wp3-report.md (STALE — do not trust claims)
- worker/consumer.py (create_consumer factory ~L365)
- tests/test_worker_consumer.py
- tests/test_dashboard.py (test_dashboard_never_opens_writable_connection)
- dashboard/queries.py

Do NOT touch ingestor/, docker-compose.yml, or worker/extract.py algorithm logic.

## Part A — WP-3 (G1–G4)

G1 — Revise plan/wp3-report.md
- create_consumer() now wires OllamaExtractor + DetectionPersister + FingerprintAnnotator by default.
- Report must reflect full pipeline, not "ASR only".

G2 — Scope decision (document in report + brief note in .windsurf/plans/handoff-wp3-asr-worker-6165b3.md OR plan/wp3-report.md deviation section)
- Option (a): Accept WP-3→5 merge in consumer — update handoff/report accordingly.
- Option (b): Split create_consumer default to ASR-only; full pipeline behind explicit factory flag.
- Pick ONE, justify in one paragraph. Do not leave ambiguous.

G3 — Test: known_ad fingerprint path
- When fingerprint_annotator returns a match: chunk still transcribed, status done, LLM extraction SKIPPED.
- Add test in test_worker_consumer.py with Fake annotator.

G4 — Test: extraction failure semantics
- Read PLAN.md + _process_claimed: on extraction/dedup exception chunk is marked dropped.
- Add test asserting intended behavior. If wrong vs PLAN, fix code OR document deviation — not silent.

## Part B — WP-9 (F8)

F8 — Strengthen read-only test (no false positive)
- Current test monkeypatches shared.db.get_connection only.
- dashboard/queries.py does `from shared.db import get_connection` — patch dashboard.queries.get_connection too, OR add app-level connection audit.
- Test must FAIL if any route opens a writable connection.

## Verify before done
.venv\Scripts\pytest tests/test_worker_consumer.py tests/test_dashboard.py -v
.venv\Scripts\pytest -q
```

---

## Session 3 — MiniMax M3 → WP-7a F5–F6

```
You are fixing WP-7a Docker skeleton per Opus fix-then-ship. Read first:
- plan/work-dispatch-6165b3.md (สาย C)
- plan/wp7a-report.md
- docker-compose.yml (dashboard + alerter services)
- shared/config.py, shared/models.py, config/settings.yaml
- alerter/Dockerfile, dashboard/__main__.py

Declarative/config only — no business logic in worker/ingestor.

## F5 — Dashboard bind env actually works

Problem: compose sets DASHBOARD_HOST env but load_settings() reads settings.yaml only.
- Wire DASHBOARD_HOST and DASHBOARD_PORT from environment into PipelineSettings at runtime.
- Pattern: extend load_settings() or use pydantic-settings env overlay on PipelineSettings.
- Default remains 127.0.0.1 (LAN-only per PLAN).
- Add/adjust test in tests/test_config.py if needed.

## F6 — Alerter container boots without WP-6 full implementation

Problem: alerter/Dockerfile CMD is `python -m alerter` but no alerter/__main__.py exists.
Problem: compose healthcheck asserts telegram_bot_token — conflicts WP-6 dry-run (no token).

Fix:
- Add minimal alerter/__main__.py: logs "alerter stub — WP-6 pending", sleeps/polls or exits 0 loop.
- Healthcheck: verify `python -c "import alerter; from shared.config import load_telegram_settings"` — do NOT require token.
- Update wp7a-report.md deviations section if healthcheck contract changed.

## Constraints
- Do not bake secrets into images
- docker compose config must pass

## Verify before done
docker compose config --quiet
.venv\Scripts\pytest tests/test_config.py -q
```

---

## Session 4 — Opus / High thinking → WP-4 Deep Review (read-only)

```
Act as the review gate for WP-4 (LLM Extraction). Read in order:
1. PLAN.md — Phase 4, LLM schema, risks (false positives)
2. plan/opus-review-plan-6165b3.md — WP-4 row (Deep)
3. plan/radio-ad-sensing-pipeline-6165b3.md — agreed decisions

No handoff file. No wp4-report.md. Code is the only claim.

## Review level: Deep

Trace worker/extract.py end-to-end. Read tests/test_extract.py — confirm tests exercise real validation logic.

## Focus areas (must trace)
- Prompt guards against false positives (loan talk show ≠ ad)
- JSON schema matches AdExtraction in shared/models.py
- No station/timestamp in LLM prompt or schema
- retry-on-invalid-JSON (once)
- phone normalization edge cases ("eight hundred" → 800)
- shared/ stays import-light (Ollama client only in worker/)

## Verify (run yourself)
.venv\Scripts\pytest tests/test_extract.py -v
.venv\Scripts\pytest -q

## Output
1. Findings by severity with file:line evidence
2. Spec checklist: each Phase 4 criterion pass/fail/untested
3. Test gap analysis
4. Verdict: ship / fix-then-ship (numbered list for GPT high) / rework
5. Do NOT edit code — review only. Suggest updating plan/opus-review-plan-6165b3.md checklist line for WP-4.
```

---

## หลัง Batch 1 เสร็จ

| Session | ถัดไป |
|---|---|
| 1 (WP-2) | Opus Deep re-review WP-2 |
| 2 (WP-3+9) | Opus re-review WP-3 + WP-9 |
| 3 (WP-7a) | Opus Spot-check re-review WP-7a |
| 4 (WP-4) | ถ้า ship → GPT high เขียน wp4-report; ถ้า fix → ส่งกลับ GPT high |

Batch 3 (WP-6, 7b, 10b, 11) เริ่มหลัง WP-4/5 Opus pass — ดู `plan/work-dispatch-6165b3.md` § Batch 3
