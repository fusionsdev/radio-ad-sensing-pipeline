# Final 48h Loan Station Batch

**Generated**: 2026-06-21
**Tool**: Strict loan classifier (v2) + ffprobe stream verification

## Batch Summary

| Action | Count | Stations |
|---|---|---|
| ✅ Keep | 4 | KTRH, KLIF, WSB, WBAP |
| 🆕 Add | 6 | KLBJ, WLW, KNTH, KTSA, WFLA, KABC |
| ⏸️ Pause | 6 | WOAI, WWTN, WHBO, WTAM, WIBC |
| ❌ Failed | 1 | WGUL (403 Forbidden — replaced by WFLA) |

**Total active**: 10 stations for 48h

## Station Batch

| Action | Callsign | State | Market | Format | Stream URL | Reason |
|---|---|---|---|---|---|---|
| ✅ keep | KTRH | TX | Houston | Talk | `http://stream.revma.ihrhls.com/zc2285` | 10 loan ads, 6 unique advertisers. Proven iHeart stream. |
| ✅ keep | KLIF | TX | Dallas | Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3` | 12 loan ads, 9 unique advertisers. Proven StreamTheWorld. |
| ✅ keep | WSB | GA | Atlanta | News/Talk | `http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3` | 15 loan ads, 6 unique advertisers. Proven StreamGuys. |
| ✅ keep | WBAP | TX | Dallas–Fort Worth | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3` | 13 loan ads, 8 unique advertisers. Proven StreamTheWorld. |
| 🆕 add | KLBJ | TX | Austin | News/Talk | `http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls` | Austin market gap. PLS resolves now (was 403 previously). |
| 🆕 add | WLW | OH | Cincinnati | News/Talk | `https://stream.revma.ihrhls.com/zc1713` | New market (Ohio). iHeart stream verified AAC. |
| 🆕 add | KNTH | TX | Houston | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNTHAM.mp3` | 2nd Houston station. Salem Media/StreamTheWorld MP3. |
| 🆕 add | KTSA | TX | San Antonio | News/Talk | `http://live.amperwave.net/direct/alphacorporate-ktsaamaac-imc3?source=iheart` | Replaces WOAI in San Antonio. AmperWave AAC. |
| 🆕 add | WFLA | FL | Tampa | News/Talk | `https://stream.revma.ihrhls.com/zc2823` | Replaces WGUL. iHeart AAC verified. |
| 🆕 add | KABC | CA | Los Angeles | Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3` | LA market. StreamTheWorld MP3. May need Docker re-test. |

## Coverage Map

| Region | Stations | Markets Covered |
|---|---|---|
| **Texas (5)** | KTRH, KLIF, WBAP, KLBJ, KTSA, KNTH | Houston, Dallas, Austin, San Antonio |
| **Southeast (2)** | WSB, WFLA | Atlanta, Tampa |
| **Midwest (1)** | WLW | Cincinnati |
| **West Coast (1)** | KABC | Los Angeles |

## Paused Stations

| Station | Market | Reason |
|---|---|---|
| WOAI | San Antonio, TX | Replaced by KTSA (same market, new opportunity) |
| WWTN | Nashville, TN | Only 1 unique loan advertiser |
| WHBO | Tampa, FL | Replaced by WFLA (bigger Tampa station) |
| WIBC | Indianapolis, IN | 5 loan ads — borderline, freeing slot |
| WTAM | Cleveland, OH | 0 loan ads after 50 detections |

## Success Criteria (48h)

| Criteria | Threshold | Action |
|---|---|---|
| 2+ unique loan advertisers | ✅ Pass | Keep in batch |
| 1 named loan advertiser | ⚠️ Marginal | Watch — 48h more |
| 0 loan advertisers | ❌ Fail | Rotate out |
| Mostly debt/tax/insurance | ❌ Fail | Rotate out |
| Classifier precision < 70% | 🔧 Audit | Fix classifier before decision |
