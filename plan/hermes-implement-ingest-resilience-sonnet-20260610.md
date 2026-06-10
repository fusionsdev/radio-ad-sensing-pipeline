**103 passed / 1 pre-existing failure** (unrelated Telegram env-leak, confirmed failing before this WP).

---

## Summary

### WP-ingest-resilience — SHIPPED

**TDD flow followed strictly:**
- RED: 3 new tests written first → all failed as expected
- Implementation: 3 files changed
- GREEN: 11/11 ingestor tests pass, 103/104 total pass

**Files changed:**

| File | Change |
|---|---|
| `shared/models.py` | +4 fields to `PipelineSettings` with matching defaults |
| `config/settings.yaml` | +4 matching YAML keys |
| `ingestor/supervisor.py` | `run_once` immediate-retry loop; `create_station_ingestors` wires BackoffPolicy from settings |
| `tests/test_ingestor.py` | +`SequencedFakeRunner` helper + 3 new tests; 2 existing tests pinned to `ingest_immediate_retries=0` |
| `plan/wp-ingest-resilience-report.md` | Operator report |

**Behavior change:**
- Stream blip recovery: 5s penalty → ~1s (3 immediate retries × 0.5s delay, zero gap logged on recovery)
- Backoff cap: 300s → 30s (configurable via `ingest_backoff_max_sec`)
- Gap log guarantee: always exactly 1 gap per `run_once` failure event, never one per retry

**pytest result: 103 passed** (3 new tests added; pre-existing Telegram env-leak failure unchanged at 1).
