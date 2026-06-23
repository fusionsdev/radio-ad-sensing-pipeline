# Next 48h Loan Station Batch

**Generated**: 2026-06-21 05:43
**Tool**: Strict loan classifier (v2, phrase-level, exclusion-aware)

## Batch Summary

| Action | Count | Stations |
|---|---:|---|
| ✅ Keep | 4 | ktrh-am-740, klif-am-570, wsb-am-750, wbap-am-820 |
| 🆕 Add | 3 | klbj-am-590, wgul-860, kabc-am-790 |
| ⏸️ Pause | 5 | woai-am-1200, wwtn-fm-997, whbo-1040, wtam-am-1100, wibc-fm-931 |

**Total active**: 7 stations for 48h

## Station Batch

| Action | Callsign | State | Market | Format | Stream URL | Reason |
|:---|:---|:---|:---|---:|:---|:---|
| ✅ keep | ktrh-am-740 | TX | Houston | Talk | `http://stream.revma.ihrhls.com/zc2285` | 10 loan ads, 6 unique advertisers. Stream verified (iHeart). |
| ✅ keep | klif-am-570 | TX | Dallas | Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3` | 12 loan ads, 9 unique advertisers. Stream verified (StreamTheWorld). |
| ✅ keep | wsb-am-750 | GA | Atlanta | News/Talk | `http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3` | 15 loan ads, 6 unique advertisers. Stream verified (StreamGuys). |
| ✅ keep | wbap-am-820 | TX | Dallas–Fort Worth | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3` | 13 loan ads, 8 unique advertisers. Stream verified (StreamTheWorld). |
| 🆕 add | klbj-am-590 | TX | Austin | News/Talk | `http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls` | Austin market gap. Stream had 403 on 2026-06-10. Needs re-test. Enabled=false. |
| 🆕 add | wgul-860 | FL | Tampa | News/Talk | `http://208.80.52.107/WGULAM_SC` | Tampa has WHBO only. Stream had 403 on 2026-06-10. Needs re-test. Enabled=false. |
| 🆕 add | kabc-am-790 | CA | Los Angeles | Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3` | 2 loan ads, 2 unique. Weak signal but LA is major market. Enable and re-test. |
| ⏸️ pause | woai-am-1200 | TX | San Antonio | Talk | `http://stream.revma.ihrhls.com/zc2361` | Rotated out. Only 3 loan ads — too weak for batch slot. Replace with KLBJ (Austin). |
| ⏸️ pause | wwtn-fm-997 | TN | Nashville | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/WWTNFM.mp3` | Rotated out. Only 1 unique loan advertiser. Replace with WGUL (Tampa). |
| ⏸️ pause | whbo-1040 | FL | Tampa | Talk | `https://ice41.securenetsystems.net/WHBO` | Rotated out. Only 2 loan ads across 485 detections. Replace with KABC (LA). |
| ⏸️ pause | wtam-am-1100 | OH | Cleveland | Talk | `http://stream.revma.ihrhls.com/zc1757` | Confirmed rotate out. 0 loan ads in 50 detections. |
| ⏸️ pause | wibc-fm-931 | IN | Indianapolis | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/WIBCFM.mp3` | Rotated out. 5 loan ads is borderline, freeing slot for new market test. |

## Coverage Map

| Region | Stations | Markets Covered |
|---|---:|---|
| **Texas** | KTRH, KLIF, WBAP, KLBJ | Houston, Dallas, Austin |
| **Southeast** | WSB, WGUL | Atlanta, Tampa |
| **West Coast** | KABC | Los Angeles |

## Risks

1. **KLBJ (Austin)**: Stream had 403 error on 2026-06-10. `Enabled=false`. Must re-test before batch starts.
2. **WGUL (Tampa)**: Stream had 403 error on 2026-06-10. `Enabled=false`. Must re-test before batch starts.
3. **KABC (Los Angeles)**: Stream had `empty_chunk` loop on 2026-06-10. `Enabled=false`. Must re-test.
4. **WLW, KNTH, KTSA, WFLA**: Not in station config. Cannot add without stream discovery first.

## Success Criteria (after 48h)

| Criteria | Threshold | Action |
|---|---|---|
| 2+ unique loan advertisers | Pass | Keep in batch |
| 1 named loan advertiser | Marginal | Watch — 48h more |
| 0 loan advertisers | Fail | Rotate out |
| Mostly debt/tax/insurance | Fail | Rotate out |
| Classifier precision < 70% | Audit | Fix classifier before keeping |
