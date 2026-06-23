# Station Stream Re-Test Results

**Generated**: 2026-06-21

## Method

Each URL was tested with `ffprobe -v error -show_entries format=format_name` on the Windows host. A valid format name (aac, mp3, hls) means the stream is reachable and producing audio.

## Results

| Station | Callsign | Market | Test URL | Format | Status |
|---|---|---|---|---|---|
| **KEEP** | | | | | |
| KTRH | ktrh-am-740 | Houston, TX | `http://stream.revma.ihrhls.com/zc2285` | aac | ✅ Pass |
| KLIF | klif-am-570 | Dallas, TX | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3` | mp3 | ✅ Pass |
| WSB | wsb-am-750 | Atlanta, GA | `http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3` | mp3 | ✅ Pass |
| WBAP | wbap-am-820 | Dallas–Fort Worth, TX | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3` | mp3 | ✅ Pass |
| **ADD** | | | | | |
| KLBJ | klbj-am-590 | Austin, TX | `http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls` | lrc/pls | ✅ Pass (PLS resolves) |
| WLW | wlw-700 | Cincinnati, OH | `https://stream.revma.ihrhls.com/zc1713` | aac | ✅ Pass (iHeart) |
| KNTH | knth-1070 | Houston, TX | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNTHAM.mp3` | mp3 | ✅ Pass (Salem/StreamTheWorld) |
| KTSA | ktsa-550 | San Antonio, TX | `http://live.amperwave.net/direct/alphacorporate-ktsaamaac-imc3?source=iheart` | aac | ✅ Pass (AmperWave) |
| WFLA | wfla-970 | Tampa, FL | `https://stream.revma.ihrhls.com/zc2823` | aac | ✅ Pass (iHeart) |
| KABC | kabc-am-790 | Los Angeles, CA | `http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3` | mp3 | ✅ Pass (fallback) |
| **FAILED** | | | | | |
| WGUL | wgul-860 | Tampa, FL | `http://208.80.52.107/WGULAM_SC` | — | ❌ 403 Forbidden |

## Notes

- **WGUL (Tampa)** is dead (403). Since both WFLA and WGUL are in Tampa, WFLA replaces WGUL.
- **KLBJ (Austin)** previously showed 403 in old config; PLS now resolves successfully from this host.
- **KABC (Los Angeles)** previously had `empty_chunk` loop in Docker; raw StreamTheWorld URL returns MP3 on host test. May still need Docker-side verification.
- **All 10 proposed stations pass stream test** (using KABC as fallback for failed WGUL).
