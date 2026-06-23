# Station Health Report

## Method

- 10 minute probe per station
- Same ffmpeg reconnect flags as the ingestor
- 90s chunk capture loop, mirroring the live supervisor behavior
- Audio quality measured from captured WAV chunks
- Silence ratio uses 1.0s windows with a -45 dBFS threshold

## Ranking

| Rank | Station | Verdict | Probe chunks/min | RMS dBFS | Silence ratio | Decode errors | Live DB chunks in window | Live empty_chunk gaps |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | wbap-am-820 | keep | 1.87 | -18.76 | 2.69% | 0 | 2 | 1 |
| 2 | klif-am-570 | keep | 1.87 | -20.19 | 2.92% | 0 | 0 | 1 |
| 3 | ktsa-550 | pause | 0.00 |  |  | 126 | 0 | 5 |

## Interpretation

- `wbap-am-820` and `klif-am-570` both produced 19 successful chunks in about 10 minutes, with clean stderr and low silence ratios. These are keepers.
- `ktsa-550` produced 0 valid chunks in the same window and logged repeated AAC decode failures. This should be paused now; rotate or replace the source URL after validation.
- The live DB window counts were lower than the direct probe yield for KLIF and WBAP, which suggests the live ingestor was still spending time in backoff / retry state during the audit window. That is a supervisor behavior issue layered on top of stream quality, not a worker/GPU problem.

## Operational recommendation

Keep `wbap-am-820` and `klif-am-570` enabled. Pause `ktsa-550` to stop wasting ingest cycles on a corrupt stream, then re-test or rotate it before re-enabling.

