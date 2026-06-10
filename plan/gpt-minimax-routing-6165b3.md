# Model Routing: GPT (high + mini) และ MiniMax M3

**อัปเดต:** 2026-06-10 — หลังอ่าน reports + `plan/opus-review-plan-6165b3.md` checklist  
**Verify ล่าสุด:** `pytest` → 58 passed

จัดสรรงานที่เหลือให้ GPT high/mini, Composer 2.5, MiniMax M3 และ Opus review gate ตาม tier และผล review

## สถานะจาก reports (สรุป)

| WP | Report | Review verdict | หมายเหตุ |
|---|---|---|---|
| WP-1 | `phase1-report.md` | ✅ ship | 2 จุดโอน WP-11 |
| WP-2 | ❌ ไม่มี | 🔧 fix-then-ship | โค้ดมี + tests 4 ตัว; Opus Deep พบ F1–F7 |
| WP-3 | `wp3-report.md` | 🔧 fix-then-ship | report บอก ASR-only แต่ `consumer.py` รวม extract/dedup/fingerprint แล้ว |
| WP-4 | ❌ ไม่มี | ⏳ Opus Deep | `worker/extract.py` + `tests/test_extract.py` มีแล้ว |
| WP-5 | ❌ ไม่มี | ⏳ Opus Deep | `worker/dedup.py` + `tests/test_dedup.py` มีแล้ว |
| WP-6 | ❌ ไม่มี | ⏳ ยังไม่ทำ | `alerter/` stub เท่านั้น |
| WP-7a | `wp7a-report.md` | 🔧 fix-then-ship | F5 env bind + F6 alerter Dockerfile |
| WP-7b | ❌ ไม่มี | ⏳ ยังไม่ทำ | รอ fix wave + service ครบ |
| WP-8 | ❌ ไม่มี | ⏳ Opus Deep | `worker/fingerprint.py` + `tests/test_fingerprint.py` มีแล้ว |
| WP-9 | `wp9-report.md` | 🔧 fix-then-ship | F8 read-only test false positive |
| WP-10a | `wp10a-report.md` | ⏳ Opus spot-check | ยังไม่ติ๊ก checklist |
| WP-10b | ❌ ไม่มี | ⏳ blocked | รอ ingestor + alerter emit metrics |
| WP-11 | ❌ ไม่มี | ⏳ ปิดท้าย | รวม WP-1 debt + e2e |

## Wave 1 — Fix-then-ship (ขนาน 4 สาย, ส่งทันที)

### 1a. GPT mini → WP-2 Ingestor fixes (F1–F7)

| # | แก้ | หลักฐาน |
|---|---|---|
| F1 | `subprocess.run` → `Popen` + timeout = `chunk_len + grace` | `ingestor/ffmpeg.py:83` — hang เมื่อ EOF+reconnect |
| F2 | ลบหรือจำกัด `-reconnect_at_eof 1` (หรือ timeout ครอบคลุม) | สาเหตุ hang บน dead stream |
| F3 | SIGTERM: ส่ง terminate ไป ffmpeg child; `join` มี deadline | `ingestor/__main__.py` — daemon thread ค้าง mid-chunk |
| F4 | validate duration จริง (ffprobe หรือ wave header) ก่อน enqueue | มีแค่ `st_size > 0` |
| F5 | zombie reaping ใน shutdown path | ไม่มี process group cleanup |
| F6 | test: subprocess timeout → gap + backoff (ไม่ใช่ FakeRunner เท่านั้น) | `tests/test_ingestor.py` |
| F7 | เขียน `plan/wp2-report.md` หลังแก้ | ไม่มี report |

**Verify:** `pytest tests/test_ingestor.py -v` + ingestor 5 นาทีกับ stream จริง

### 1b. Composer 2.5 → WP-3 report + scope doc

| # | แก้ |
|---|---|
| S1 | อัปเดต `plan/wp3-report.md` — consumer เป็น full pipeline (ASR→fingerprint→extract→dedup) |
| S2 | ระบุ deviation ชัด: WP-4/5/8 ถูก merge เข้า consumer ก่อน review หรือไม่ |
| S3 | ยืนยัน tests ใน `test_worker_consumer.py` ครอบ path ใหม่ (ไม่ใช่แค่ ASR) |

