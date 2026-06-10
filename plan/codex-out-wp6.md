WP-6 is in place.

What changed:
- Added a real Telegram alerter service in [alerter/service.py](H:/DEV/projects/radio-ad-sensing-pipeline/alerter/service.py) for:
  - first-seen detection alerts
  - optional `sendAudio` when archived audio exists
  - station-down ops alerts
  - queue-drop ops alerts
  - daily digest
  - dry-run mode when Telegram credentials are missing
- Replaced the stub entrypoint in [alerter/__main__.py](H:/DEV/projects/radio-ad-sensing-pipeline/alerter/__main__.py) with a real poll loop and signal shutdown handling.
- Updated [shared/config.py](H:/DEV/projects/radio-ad-sensing-pipeline/shared/config.py) so `TelegramSettings` can be constructed by field name in code/tests.
- Added mocked Telegram HTTP coverage in [tests/test_alerter.py](H:/DEV/projects/radio-ad-sensing-pipeline/tests/test_alerter.py).
- Wrote the phase report at [plan/wp6-report.md](H:/DEV/projects/radio-ad-sensing-pipeline/plan/wp6-report.md).

Verification:
- `.venv\Scripts\pytest tests/test_alerter.py -v` → 5 passed
- `.venv\Scripts\pytest -q` → 74 passed

One small implementation note: dry-run mode logs alerts and still advances alert state so it does not spam every loop when `TELEGRAM_BOT_TOKEN` is unset.