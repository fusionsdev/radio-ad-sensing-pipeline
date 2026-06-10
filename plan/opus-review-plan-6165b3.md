# Opus Review Plan — ตรวจงานทุก WP แบบลดหลั่นตามความเสี่ยง

Opus เป็น review gate ของทุก work package โดยใช้ความลึก 3 ระดับ (Deep / Standard / Spot-check) ตามความเสี่ยงของงาน เพื่อคุมคุณภาพครบทุกชิ้นโดยไม่เปลือง token

## หลักการ

- **ตรวจหลังผู้ทำส่ง report** (`plan/wpN-report.md`) — ไม่เชื่อรายงาน ต้อง trace โค้ดจริง + รัน verify commands เอง (แบบเดียวกับที่ตรวจ Phase 1)
- **สองแกนเสมอ**: (1) Spec — ตรงกับ handoff + `PLAN.md` ไหม (2) Standards — โค้ดสะอาด, ใช้ `shared/` ไม่ reimplement, `shared/` ยัง import-light
- **ผล review**: ship / fix-then-ship (รายการแก้ส่งกลับผู้ทำเดิม) / rework (ส่ง tier สูงขึ้นทำใหม่)
- ทุก review จบด้วยอัปเดต checklist ในไฟล์นี้

## ระดับความลึก

| ระดับ | ทำอะไร | ใช้กับ |
|---|---|---|
| **Deep** | trace ทุก code path end-to-end, ไล่ edge cases, ตรวจ concurrency/failure paths, ตรวจว่า tests exercise path จริง (ไม่ mock จนไร้ความหมาย), รัน pytest + adversarial input | งานที่ผิดแล้วลามทั้งระบบ |
| **Standard** | อ่าน diff ทั้งหมด + trace เฉพาะ critical path, รัน pytest + manual smoke 1 รอบ, ตรวจ acceptance criteria ทีละข้อ | งาน implement ตาม spec |
| **Spot-check** | รัน verify commands + สุ่มอ่าน 2–3 จุดที่ผิดบ่อย (path, env var, port, ชื่อ metric) | งาน declarative/config |

## ตาราง review ราย WP

| WP | ผู้ทำ | ระดับ | จุดที่ Opus ต้องเพ่งเป็นพิเศษ | Verify commands |
|---|---|---|---|---|
| **WP-1** Scaffold+DB | Cursor | ~~Deep~~ **ตรวจแล้ว** ✅ | ค้างแก้: concurrent test ไม่ exercise retry path, `import json` กลางไฟล์ — มอบ GPT mini ใน WP-11 | `pytest` |
| **WP-2** Ingestor | GPT mini | **Deep** | reconnect/backoff ไม่ spin-loop, partial chunk ตอน stream ตาย, gap log ครบช่วง, ffmpeg zombie process, chunk timestamp ไม่ drift | `pytest`; รัน ingestor กับ stream จริง 5 นาที แล้วดู `chunks`/`gaps` |
| **WP-3** ASR worker | Composer 2.5 | **Deep** | atomic claim (สอง consumer ห้ามชน), drop-oldest นับ backlog ถูก, segments_json เก็บ timestamps ครบ (WP-5 ต้องใช้), RTF logging, model mock ใน test ไม่กลบ logic จริง | `pytest`; ตรวจ migration 002 |
| **WP-4** LLM extraction | GPT high | **Deep** | prompt กัน false positive (รายการคุยเรื่องเงินกู้ ≠ โฆษณา), JSON schema ตรง `AdExtraction`, retry-on-invalid-JSON, phone normalization edge cases ("eight hundred" → 800), ห้ามมี station/timestamp ใน prompt schema | `pytest`; รัน eval set ถ้ามีแล้ว |
| **WP-5** Dedup | GPT high | **Deep** | fuzzy threshold ไม่ over/under-merge, 3-min airing window ทำงานข้าม chunk overlap, ตัด clip จาก segment timestamps ±2s ถูกต้อง, `airing_count` ไม่เฟ้อ | `pytest` + fixture transcripts ซ้ำ ๆ |
| **WP-6** Alerter | GPT mini | **Standard** | alert เฉพาะ first-seen, `alerted` flag กันส่งซ้ำหลัง restart, ops alert >15min ไม่ spam ทุก loop, token ไม่หลุดใน log | `pytest`; dry-run กับ mock Telegram API |
| **WP-7a** Docker skeleton | MiniMax M3 | **Spot-check** | volume paths ตรง `data/`, service names ตรงแผน 7 ตัว, healthcheck ไม่ fail ตอน boot ช้า | `docker compose config` |
| **WP-7b** Docker finalize | GPT mini | **Standard** | NVIDIA runtime เฉพาะ worker, Ollama pull model ตอน start, restart policy, `.env` ไม่ bake ลง image | `docker compose up` + `docker compose ps` ทุกตัว healthy |
| **WP-8** Fingerprint | GPT high | **Deep (เข้มสุด)** | sliding-window matching ถูกหลัก (chunk 90s vs clip 30s ที่ offset ใด ๆ), threshold มี test ทั้ง true-match และ near-miss, false `known_ad` ไม่ทำข้อมูลหาย (transcription ยังรัน), CPU time ต่อ chunk ไม่กิน budget | `pytest` + fixture เสียงจริง: คลิปเดียวกันฝังที่ offset ต่างกัน |
| **WP-9** Dashboard | Composer 2.5 | **Standard** | read-only จริงทุก connection, `/audio` กัน path traversal, ทุกหน้า render ได้บน DB ว่าง, ไม่มี write path | `pytest`; เปิดทุก route บน empty DB |
| **WP-10a** Monitoring config | MiniMax M3 | **Spot-check** | scrape targets ตรงชื่อ service ใน compose, datasource UID ตรง dashboard JSON | `promtool check config`; Grafana ขึ้น dashboard ไม่ error |
| **WP-10b** Instrument metrics | MiniMax M3 | **Spot-check** | ชื่อ metric ตรง convention (`pipeline_*`), ไม่ instrument ใน hot loop จน latency เพิ่ม | `curl /metrics` ทุก service เทียบรายการชื่อ |
| **WP-11** Tests+hardening | GPT mini + high | **Standard** | e2e smoke ครอบ ingest→transcribe→extract→alert จริง, แก้ 2 จุดค้างจาก WP-1 review แล้ว, eval set มีเกณฑ์ให้คะแนนชัด | `pytest` ทั้ง suite + e2e |

