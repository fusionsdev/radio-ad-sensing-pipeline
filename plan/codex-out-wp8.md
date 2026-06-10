**Findings**

1. Medium: near-miss threshold behavior is not acceptance-tested, so the conservative-match claim is still unproven. The only rejection test uses a maximally dissimilar vector, not a realistic near-threshold false positive case, even though WP-8 explicitly calls for “true-match and near-miss” coverage. Evidence: [tests/test_fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_fingerprint.py:113), [plan/opus-review-plan-6165b3.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/opus-review-plan-6165b3.md:32), [PLAN.md](h:/DEV/projects/radio-ad-sensing-pipeline/PLAN.md:107).

2. Medium: offset-tolerant matching is only proven with a toy 4-frame synthetic vector, not with a realistic 90s-chunk vs 30s-clip fixture at multiple offsets as required by the WP-8 review plan. The implementation does slide correctly, but the acceptance proof is thinner than the spec asks for. Evidence: [worker/fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/fingerprint.py:66), [tests/test_fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_fingerprint.py:95), [plan/opus-review-plan-6165b3.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/opus-review-plan-6165b3.md:32), [PLAN.md](h:/DEV/projects/radio-ad-sensing-pipeline/PLAN.md:42).

3. Low: CPU budget is not guarded by tests or instrumentation. The matcher is a pure Python brute-force sliding window over every candidate and offset, so cost grows linearly with catalog size. On this host, a synthetic 360-frame chunk vs 120-frame clip benchmark measured about `0.003s` per call for 1 candidate, `0.028s` for 10, and `0.300s` for 100, which is probably acceptable now but is not enforced anywhere. Evidence: [worker/fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/fingerprint.py:75), [plan/opus-review-plan-6165b3.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/opus-review-plan-6165b3.md:32).

**Spec Checklist**

- Pass: sliding-window offset logic exists and returns the best offset/score, matching the Phase 8 design. See [worker/fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/fingerprint.py:66).
- Pass: false `known_ad` does not lose transcript in the worker path; ASR still runs and transcript persistence is tested. See [worker/consumer.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/consumer.py:200), [tests/test_worker_consumer.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_worker_consumer.py:243).
- Pass: same-station 3-minute overlap de-double-counting is covered for the fingerprint fast path. See [worker/fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/fingerprint.py:184), [tests/test_fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_fingerprint.py:160).
- Fail: no near-miss threshold regression test.
- Fail: no realistic multi-offset fixture test.
- Partial: CPU budget looks plausible in a synthetic probe, but there is no repo-level guardrail.

**Test Gaps**

- Add a borderline near-miss case around the chosen `0.88` threshold.
- Add a realistic long-vector or fixture-audio test with the same ad embedded at several offsets.
- Add either a perf test budget or lightweight timing instrumentation so runtime drift is visible as the fingerprint catalog grows.

**Verdict**

`fix-then-ship`

1. Add near-miss threshold tests that would catch false positives from similar jingles/spot variants.
2. Add a realistic offset fixture test for 90s chunk vs 30s clip at multiple offsets.
3. Add a CPU-budget guard: perf assertion, benchmark fixture, or runtime metric/log for matcher latency.

Verification ran as requested: `.venv\Scripts\pytest tests\test_fingerprint.py -v` passed `5/5`, and `pytest -q` passed `69/69`. I also updated the WP-8 checklist line in [plan/opus-review-plan-6165b3.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/opus-review-plan-6165b3.md:81).