**Verify:** `pytest tests/test_worker_consumer.py -v`

### 1c. Composer 2.5 → WP-9 Dashboard fix (F8)

| # | แก้ | หลักฐาน |
|---|---|---|
| F8 | แก้ `test_dashboard_never_opens_writable_connection` — patch `dashboard.queries.get_connection` ไม่ใช่ `shared.db.get_connection` | import bind ที่ module level ทำให้ monkeypatch หลอกผ่าน |

**Verify:** `pytest tests/test_dashboard.py::test_dashboard_never_opens_writable_connection -v`

### 1d. MiniMax M3 → WP-7a Docker fixes (F5 + F6)

| # | แก้ | หลักฐาน |
|---|---|---|
| F5 | `DASHBOARD_HOST` ใน compose ไม่มีผล — `load_settings()` อ่าน yaml อย่างเดียว (`shared/config.py:34`) | ใช้ `pydantic-settings` env override หรือลบ env ที่หลอก |
| F6 | `alerter/Dockerfile` CMD `python -m alerter` แต่ไม่มี `alerter/__main__.py` | เพิ่ม stub entrypoint หรือเปลี่ยน CMD เป็น no-op จน WP-6 |

**Verify:** `docker compose config --quiet`

## Wave 2 — Opus review gate (หลัง Wave 1 หรือขนานกับ 1a–1d ถ้าไม่ block)

ลำดับตาม `opus-review-plan-6165b3.md`:

```
Opus Deep   WP-4 (extraction)     — ก่อน WP-5
Opus Deep   WP-5 (dedup)          — หลัง WP-4
Opus Deep   WP-8 (fingerprint)    — เข้มสุด + fixture เสียง
Opus Spot   WP-10a (monitoring)   — promtool + datasource UID
Opus re-check WP-2,3,7a,9         — หลัง fix-then-ship แต่ละตัว
```

**ก่อนส่ง Opus:** ผู้ทำ WP-4/5/8 เขียน `plan/wp4-report.md`, `wp5-report.md`, `wp8-report.md` (หรือ Cursor เขียนให้จากโค้ดที่มี)

## Wave 3 — งานใหม่ (หลัง Opus ship WP-4/5)

| ลำดับ | ผู้ทำ | WP | เงื่อนไข |
|---|---|---|---|
| 1 | GPT mini | WP-6 Alerter | Opus ship WP-5; มี detections ใน DB |
| 2 | GPT mini | WP-7b Docker finalize | WP-6 มี `__main__.py`; GPU host พร้อม |
| 3 | MiniMax M3 | WP-10b Instrument metrics | ingestor + worker + alerter + dashboard emit ตาม `wp10a-report.md` |
| 4 | GPT mini | WP-11 smoke + WP-1 debt | concurrent retry test, `import json` ใน models.py |
| 5 | GPT high | WP-11 eval set | fixture โฆษณาเงินกู้ + เกณฑ์คะแนน |

## Wave 4 — ปิดโปรเจกต์

- Opus Standard WP-11 + e2e smoke
- ไล่ checklist ใน `opus-review-plan-6165b3.md` ให้ครบ 13/13
- อัปเดต `AGENTS.md`

## Tier mapping

| Model | Tier | จุดแข็ง/จุดอ่อน |
|---|---|---|
| **GPT high/thinking** | Heavy | reasoning ลึก, ออกแบบ algorithm/prompt ได้; แพง+ช้า — ใช้เฉพาะงานที่ผิดแล้วลาม |
| **GPT mini/fast** | Mid–Light | implement ตาม spec ชัดได้ดี, ถูก+เร็ว; อย่าให้ตัดสินใจเชิง design |
| **MiniMax M3** | Light (–Mid) | งาน declarative/pattern ซ้ำ, config, boilerplate; ความแม่นยำ instruction-following ต่ำกว่า GPT mini — งานที่ verify ง่ายเท่านั้น |

