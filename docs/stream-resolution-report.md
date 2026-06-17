# Stream Resolution Report — First Five Stations

**Scope:** WSCR, KMVK, KBXX, WHTA, and WXYT only  
**Validation date:** 2026-06-11  
**Validation artifacts:** `data/stream_validation_results.json`, `data/stream_validation_results.csv`

## Executive Summary

| Metric | Count |
|---|---:|
| Stations checked | 5 |
| PASS | 0 |
| REDIRECT | 1 |
| HEADER_REQUIRED | 0 |
| TOKENIZED | 0 |
| FAIL | 4 |
| UNKNOWN | 0 |
| Still need manual stream resolution | 4 |

Only WSCR produced a usable ffmpeg result on this pass, and it did so via a redirecting AmperWave manifest.

The browser resolver found one public media candidate for each of the five stations from public browser-accessible pages.

The header-aware ffmpeg retry did not change the outcome for the unresolved four:

- KMVK surfaced a public AmperWave direct URL from radio.net, but ffmpeg returned HTTP 503 before and after headers.
- KBXX surfaced a public StreamTheWorld redirect from radio.net, but ffmpeg returned HTTP 403 before and after headers.
- WHTA surfaced a public StreamTheWorld redirect from radio.net, but ffmpeg returned HTTP 403 before and after headers.
- WXYT surfaced a public AmperWave manifest from radio.net, but ffmpeg returned HTTP 503.

## Validation Table

| Priority | Station | Call Sign | Market | Format | Public Source | Direct Stream URL | Stream Type | Browser Candidates | Pre-headers | Post-headers | ffmpeg Status | Stability | Use Now? | Notes |
|---|---|---|---|---|---|---|---|---:|---|---|---|---|---|---|
| 1 | 104.3 The Score | WSCR | Chicago, IL | Sports | `https://live.amperwave.net/manifest/audacy-wscramaac-hlsc.m3u8` | `https://live.amperwave.net/manifest/audacy-wscramaac-hlsc.m3u8` | `m3u8` | 1 | `REDIRECT` | `REDIRECT` | `REDIRECT` | `redirect` | Yes | ffmpeg followed the manifest to a signed AmperWave origin URL and played audio for 10s. Treat as usable, but keep an eye on redirect behavior. |
| 2 | La Grande 107.5 FM | KMVK-FM | Dallas-Fort Worth, TX | Spanish Regional Mexican | `radio.net` | `https://live.amperwave.net/direct/audacy-kmvkfmaac-imc?source=tritonredirect` | `direct` | 1 | `FAIL` | `FAIL` | `FAIL` | `unknown` | No | radio.net exposed a public AmperWave direct URL, but ffmpeg returned HTTP 503 before and after header-style retries. |
| 3 | 97.9 The Box | KBXX-FM | Houston, TX | Urban / Hip-Hop | `radio.net` | `https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac` | `redirect` | 1 | `FAIL` | `FAIL` | `FAIL` | `unknown` | No | radio.net exposed a public StreamTheWorld redirect, but ffmpeg returned HTTP 403 even with browser-style headers. |
| 4 | Hot 107.9 | WHTA-FM | Atlanta, GA | Urban / Hip-Hop | `radio.net` | `https://playerservices.streamtheworld.com/api/livestream-redirect/WHTAFM.mp3` | `redirect` | 1 | `FAIL` | `FAIL` | `FAIL` | `unknown` | No | radio.net exposed a public StreamTheWorld redirect, but ffmpeg returned HTTP 403 even with browser-style headers. |
| 5 | 97.1 The Ticket | WXYT-FM | Detroit, MI | Sports | `radio.net` | `https://live.amperwave.net/manifest/audacy-wxytfmaac-hlsc.m3u8` | `m3u8` | 1 | `FAIL` | `FAIL` | `FAIL` | `unknown` | No | radio.net exposed a public AmperWave manifest, but ffmpeg returned HTTP 503 on repeated attempts. |

## Patch Decision

Included in the patch:

- `WSCR` because it validated with `REDIRECT` and can be used directly.
- `KBXX`, `WHTA`, `WXYT`, and `KMVK` because each now has a concrete public candidate URL and a recorded ffmpeg failure for evidence.

Not included in the patch:

- None.

## Operational Notes

- The validation was intentionally limited to the first five stations only.
- No attempt was made to expand into the full batch.
- The stream validation helper writes machine-readable results to `data/stream_validation_results.json` and `data/stream_validation_results.csv`.
- WSCR is the only station from this pass that is ready to use now.