## จังหวะ review (อัปเดต 2026-06-10 — ดู `plan/work-dispatch-6165b3.md`)

```
Batch 1 (fix-then-ship, ขนาน 4 สาย):
  GPT mini      → WP-2 F1–F7 (ffmpeg timeout, zombie, partial chunk, wp2-report)
  Composer 2.5  → WP-3 G1–G4 (report stale) + WP-9 F8 (read-only test)
  MiniMax M3    → WP-7a F5–F6 (dashboard bind env, alerter Dockerfile/healthcheck)
  Opus (ขนาน)   → WP-4 Deep review (โค้ดมีแล้ว ไม่มี report)

Batch 2 (re-review หลัง Batch 1):
  WP-2 Deep → WP-4 (ถ้ายังไม่เสร็จ) → WP-5 Deep → WP-8 Deep → WP-3/9/7a/10a

Batch 3 (implement ใหม่):
  GPT mini  → WP-6, WP-7b, WP-11a smoke
  GPT high  → WP-11b eval set
  MiniMax M3 → WP-10b metrics
```

## Prompt template สำหรับ Opus

```
Act as the review gate. Read these in order:
1. PLAN.md (architecture + decisions — do not re-litigate)
2. .windsurf/plans/handoff-wpN-...-6165b3.md (spec for this WP)
3. plan/wpN-report.md (implementer's claims)
Then review at [Deep/Standard/Spot-check] level per
C:\Users\Barbara\.windsurf\plans\opus-review-plan-6165b3.md:
- Verify every acceptance criterion yourself (run commands, don't trust the report)
- Trace the focus areas listed for this WP
- Output: findings ordered by severity, each with file:line evidence,
  then verdict: ship / fix-then-ship (with fix list) / rework
```

## Review checklist (อัปเดตหลังตรวจแต่ละงาน)

- [x] WP-1 — ✅ ship (2 จุดค้างโอนเข้า WP-11)
- [x] WP-2 — ✅ **ship** (Batch 2 Opus Deep re-review): F1–F5/F7 verified, 8/8 ingestor pytest; F6 smoke skipped
- [x] WP-3 — ✅ **ship** (Batch 2 Opus Deep re-review): G1–G4 verified, 9/9 worker pytest; create_consumer wired
- [x] WP-4 — ✅ **ship** (Batch 2 fix-then-ship): N1 vanity fallback, N2 toll-free prefix relax, N3 regression tests, N4 few-shot ex.3 phone; `plan/wp4-report.md`; 67/67 pytest pass
- [x] WP-5 — ✅ **ship** (Batch 3 fix-then-ship): H1 omit mismatched phone weight, M2 category mismatch = 0, regression tests for mangled phone, distinct ads, same-station >180s, cross-station within 3min; `plan/wp5-report.md`; 69/69 pytest pass
- [x] WP-6 — ✅ **ship** (Batch 3 Codex CLI): Telegram alerter + dry-run, `plan/wp6-report.md`, 5 alerter tests
- [x] WP-7a — ✅ **ship** (Batch 2 Spot-check): F5/F6 verified, compose config OK
- [x] WP-7b — ✅ **ship** (Batch 4 Codex CLI Standard): metrics ports 9101–9104 exposed, worker waits on `ollama-pull`, NVIDIA scope unchanged; `plan/wp7b-report.md`; `docker compose config --quiet` OK
- [x] WP-8 — ✅ **ship** (Batch 4 Codex CLI fix-then-ship): strict borderline rejection at `0.88` (`score <= threshold` rejects), realistic 90s/30s multi-offset coverage (`0s`/`30s`/`45s`), 100-candidate CPU-budget guard; `plan/wp8-report.md`; 10/10 fingerprint pytest, **83/83** full suite
- [x] WP-9 — ✅ **ship** (Batch 2 Standard re-review): F8 + 13/13 dashboard pytest
- [x] WP-10a — ✅ **ship** (Batch 2 Spot-check + F1 uid:prometheus, F2 VRAMNearFull parens)
- [x] WP-10b — ✅ **ship** (Batch 3 Codex CLI): `shared/metrics.py`, ports 9101–9104, `plan/wp10b-report.md`
- [x] WP-11 — ✅ **ship** (Batch 4 Codex CLI): 11a retry test + `import json` fix + e2e smoke (`tests/test_e2e_smoke.py`); 11b extraction eval corpus + scorer (`tests/test_extraction_eval.py`); `plan/wp11a-report.md`, `plan/wp11b-report.md`; **83/83** pytest

**Gate closed:** ทุก WP ship (2026-06-10). Optional operator smoke: WP-2 F6 live ingestor, WP-7b `docker compose up` on GPU host.
