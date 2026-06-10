# pipeline.db live schema (verified 2026-06-11)

Source of truth: `docker exec radio-worker python -c "import sqlite3; ... PRAGMA table_info(...)"` and sample row counts.
**Do not trust `AGENTS.md` / `PLAN.md` / older skill text** for column names — they drifted.

## Tables present

```
schema_migrations, stations, sqlite_sequence, canonical_ads,
chunks, transcripts, detections, gaps, fingerprints,
status, keyword_hits, station_daily
```

## `chunks` — queue table (no Redis)

| col | type | notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `station_id` | INTEGER | FK → `stations.id` |
| `path` | TEXT | tmpfs path under `/app/chunks/<station>/` |
| `start_ts` | REAL | unix seconds (NOT `ingest_ts`) |
| `end_ts` | REAL | unix seconds |
| `status` | TEXT | `pending` / `processing` / `done` / `dropped` |
| `error` | TEXT | NULL on success |
| `known_ad_id` | INTEGER | FK → `canonical_ads.id` if fingerprint matched |

**Time filters:** use `end_ts > strftime('%s','now')-3600` for "last 1h".

## `detections` — LLM output

| col | type |
|---|---|
| `id` | INTEGER |
| `chunk_id` | INTEGER (NOT `station_id` — join via `chunks`) |
| `canonical_ad_id` | INTEGER |
| `is_ad` | INTEGER 0/1 |
| `ad_category` | TEXT (NOT `category`) |
| `company_name` | TEXT |
| `phone_number` | TEXT |
| `website` | TEXT |
| `offer_summary` | TEXT |
| `key_claims` | TEXT |
| `confidence` | REAL |
| `alerted` | INTEGER 0/1 |

## `keyword_hits` — separate from detections

Has `detection_id` FK, but **junction is empty in current data** even though
`detections` has 199 rows and `keyword_hits` has 0. Likely a gating/bug where
keyword scan only fires on certain `ad_category` values. Don't assume
`detections JOIN keyword_hits` produces useful rows.

## `canonical_ads` — deduplicated advertisers

`id, ?, ?, category, first_seen_ts, last_seen_ts`. Top values seen: `business_funding`,
`tax_relief`, `debt_relief`, `insurance`, `wine`, etc.

## Canonical copy-paste queries

Run with: `docker exec radio-worker python -c "<one-liner>"` (paste inside the
double-quoted python; escape inner quotes as needed). Or use
`scripts/pipeline_status_query.py` via:

```powershell
Get-Content scripts\pipeline_status_query.py -Raw | docker exec -i radio-worker python -
```

### Queue depth

```python
import sqlite3
c=sqlite3.connect('/app/data/pipeline.db')
for s in ('pending','processing','done','dropped'):
    print(s, c.execute(f"SELECT COUNT(*) FROM chunks WHERE status='{s}'").fetchone()[0])
c.close()
```

### Per-station health (last chunk age)

```python
import sqlite3, time
c=sqlite3.connect('/app/data/pipeline.db')
now=time.time()
for sid, name in c.execute('SELECT id, name FROM stations ORDER BY name'):
    row=c.execute('SELECT MAX(end_ts), COUNT(*) FROM chunks WHERE station_id=?',(sid,)).fetchone()
    last,total=row
    age_min = (now-last)/60 if last else None
    print(f'{name:14s} last_min={age_min!s:>8s} total={total}')
c.close()
```

Stations with `last_min > 720` (12h) are **stale** — stream probably dead or station
newly enabled but not flowing yet. Stations with `last_min > 1440` (24h) need
operator attention.

### Detection category mix (last N)

```python
import sqlite3
c=sqlite3.connect('/app/data/pipeline.db')
for cat, n in c.execute("SELECT ad_category, COUNT(*) FROM detections GROUP BY ad_category ORDER BY 2 DESC"):
    print(cat, n)
c.close()
```

### Top advertisers

```python
import sqlite3
c=sqlite3.connect('/app/data/pipeline.db')
for co, n in c.execute("SELECT company_name, COUNT(*) FROM detections WHERE company_name IS NOT NULL AND company_name<>'' GROUP BY company_name ORDER BY 2 DESC LIMIT 10"):
    print(co, n)
c.close()
```

### Keyword scan health (often returns 0!)

```python
import sqlite3
c=sqlite3.connect('/app/data/pipeline.db')
print('keyword_hits:', c.execute('SELECT COUNT(*) FROM keyword_hits').fetchone()[0])
for k, n in c.execute('SELECT keyword, COUNT(*) FROM keyword_hits GROUP BY keyword ORDER BY 2 DESC LIMIT 10'):
    print(k, n)
c.close()
```

**Heuristic for "is the system actually working":** if `canonical_ads` is growing
and `detections.is_ad = 1` count > 50/day, the pipeline is healthy. `keyword_hits = 0`
alone is **not** a degradation signal — see notes above.
