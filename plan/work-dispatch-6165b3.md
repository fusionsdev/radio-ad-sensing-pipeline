# Work Dispatch — หลังอ่าน Reports + Opus Review Gate (2026-06-10)

อัปเดตจาก `plan/opus-review-plan-6165b3.md`, reports ทั้งหมดใน `plan/wp*-report.md`, และ trace โค้ดจริง (**`pytest` 83/83 — gate closed**).

**หลักการแจกงาน:** fix-then-ship ส่งกลับผู้ทำเดิม → Opus review งานที่ยังไม่ตรวจ → implement งานใหม่ตาม dependency

---

## สถานะปัจจุบัน

| WP | Report | Opus verdict |
|---|---|---|
| WP-1 | `phase1-report.md` | ✅ ship |
| WP-2 | `wp2-report.md` | ✅ ship |
| WP-3 | `wp3-report.md` | ✅ ship |
| WP-4 | `wp4-report.md` | ✅ ship |
| WP-5 | `wp5-report.md` | ✅ ship |
| WP-6 | `wp6-report.md` | ✅ ship |
| WP-7a | `wp7a-report.md` | ✅ ship |
| WP-7b | `wp7b-report.md` | ✅ ship |
| WP-8 | `wp8-report.md` | ✅ ship |
| WP-9 | `wp9-report.md` | ✅ ship |
| WP-10a | `wp10a-report.md` | ✅ ship |
| WP-10b | `wp10b-report.md` | ✅ ship |
| WP-11 | `wp11a-report.md`, `wp11b-report.md` | ✅ ship |

---

## Batch 1 — แก้ fix-then-ship (ขนาน 4 สาย, ทำก่อน review รอบ 2)

### สาย A — WP-2 Ingestor fixes → **GPT mini**

**Owner:** GPT mini (ผู้ทำเดิม)  
**Blocked by:** ไม่มี  
**Verify:** `pytest tests/test_ingestor.py -v` + ส่ง `plan/wp2-report.md`

| ID | แก้อะไร | หลักฐาน |
|---|---|---|
| **F1** | `subprocess.run` ใน `ingestor/ffmpeg.py` ไม่มี timeout → ffmpeg hang บน EOF-reconnect, backoff/gap ไม่ถึง | `FfmpegChunkRunner.record_chunk` L83 |
| **F2** | SIGTERM ไม่หยุด ffmpeg กลาง chunk — ใช้ `Popen` + process group, supervisor shutdown ฆ่า child | `ingestor/supervisor.py`, `ingestor/__main__.py` |
| **F3** | ไม่ validate duration ไฟล์ partial — ตรวจ WAV ≈ `chunk_len` ก่อน enqueue | `StationIngestor.run_once` L106 |
| **F4** | ไม่ reap zombie — cleanup subprocess ใน `finally` ทุก path | `ingestor/ffmpeg.py` |
| **F5** | Test stride 83s ด้วย fixture WAV จริง (ffprobe/wave) ไม่ใช่แค่ assert sleep | `tests/test_ingestor.py` |
| **F6** | Live smoke 5 นาที + บันทึกใน report (chunks/gaps rows) | manual |
| **F7** | เขียน `plan/wp2-report.md` | deliverable |

---

### สาย B — WP-3 Report + scope alignment → **Composer 2.5**

**Owner:** Composer 2.5 (ผู้ทำเดิม)  
**Blocked by:** ไม่มี (doc + tests เท่านั้น ไม่แตะ algorithm)

| ID | แก้อะไร | หลักฐาน |
|---|---|---|
| **G1** | อัปเดต `plan/wp3-report.md` — `create_consumer()` wire extract+dedup+fingerprint แล้ว | `worker/consumer.py` L365–388 |
| **G2** | ตัดสินใจ scope: (a) ยอมรับ WP-3→5 merge ใน consumer แล้วอัปเดต handoff หรือ (b) แยก default เป็น ASR-only factory | handoff vs code |
| **G3** | Test: `known_ad` fingerprint hit → skip LLM แต่ยัง transcribe + `done` | `_process_claimed` L200–243 |
| **G4** | Test: extraction failure → chunk `dropped` เป็นที่ตั้งใจหรือควร `done`+log? ตรง PLAN | L237–243 |

**Verify:** `pytest tests/test_worker_consumer.py -v`

---

### สาย C — WP-7a Docker fixes → **MiniMax M3**

**Owner:** MiniMax M3 (ผู้ทำเดิม)  
**Blocked by:** ไม่มี

| ID | แก้อะไร | หลักฐาน |
|---|---|---|
| **F5** | `DASHBOARD_HOST` ใน compose ไม่มีผล — `load_settings()` อ่าน yaml อย่างเดียว; wire env → `PipelineSettings` หรือ mount override | `docker-compose.yml` L150, `shared/config.py` |
| **F6** | `alerter/Dockerfile` CMD `python -m alerter` แต่ไม่มี `__main__.py`; healthcheck บังคับ token (ขัด WP-6 dry-run) → placeholder entrypoint + healthcheck ที่ pass เมื่อ import ได้ | `alerter/`, compose L117–122 |

**Verify:** `docker compose config --quiet`

---

### สาย D — WP-9 Dashboard test fix → **Composer 2.5**

**Owner:** Composer 2.5 (ผู้ทำเดิม)  
**Blocked by:** ไม่มี

| ID | แก้อะไร | หลักฐาน |
|---|---|---|
| **F8** | `test_dashboard_never_opens_writable_connection` false-positive — patch `dashboard.queries.get_connection` (import ตรง) ไม่ใช่แค่ `shared.db`; หรือ audit wrapper ใน `create_app` | `tests/test_dashboard.py` L124–141, `queries.py` L11 |

