# WP — Keyword Stats + Station Scorecard (MVP 1–2)

**Date:** 2026-06-10  
**Status:** Shipped  
**Tests:** 127/127 passing

## Goal

Track loan keyword hits per station, expose yield metrics for limited ingest slot decisions, and surface ops health + content value on the dashboard.

## MVP 1 (data collection)

| Item | Path |
|------|------|
| Seed keywords | `config/loan_keywords.yaml` |
| Migration | `shared/migrations/003_keyword_hits.sql` |
| Scanner | `worker/keywords.py` |
| Worker hook | `worker/consumer.py` — scan after ASR, same transaction as transcript |
| Config loader | `shared/config.py` → `load_loan_keywords()` |

## MVP 2 (operator visibility)

| Item | Path |
|------|------|
| Migration | `shared/migrations/004_station_daily.sql` |
| Daily rollup | `worker/janitor.py` → `rollup_station_daily()` |
| Yield helpers | `dashboard/stats.py` |
| Scorecard query | `dashboard/queries.py` → `fetch_station_scorecard()` |
| Keyword matrix | `dashboard/queries.py` → `fetch_keyword_matrix()` |
| UI | `/scorecard`, `/keywords` |

## Slot recommendation hints

| Hint | Rule |
|------|------|
| **swap** | enabled + live ingest + ≥50 chunks/7d + 0 keyword hits |
| **fix** | enabled + status down/stale |
| **review** | enabled + yield < 0.3% + < 2 keyword hits |
| **bench** | disabled |
| **keep** | otherwise |

## Operator URLs

- `http://127.0.0.1:8080/scorecard` — station yield ranking
- `http://127.0.0.1:8080/keywords` — keyword × station matrix

## Next (MVP 3)

- URL probe janitor for bench pool
- Hermes weekly swap brief
- Optional auto slot rotator
