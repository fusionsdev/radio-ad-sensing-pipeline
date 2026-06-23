# Loan-Heavy Station Expansion Recommendation

Generated: 2026-06-20 (probe-verified, ffmpeg 6s capture inside radio-ingestor container)

## Context

Current 9-station mix (KLIF, WBAP, KTRH, WOAI, WHBO, WSB, WTAM, WIBC, WWTN) produces
insurance / auto / real-estate / mattress / home-service ads, not consumer-loan ads.
Broad scan of 2,000 recent transcripts: `payday=0 installment=0 direct deposit=0`.
Drop rate is 71% (36k dropped / 51k total) — **do not just add stations; swap.**

## Verified-reachable candidates (probed this session)

| Priority | Station | State | Lending law | URL | Format | Probe |
|----------|---------|-------|-------------|-----|--------|-------|
| ★★★ | KCMO 710 AM — Kansas City, MO | MO | **No rate cap** (most permissive) | `http://playerservices.streamtheworld.com/api/livestream-redirect/KCMOAM.mp3` | mp3 | ✅ 3.2s |
| ★★★ | WLW 700 AM — Cincinnati, OH | OH | Permissive (installment) | `http://16843.live.streamtheworld.com/WLWAM_SC` | aac | ✅ 3.9s |
| ★★☆ | WWBA 1040 AM — Tampa, FL | FL | Permissive (payday) | `https://ice41.securenetsystems.net/WWBA` | aac | ✅ 3.1s |
| ★★☆ | KFI 640 AM — Los Angeles, CA | CA | Permissive (large market) | `http://stream.revma.ihrhls.com/zc177` | aac | ✅ 2.7s (re-enable) |
| ★☆☆ | WLS 890 AM — Chicago, IL | IL | Restricted | `http://playerservices.streamtheworld.com/api/livestream-redirect/WLSAM.mp3` | mp3 | ✅ 7.2s |
| ★☆☆ | WABC 770 AM — New York, NY | NY | **Payday banned** | `http://playerservices.streamtheworld.com/api/livestream-redirect/WABCAM.mp3` | mp3 | ✅ 2.9s |

## Recommended swap plan (keep total ≤ 10)

**Add (Tier 1 — loan-heavy):**
1. `kcmo-am-710` — Kansas City, MO (MO has no payday rate cap; highest loan-ad density)
2. `wlw-am-700` — Cincinnati, OH (OH installment-loan market; 50kW tri-state reach)
3. `wwba-am-1040` — Tampa, FL (FL permissive; pairs with existing WHBO Tampa)

**Re-enable:**
4. `kfi-am-640` — Los Angeles, CA (was disabled for empty_chunk; now reachable)

**Swap out (low loan yield, keep queue manageable):**
- Disable 2-3 current stations with lowest detection density to make room.
  Check per-station health via `references/db-schema.md` per-station query.
  Candidates to drop: lowest-yield daytime political-talk stations.

**Skip for now:** WLS (IL restricted), WABC (NY payday banned) — won't add loan yield.

## Probed but NOT reachable (404 / 403 — do not add)

WLAC Nashville (404), WSPD Toledo (404), WOKV Jacksonville (404), WRVA Richmond (404),
KOA Denver (404), WHO Des Moines (404), WSCR Chicago sports (404), WQAM Miami (404),
KFNS St. Louis (404), WJR Detroit (403), WHIO Dayton (404).

These iHeart stations migrated off the StreamTheWorld `.mp3` redirect. They likely
use `stream.revma.ihrhls.com/zcXXXX` (non-guessable IDs) — would need manual lookup
on each station's iHeart page to extract the real stream ID.
