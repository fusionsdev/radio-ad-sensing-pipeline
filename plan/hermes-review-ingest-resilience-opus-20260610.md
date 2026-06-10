Good. I've now read all the source files, verified tests pass, and checked the constraints. Here's my review:

---

## Opus Review Gate — WP-ingest-resilience

### Spec alignment

PLAN.md says: "ffmpeg reconnect + supervisor loop w/ backoff; gap logging"

The WP adds immediate retries before the backoff loop, with configurable knobs. This is an additive improvement to the specified backoff behavior — it does not contradict the spec. ffmpeg reconnect flags already existed (verified in test_build_ffmpeg_command). Gap logging invariant (1 per run_once) is preserved. Settings wired correctly through PipelineSettings -> create_station_ingestors -> BackoffPolicy.

### Findings (critical / major / minor)

- [minor] ingestor/supervisor.py:120-126 — On retry attempts where the runner writes a partial file (returncode != 0 but file exists), the file is only cleaned up on the NEXT iteration's `if attempt > 0` block. If the initial attempt (attempt=0) writes a partial file and fails returncode!=0, the partial file is cleaned up by attempt=1 before retrying. This is correct. However, if the LAST retry attempt writes a partial file and fails, the cleanup happens in the "all attempts exhausted" block at line 163. This path is also covered. No bug here on closer inspection — the flow is correct.

- [minor] ingestor/supervisor.py:130-133 — `chunk_len` is computed inside the loop on every iteration (`chunk_len = float(self.settings.chunk_len)`) even though it's constant. Trivial inefficiency, no correctness impact. Could be hoisted above the loop next to `retry_delay`.

- [minor] supervisor.py:87 — BackoffPolicy dataclass defaults (5/300) are now vestigial for production since create_station_ingestors always overrides them. The report acknowledges this ("remain for unit-test backward-compat"). The old tests explicitly construct BackoffPolicy with their own values so this is harmless, but it could confuse a developer who constructs StationIngestor directly without overriding backoff. Consider adding a comment on the BackoffPolicy class noting that production defaults come from PipelineSettings.

- [minor] tests/test_ingestor.py:SequencedFakeRunner — When the returncodes list is exhausted, `pop(0)` falls through to the `else` branch returning 0 (success). This is intentional per the docstring ("last entry repeated forever once list is exhausted"). However the `else` branch is `0` hardcoded, NOT popping the last entry. If the list `[1, 1, 0]` is given, calls 4+ always succeed with 0 — matching the docstring. Correct.

- [info] tests/test_ingestor.py — The three new tests set `ingest_immediate_retry_delay_sec=0.0`, so the 0.5s default delay path is never exercised in tests. This is fine for unit test speed, but there's no test verifying that retry delay sleeps actually accumulate correctly when `delay > 0`. Low risk since the code is trivially `if retry_delay > 0: self.clock.sleep(retry_delay)`.

- [info] The 1 pre-existing failure (test_telegram_settings_optional) is confirmed unrelated — it's an env var leak from the host's TELEGRAM_BOT_TOKEN. Not a blocker.

### Verified commands

TRUSTED (I ran them myself):
  - `pytest tests/test_ingestor.py -v` => 11/11 passed
  - `pytest -v` => 103/104 passed (1 pre-existing failure, unrelated)

TRUSTED (I read source directly):
  - shared/models.py: import-light (only stdlib + pydantic)
  - ingestor/supervisor.py: imports only shared.models and shared.metrics
  - ingestor/repository.py: all 3 DB functions use short single-statement transactions with @retry_on_busy + connection closed in finally
  - config/settings.yaml: 4 new keys match PipelineSettings defaults exactly
  - create_station_ingestors: correctly wires BackoffPolicy from settings

NO RE-RUN NEEDED — bundle claims match actual code and test output.

### Verdict

VERDICT: ship

The implementation is correct, well-tested, and spec-aligned. The immediate retry loop has the right invariants (single gap per failure event, backoff reset on any success, partial cleanup between attempts). Settings are properly wired. DB transactions stay short. shared/ stays import-light. The three new tests cover the key behavioral paths (recover-without-gap, exhausted-logs-single-gap, backoff-uses-settings). The existing tests were minimally updated (retries=0) to preserve their original assertions. No correctness bugs found.
