# Owner Review Diff Packet

## Scope

- Thai-localized the dashboard chrome and status labels.
- Tightened the dashboard regression tests so leftover English UI text is caught.
- Added repeatable owner-review QA guidance and request-host logging to the browser smoke harness.

## Key Files

- [dashboard/main.py](../dashboard/main.py)
- [dashboard/templates/base.html](../dashboard/templates/base.html)
- [dashboard/templates/index.html](../dashboard/templates/index.html)
- [dashboard/templates/review.html](../dashboard/templates/review.html)
- [dashboard/templates/ops/watchdog.html](../dashboard/templates/ops/watchdog.html)
- [dashboard/templates/ads.html](../dashboard/templates/ads.html)
- [dashboard/templates/keyword_hits.html](../dashboard/templates/keyword_hits.html)
- [dashboard/templates/no_database.html](../dashboard/templates/no_database.html)
- [dashboard/templates/scorecard.html](../dashboard/templates/scorecard.html)
- [dashboard/templates/novelty/_table.html](../dashboard/templates/novelty/_table.html)
- [dashboard/templates/novelty/batch_review.html](../dashboard/templates/novelty/batch_review.html)
- [scripts/browser_resolve_streams.py](../scripts/browser_resolve_streams.py)
- [tests/test_dashboard.py](../tests/test_dashboard.py)
- [tests/test_watchdog.py](../tests/test_watchdog.py)
- [docs/OWNER_REVIEW_QA.md](../docs/OWNER_REVIEW_QA.md)

## Verification

- `python -m pytest -q tests/test_dashboard.py tests/test_watchdog.py`
- Result: `37 passed`

## Browser Smoke

- Seeded temp DB and launched the dashboard on `http://127.0.0.1:8002/`
- Visited:
  - `/`
  - `/review`
  - `/ops/watchdog`
  - `/ads`
- Thai chrome checks passed on those pages.

### Request hosts

- `request_hosts = ["127.0.0.1:8002"]`
- `request_host_count`: `1`
- `request_hosts`:
  - `127.0.0.1:8002`
- `local_only`: `true`

### Note

- Dashboard smoke is local-only. The browser only contacted `127.0.0.1:8002`.
- HTMX is served locally from `/static/vendor/htmx.min.js`.
- `dashboard/templates/base.html` no longer loads the external HTMX CDN.