## งานของ GPT high (Heavy — 2 งานคงเหลือ)

| WP | งาน | หมายเหตุ |
|---|---|---|
| **WP-8** Fingerprint (P8) | ~~implement~~ → **Opus Deep review** + แก้ถ้า fail | โค้ดมีแล้ว (`worker/fingerprint.py`) |
| **WP-11 eval set** | fixture โฆษณาเงินกู้จริง + เกณฑ์ให้คะแนน | ทำหลัง Opus ship WP-4 |

~~WP-4, WP-5~~ — implement เงียบ ๆ แล้ว → ส่ง Opus Deep แทน implement ใหม่

## งานของ GPT mini (Mid — 3 งาน)

| WP | งาน | สถานะ |
|---|---|---|
| **WP-2** Ingestor | ~~implement~~ → **แก้ F1–F7** (Wave 1a) | Opus Deep ตรวจแล้ว fix-then-ship |
| **WP-6** Alerter (P6) | Telegram sendMessage/sendAudio, ops alerts, daily digest | Wave 3 — หลัง Opus ship WP-5 |
| **WP-7b** Docker finalize (P7) | `docker compose up` + GPU sanity | Wave 3 — หลัง WP-6 |

## งานของ MiniMax M3 (Light — 3 งาน)

| WP | งาน | สถานะ |
|---|---|---|
| **WP-7a** Docker skeleton | ~~implement~~ → **แก้ F5+F6** (Wave 1d) | report มีแล้ว |
| **WP-10a** Monitoring config | ~~implement~~ → **Opus spot-check** (Wave 2) | report มีแล้ว |
| **WP-10b** Instrument metrics | แปะ `pipeline_*` metrics ทุก service | Wave 3 — รอ WP-6 |

**กติกาสำหรับ M3**: ให้ spec แบบ explicit ที่สุด (ไฟล์ตัวอย่าง + รายการ metric ชื่อตรงตัว), งานละ session, ตรวจผลด้วยคำสั่ง verify อัตโนมัติ (`docker compose config`, `promtool check config`, `pytest`)

## WP-11 Tests + hardening — แบ่งสองส่วน

- **Extraction eval set** (ออกแบบ fixture โฆษณาเงินกู้จริง + เกณฑ์ให้คะแนน) → **GPT high**
- **e2e smoke test + แก้ test gap จาก Phase 1 review** (concurrent test ไม่ exercise retry path, `import json` กลางไฟล์ models.py) → **GPT mini**

## ลำดับส่งงาน (ปัจจุบัน)

```
Wave 1 (ขนาน — ส่งทันที):
  GPT mini      ── WP-2 fixes F1–F7 + wp2-report
  Composer 2.5  ── WP-3 report/scope S1–S3
  Composer 2.5  ── WP-9 fix F8
  MiniMax M3    ── WP-7a fixes F5+F6

Wave 2 (Opus review gate):
  Opus Deep     ── WP-4 → WP-5 → WP-8
  Opus Spot     ── WP-10a
  Opus re-check ── WP-2,3,7a,9 หลัง Wave 1

Wave 3 (implement ใหม่):
  GPT mini      ── WP-6 → WP-7b
  MiniMax M3    ── WP-10b

Wave 4 (ปิด):
  GPT mini+high ── WP-11
  Opus Standard ── e2e + checklist 13/13
```

## Handoffs / reports

| WP | Handoff | Report |
|---|---|---|
| WP-1 | `handoff-phase1-scaffold-db-6165b3.md` | `phase1-report.md` ✅ |
| WP-2 | ❌ ต้องร่างหลัง fix | ❌ ต้องเขียน |
| WP-3 | `handoff-wp3-asr-worker-6165b3.md` | `wp3-report.md` (stale) |
| WP-4–5,8 | ❌ | ❌ ต้องเขียนก่อน Opus |
| WP-7a | (ใน wp7a-report) | `wp7a-report.md` |
| WP-9 | `handoff-wp9-dashboard-6165b3.md` | `wp9-report.md` |
| WP-10a | (ใน wp10a-report) | `wp10a-report.md` |