**Verify:** `pytest tests/test_dashboard.py::test_dashboard_never_opens_writable_connection -v`

---

## Batch 2 — Opus review (หลัง Batch 1 ship หรือขนานถ้าไม่ block)

ลำดับตามความเสี่ยง — ใช้ prompt template ใน `opus-review-plan-6165b3.md`

| ลำดับ | WP | ระดับ | เงื่อนไข |
|---|---|---|---|
| 1 | **WP-2** re-review | Deep | หลัง F1–F7 |
| 2 | **WP-4** LLM extraction | Deep | ไม่มี report — trace `worker/extract.py` + `tests/test_extract.py` |
| 3 | **WP-5** Dedup | Deep | หลัง WP-4 pass; trace `worker/dedup.py` |
| 4 | **WP-8** Fingerprint | Deep (เข้มสุด) | หลัง WP-5; ขอ fixture เสียง offset |
| 5 | **WP-3** re-review | Deep | หลัง G1–G4 |
| 6 | **WP-9** re-review | Standard | หลัง F8 |
| 7 | **WP-7a** re-review | Spot-check | หลัง F5–F6 |
| 8 | **WP-10a** | Spot-check | มี `wp10a-report.md` แล้ว — ยังไม่ตรวจ |

---

## Batch 3 — Implement งานใหม่ (หลัง WP-4/5 review pass)

| WP | Owner | Blocked by | งาน |
|---|---|---|---|
| **WP-6** Alerter | GPT mini | WP-5 ship (ต้องมี detections จริง) | Telegram first-seen, ops >15min, digest, dry-run |
| **WP-7b** Docker finalize | GPT mini | WP-6 stub มี entrypoint, WP-2 F1–F2 | NVIDIA worker, `docker compose up`, healthy |
| **WP-10b** Instrument metrics | MiniMax M3 | WP-6 + ingestor metrics ports | `pipeline_*` ตาม `wp10a-report.md` metric table |
| **WP-11a** e2e + Phase 1 gaps | GPT mini | WP-6 ship | concurrent retry test, `import json` ใน models.py |
| **WP-11b** extraction eval set | GPT high | WP-4 ship | fixture transcripts + scoring rubric |

---

## Batch 1 — ✅ เสร็จแล้ว (2026-06-10, 4 session ขนาน)

| Session | Owner | ผล | Tests |
|---|---|---|---|
| S1 | GPT mini | WP-2 F1–F7 ✅ `plan/wp2-report.md` | ingestor 8 tests |
| S2 | Composer 2.5 | WP-3 G1–G4 + WP-9 F8 ✅ | worker+dashboard 22 |
| S3 | MiniMax M3 | WP-7a F5–F6 ✅ | config 5 + compose config |
| S4 | Opus | WP-4 Deep review → **fix-then-ship** N1–N4 | extract 5/5 |

**รวม:** `pytest` **64/64 passed**

## Batch 2 — ✅ เสร็จแล้ว (2026-06-10)

| Session | ผล |
|---|---|
| WP-4 N1–N4 | ✅ ship — `plan/wp4-report.md`, 67 pytest |
| Re-review WP-2,3,9,7a | ✅ ทั้ง 4 ship |
| WP-5 Deep review | 🔧 fix-then-ship (H1 phone scoring) |
| WP-10a Spot-check | ✅ ship (F1 datasource uid, F2 VRAM PromQL) |

## Batch 3 — ✅ เสร็จแล้ว (Codex CLI + Cursor)

WP-5 ship, WP-6 ship, WP-10b ship, WP-8 review → fix-then-ship. **74/74 pytest**

## Batch 4 — ✅ เสร็จแล้ว (Codex CLI, 2026-06-10)

| Session | ผล |
|---|---|
| A WP-8 fixes | ✅ ship — threshold strict, multi-offset + CPU tests, `plan/wp8-report.md` |
| B WP-7b Docker | ✅ ship — metrics ports, ollama-pull dep, `plan/wp7b-report.md` |
| C WP-11a hardening | ✅ ship — retry test, `import json`, e2e smoke, `plan/wp11a-report.md` |
| D WP-11b eval set | ✅ ship — extraction eval corpus + scorer, `plan/wp11b-report.md` |
| E Opus close gate | ✅ **ทุก WP ship** — `plan/opus-review-plan-6165b3.md` checklist ปิด |

**83/83 pytest** · `docker compose config --quiet` OK

Optional (operator): WP-2 F6 live ingestor smoke เมื่อมี enabled stream; WP-7b `docker compose up` on GPU host

---

## Reports ที่ต้องสร้าง/อัปเดต

| ไฟล์ | ใคร | เมื่อไหร่ |
|---|---|---|
| `plan/wp2-report.md` | GPT mini | หลัง F1–F7 |
| `plan/wp3-report.md` (revise) | Composer 2.5 | หลัง G1–G4 |
| `plan/wp4-report.md` | GPT high | หลัง Opus review pass หรือพร้อม review |
| `plan/wp5-report.md` | GPT high | หลัง WP-4 |
| `plan/wp8-report.md` | GPT high | หลัง WP-5 |

---

## อัปเดต AGENTS.md (หลัง Batch 1)

- Tests: 58/58
- WP-9, WP-7a, WP-10a: done แต่รอ fix-then-ship
- Phase 2 ingestor: implemented, ไม่ ship จนกว่า Opus re-review
- Worker: ASR + extract + dedup + fingerprint ใน consumer (scope drift จาก WP-3 handoff)
