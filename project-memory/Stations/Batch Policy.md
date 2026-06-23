# Station Batch Policy

## Rotation logic (`scripts/station_rotation.py`)

| Decision | Criteria |
|---|---|
| **keep** | ≥2 unique loan advertisers |
| **watch** (pause monitor) | 1 unique loan advertiser |
| **rotate_out** | 0 loan ads after detections processed |

Classifier: `scripts/loan_classifier.py` — strict phrase-level, no single-word matches.

## Hermes batch (10 enabled)

See `.hermes.md` for current list. Verify `config/stations.yaml` `enabled:` flags before changes.

## Harness check

`tools/harness/runners/station_harness.py` validates rotation logic against fixture cases — no YAML mutations.

## Related

- [[03_Forbidden_Assumptions]]
- [[02_Operating_Policy]]