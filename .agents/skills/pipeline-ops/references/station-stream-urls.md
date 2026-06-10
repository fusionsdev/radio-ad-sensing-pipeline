# Discovering direct stream URLs for new radio stations

When `config/stations.yaml` needs a new station or a current station's URL
goes dead, walk the discovery ladder below **in order** — each layer is faster
and more stable than the next, and most US talk/news/sports stations hit
Layer 1 or 2.

Validation for every candidate URL:

```bash
ffmpeg -hide_banner -i "<URL>" -t 8 -f null -
```

Mark as: PASS (audio plays), TIMEOUT (still playing past 8s = PASS), REDIRECT
(works after 30x), TOKENIZED (works now but URL will expire), 5XX/404/403
(broken), UNKNOWN (couldn't test).

---

## Layer 1 — iHeart / Triton public HLS (works for all iHeart-owned stations)

**Pattern:** `https://stream.revma.ihrhls.com/zc<id>/hls.m3u8`

`<id>` is the trailing integer in the iHeart live page URL.

```
https://www.iheart.com/live/kfi-am-640-177/        → zc177
https://www.iheart.com/live/newsradio-610-wiod-569/ → zc569
https://www.iheart.com/live/wtam-1100/            → zc1749
```

Proven PASS list (verified 2026-06-11):

| Station | URL |
|---|---|
| KFI AM 640 | `https://stream.revma.ihrhls.com/zc177/hls.m3u8` |
| WIOD 610 AM | `https://stream.revma.ihrhls.com/zc569/hls.m3u8` |
| WTAM 1100 AM | `https://stream.revma.ihrhls.com/zc1749/hls.m3u8` |
| WTVN 610 AM | `https://stream.revma.ihrhls.com/zc1765/hls.m3u8` |
| WREC 600 AM | `https://stream.revma.ihrhls.com/zc2145/hls.m3u8` |
| KPRC AM 950 | `https://stream.revma.ihrhls.com/zc2277/hls.m3u8` |
| KTRH 740 AM | `https://stream.revma.ihrhls.com/zc2285/hls.m3u8` |
| WFLA 970 AM | `https://stream.revma.ihrhls.com/zc2823/hls.m3u8` |

**How to find `<id>` for a new iHeart station:**

1. Google: `"iheart.com/live" "<call sign>"`
2. If that fails: `https://streema.com/radios/<CALL>` or `radiostationusa.fm/online/<call>` and grep the HTML for `iheart.com/live/<slug>-<id>/`.
3. If those fail: visit the station's official site, look for the "Listen Live" link — iHeart station sites always redirect to `https://<call>.iheart.com` or `https://www.iheart.com/live/<slug>-<id>/`.

---

## Layer 2 — iHeart `live-meta` API reveals the real Audacy/AmperWave URL

After the June 2025 iHeart–Audacy distribution deal, **most Audacy-owned
stations also have an iHeart mirror page** (e.g. WBBM at
`iheart.com/live/wbbm-newsradio-10832`). The page UI may say "No activity
yet" but the underlying API still knows the real stream URL.

**Discovery endpoint:**

```
https://us.api.iheart.com/api/v3/live-meta/stream/<iheart_id>/station-meta
```

Set `User-Agent: Mozilla/5.0` and `Accept: application/json`. The response
contains the real `live.amperwave.net/direct/audacy-<callsign_lc>aac-imc`
URL inside a JSON field.

**Extract script (Python):**

```python
import urllib.request, re, json, subprocess
iheart_id = 10832  # WBBM
url = f"https://us.api.iheart.com/api/v3/live-meta/stream/{iheart_id}/station-meta"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
data = urllib.request.urlopen(req, timeout=8).read().decode()
m = re.findall(r'https?://live\.amperwave\.net/[\w./?=&%-]+', data)
# m[0] is usually the direct AAC URL; m[1] if present is the HLS playlist
for u in m[:3]:
    print(u)
```

**Got iHeart IDs for these Audacy mirrors** (verified 2026-06-11):

| iHeart id | Station | Real stream (from API) |
|---|---|---|
| 10827 | WXYT 97.1 The Ticket | `https://live.amperwave.net/direct/audacy-wxytfmaac-imc` |
| 10832 | WBBM Newsradio 780 | `https://live.amperwave.net/direct/audacy-wbbmamaac-imc` |
| 10835 | WSCR / 104.3 The Score | `https://live.amperwave.net/playlist/audacy-wscrfmaac-imc.m3u` |
| 10850 | WWJ Newsradio 950 | `https://live.amperwave.net/direct/audacy-wwjamaac-imc` |
| 10906 | KNX News 1070 | `https://live.amperwave.net/direct/audacy-knxamaac-imc` |

⚠️ **The `zc<id>/hls.m3u8` URL itself returns 404** for these — iHeart hosts
the metadata but **does not** proxy the AmperWave stream through the
`stream.revma.ihrhls.com` CDN. You must use the AmperWave URL from the
`station-meta` response.

⚠️ **AmperWave direct endpoints return HTTP 5XX** (rate-limit) when probed
from a server IP that hits them too fast. Mitigations: 8s sleep between
probes, use a single browser session to capture once, then reuse. Do **not**
hammer them from a cron.

---

## Layer 3 — Station-specific CDNs (use only when Layers 1+2 fail)

The owner determines the stack. Look at the Wikipedia "Owned by" line, then
match to the right mountpoint:

| Owner | CDN | URL pattern | Notes |
|---|---|---|---|
| **Cox Media Group** (WSB Atlanta, etc.) | StreamGuys via CMG | `https://cmg.streamguys1.com/<market><freq>/<market><freq>-encoder.aac/playlist.m3u` | Endpoints rotate. Open the station's listen page in a browser, watch DevTools → Network for `.m3u8`. |
| **Nexstar Media Group** (WGN Chicago, etc.) | AmperWave, **no `audacy-` prefix** | `https://live.amperwave.net/direct/<call_lc>am-<call_lc>ammp3-imc2` | WGN works: `https://live.amperwave.net/direct/wgnam-wgnammp3-imc2`. |
| **Audacy** (legacy, pre-2025) | StreamTheWorld | `https://playerservices.streamtheworld.com/api/livestream-redirect/<CALL>AM.mp3` | WBAP works at this exact URL. Most other Audacy stations **no longer** respond on STW — they've been moved to AmperWave (Layer 2). |
| **Cumulus Media** (WWTN Nashville, etc.) | Triton / iHeart mirror | varies | iHeart mirror pages are placeholders. Need to find the Cumulus iHeart agreement URL. |
| **Curtis Media Group** (WPTF Raleigh, etc.) | Triton embed | `https://player.listenlive.co/<id>` (Triton embed only) | No known direct URL. Use the embed. |

---

## Layer 4 — Last-resort: capture from a real browser

For stations where the listen page is JS-only and the direct URL isn't
exposed anywhere, use a headless browser to start playback and inspect
network requests:

```python
# Pseudocode
page.goto(station_listen_url)
page.click("Listen Live")
page.wait_for_timeout(2500)  # let the player boot
urls = page.evaluate("performance.getEntriesByType('resource')"
                     ".filter(e => /\\.m3u8|\\.aac|amper|streamtheworld|streamguys/.test(e.name))"
                     ".map(e => e.name)")
# urls contains the real CDN endpoint, often with auth query params
```

For Audacy stations, the `streamUrl` field also appears in the page's
Facebook Pixel tracking beacon as plain JSON — easy to grep.

**WBAP example** (caught this way, 2026-06-11):

```json
"streamUrl":"https://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3"
```

**WGN example:**

```json
"streamUrl":"https://live.amperwave.net/direct/wgnam-wgnammp3-imc2?source=Audacy"
```

The query string has auth but the path is reusable. Test without the
query string first.

---

## Adding a new station to `config/stations.yaml`

Once you have a verified PASS URL:

```yaml
- name: "WTAM 1100 AM"
  market: "Cleveland, OH"
  format: "News/Talk"
  stream_url: "https://stream.revma.ihrhls.com/zc1749/hls.m3u8"
  enabled: true
  notes: "iHeart/Triton. Verified PASS 2026-06-11."
```

Then restart the ingestor so the new station starts flowing:

```powershell
docker compose restart radio-ingestor
docker logs radio-ingestor --tail 30
```

Watch the worker's station-health query (see `db-schema.md`) — new stations
should appear in `chunks` within ~90s of ingestor boot.

---

## Quick decision tree

```
Need a new station URL
        │
        ├── Is it iHeart-owned? ─── yes ──→ Layer 1 (zc<id>/hls.m3u8)
        │
        ├── Is it on iHeart as a mirror? ── yes ──→ Layer 2 (live-meta API)
        │
        ├── Is it Cox / Nexstar / Cumulus? ──→ Layer 3 (owner-specific CDN)
        │
        └── All else ──→ Layer 4 (browser capture)
```

## Known fragile stations (2026-06-11)

These had working URLs that may have rotated; re-verify before use:

- **WSB 750/95.5** (Cox) — `cmg.streamguys1.com/atl750/atl750-encoder.aac/playlist.m3u` returned 404 on the second test.
- **KRLD-FM 105.3 The Fan** (Audacy) — needs browser warm-up; `live.amperwave.net` is rate-limited.
- **WBT 107.9 FM** (Charlotte, Urban One) — iHeart page is a placeholder.
- **WPTF 680** (Raleigh, Curtis Media) — no public direct URL; Triton embed only.
- **WWTN 99.7** (Nashville, Cumulus) — iHeart page is a placeholder; no known direct URL.
- **WIBC 93.1** (Indianapolis, iHeart) — zc6057 returns 404; may have rotated.
