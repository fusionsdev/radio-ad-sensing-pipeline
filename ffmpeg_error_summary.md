# FFmpeg Error Summary

Audit window: 10 minutes per station, using the same reconnect flags and 90s chunk loop as the ingestor, with stderr captured to `reports/station-ingest-audit-25690623-044835/`.

| Station | Attempts | Successes | stderr bytes | Reconnects | HTTP errors | Decode errors | Timeout errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| wbap-am-820 | 19 | 19 | 106217 | 0 | 0 | 0 | 0 |
| klif-am-570 | 19 | 19 | 107983 | 0 | 0 | 0 | 0 |
| ktsa-550 | 64 | 0 | 99330 | 0 | 0 | 126 | 0 |

## Key findings

- `wbap-am-820`: clean run, no ffmpeg errors.
- `klif-am-570`: clean run, no ffmpeg errors.
- `ktsa-550`: repeated AAC decode failures throughout the run; no reconnect or HTTP errors, which points to malformed/unstable stream payload rather than transport flakiness.

## Representative ktsa stderr pattern

- AAC decoder repeatedly reported buffer exhaustion and invalid input packets while trying to decode the stream.
- No HTTP 4xx/5xx or reconnect storms were observed on this probe.

## Conclusion

The ffmpeg error surface is dominated by `ktsa-550`. `klif-am-570` and `wbap-am-820` did not show transport or decode faults in this window.

