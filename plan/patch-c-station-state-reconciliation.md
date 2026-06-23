# Patch C Station State Reconciliation

Date: 2026-06-23

Scope: compare `config/stations.yaml`, live Docker DB station state, and recent ingest activity before any ingestor restart or recreation.

No ingestor restart, worker scaling, station add, database setting change, or station enablement mutation was performed for this reconciliation.

## Decision

No-go for ingestor restart yet.

The enabled station set in config and the enabled station set in the live DB do not agree. Restarting or recreating the ingestor before reconciliation could unexpectedly enable config-only stations or preserve DB-promoted stations that are not intended for the next harvest.

## Sources

- Config: `config/stations.yaml`
- Live DB: `/app/data/pipeline.db` queried inside the Docker `worker` service
- Recent activity windows: 10 minutes, 30 minutes, and 60 minutes

No `profile` or `group` fields were found in `config/stations.yaml`.

## Enabled Set Diff

Config enabled:

`klif-am-570`, `ktrh-am-740`, `wbap-am-820`, `whbo-1040`, `wibc-fm-931`, `woai-am-1200`, `wsb-am-750`, `wtam-am-1100`, `wwtn-fm-997`

DB enabled:

`kabc-am-790`, `kfi-am-640`, `klbj-am-590`, `klif-am-570`, `knth-1070`, `ktrh-am-740`, `wbap-am-820`, `wfla-970`, `wlw-700`, `wsb-am-750`

Known bad stream:

`ktsa-550` is disabled in the DB and should remain disabled.

## Reconciliation Table

| station_id | config_enabled | db_enabled | config_url | db_url | chunks_60m | gaps_60m | recommendation |
|---|---:|---:|---|---|---:|---:|---|
| kabc-am-790 | 0 | 1 | `http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3` | 0 | 6 | disable_in_db |
| kfi-am-640 | 0 | 1 | `http://stream.revma.ihrhls.com/zc177` | `http://stream.revma.ihrhls.com/zc177` | 0 | 2 | disable_in_db |
| klbj-am-590 | 0 | 1 | `http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls` | `http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls` | 0 | 2 | disable_in_db |
| klbj-am-590-legacy | 0 | 0 | `http://playerservices.streamtheworld.com/pls/KLBJAM.pls` | `http://playerservices.streamtheworld.com/pls/KLBJAM.pls` | 0 | 0 | no_change_disabled |
| klif-am-570 | 1 | 1 | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3` | 10 | 8 | keep_enabled + investigate_stream |
| klif-am-570-aac | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAMAAC_SC` | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAMAAC_SC` | 0 | 0 | no_change_disabled |
| knth-1070 | missing | 1 | missing | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNTHAM.mp3` | 0 | 4 | remove_from_current_harvest |
| knx-news-1070 | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNXAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNXAM.mp3` | 0 | 0 | no_change_disabled |
| knx-news-1070-aac | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNXAM_SC` | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNXAM_SC` | 0 | 0 | no_change_disabled |
| ktrh-am-740 | 1 | 1 | `http://stream.revma.ihrhls.com/zc2285` | `http://stream.revma.ihrhls.com/zc2285` | 0 | 4 | investigate_stream |
| ktsa-550 | missing | 0 | missing | `http://live.amperwave.net/direct/alphacorporate-ktsaamaac-imc3?source=iheart` | 0 | 18 | keep disabled |
| wbap-am-820 | 1 | 1 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3` | 9 | 8 | keep_enabled + investigate_stream |
| wbap-am-820-aac | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM_SC` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM_SC` | 0 | 0 | no_change_disabled |
| wbbm-am-780 | 0 | 0 | `http://16843.live.streamtheworld.com/WBBMAM_SC` | `http://16843.live.streamtheworld.com/WBBMAM_SC` | 0 | 0 | no_change_disabled |
| wbt-am-1110 | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBTAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBTAM.mp3` | 0 | 0 | no_change_disabled |
| wfla-970 | missing | 1 | missing | `https://stream.revma.ihrhls.com/zc2823` | 0 | 4 | remove_from_current_harvest |
| wgn-am-720 | 0 | 0 | `http://provisioning.streamtheworld.com/pls/WGNPLUSAM.pls` | `http://provisioning.streamtheworld.com/pls/WGNPLUSAM.pls` | 0 | 0 | no_change_disabled |
| wgul-860 | 0 | 0 | `http://208.80.52.107/WGULAM_SC` | `http://208.80.52.107/WGULAM_SC` | 0 | 0 | no_change_disabled |
| whbo-1040 | 1 | 0 | `https://ice41.securenetsystems.net/WHBO` | `https://ice41.securenetsystems.net/WHBO` | 0 | 0 | remove_from_current_harvest; set config disabled before restart |
| whbo-1040-legacy | 0 | 0 | `http://1.ice1.firststreaming.com/whbo_am.mp3` | `http://1.ice1.firststreaming.com/whbo_am.mp3` | 0 | 0 | no_change_disabled |
| wibc-fm-931 | 1 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WIBCFM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WIBCFM.mp3` | 0 | 0 | remove_from_current_harvest; set config disabled before restart |
| wjr-am-760 | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WJRAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WJRAM.mp3` | 0 | 0 | no_change_disabled |
| wlrn-913 | 0 | 0 | `http://stream.wlrn.mobi/WLRNFMMP3` | `http://stream.wlrn.mobi/WLRNFMMP3` | 0 | 0 | no_change_disabled |
| wlw-700 | missing | 1 | missing | `https://stream.revma.ihrhls.com/zc1713` | 0 | 4 | remove_from_current_harvest |
| woai-am-1200 | 1 | 0 | `http://stream.revma.ihrhls.com/zc2361` | `http://stream.revma.ihrhls.com/zc2361` | 0 | 0 | remove_from_current_harvest; set config disabled before restart |
| wsb-am-750 | 1 | 1 | `http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3` | `http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3` | 0 | 4 | investigate_stream |
| wtam-am-1100 | 1 | 0 | `http://stream.revma.ihrhls.com/zc1757` | `http://stream.revma.ihrhls.com/zc1757` | 0 | 0 | remove_from_current_harvest; set config disabled before restart |
| wwj-am-950 | 0 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WWJAM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WWJAM.mp3` | 0 | 0 | no_change_disabled |
| wwtn-fm-997 | 1 | 0 | `http://playerservices.streamtheworld.com/api/livestream-redirect/WWTNFM.mp3` | `http://playerservices.streamtheworld.com/api/livestream-redirect/WWTNFM.mp3` | 0 | 0 | remove_from_current_harvest; set config disabled before restart |

## Recent Activity Detail

| station_id | chunks 10m/30m/60m | gaps 10m/30m/60m | empty_60m | stream_down_60m | dropped_backlog_60m |
|---|---:|---:|---:|---:|---:|
| klif-am-570 | 6 / 8 / 10 | 0 / 3 / 8 | 8 | 0 | 0 |
| wbap-am-820 | 4 / 6 / 9 | 0 / 3 / 8 | 8 | 0 | 0 |
| ktrh-am-740 | 0 / 0 / 0 | 0 / 1 / 4 | 4 | 0 | 0 |
| wsb-am-750 | 0 / 0 / 0 | 0 / 1 / 4 | 4 | 0 | 0 |
| ktsa-550 | 0 / 0 / 0 | 0 / 1 / 18 | 18 | 0 | 0 |
| kabc-am-790 | 0 / 0 / 0 | 0 / 2 / 6 | 5 | 1 | 0 |
| kfi-am-640 | 0 / 0 / 0 | 0 / 2 / 2 | 2 | 0 | 0 |
| klbj-am-590 | 0 / 0 / 0 | 0 / 1 / 2 | 0 | 2 | 0 |
| knth-1070 | 0 / 0 / 0 | 0 / 2 / 4 | 4 | 0 | 0 |
| wfla-970 | 0 / 0 / 0 | 0 / 1 / 4 | 4 | 0 | 0 |
| wlw-700 | 0 / 0 / 0 | 0 / 1 / 4 | 4 | 0 | 0 |

## Health And Status Notes

| station_id | DB health/status | last_gap_reason | note |
|---|---|---|---|
| klif-am-570 | healthy | empty_chunk | Producing chunks, but empty gaps still present. |
| wbap-am-820 | healthy | empty_chunk | Producing chunks, but empty gaps still present. |
| ktrh-am-740 | stale | empty_chunk | Config and DB both enabled, but no chunks in the last 60 minutes. |
| wsb-am-750 | stale | empty_chunk | Config and DB both enabled, but no chunks in the last 60 minutes. |
| ktsa-550 | disabled | empty_chunk | Known bad stream. Must remain disabled. |
| kabc-am-790 | stale | empty_chunk | DB enabled while config disabled. |
| kfi-am-640 | stale | empty_chunk | DB enabled while config disabled. |
| klbj-am-590 | stale | stream_down | DB enabled while config disabled. |
| knth-1070 | stale | empty_chunk | DB enabled and missing from config. |
| wfla-970 | stale | empty_chunk | DB enabled and missing from config. |
| wlw-700 | stale | empty_chunk | DB enabled and missing from config. |

Recent `dropped_backlog` count was zero for the stations above. Recent gap pressure is dominated by `empty_chunk` and some `stream_down`, not backlog overflow.

## Recommended Pre-Restart State

Keep enabled:

- `klif-am-570`
- `wbap-am-820`

Investigate before keeping enabled:

- `ktrh-am-740`
- `wsb-am-750`

Disable in DB or remove from current harvest before restart:

- `kabc-am-790`
- `kfi-am-640`
- `klbj-am-590`
- `knth-1070`
- `wfla-970`
- `wlw-700`

Keep disabled:

- `ktsa-550`

Set config disabled before restart unless intentionally reactivating:

- `whbo-1040`
- `wibc-fm-931`
- `woai-am-1200`
- `wtam-am-1100`
- `wwtn-fm-997`

## Success Criteria Before Ingestor Restart

- DB enabled station set matches the intended config set.
- All DB-promoted stations are represented in config or intentionally disabled.
- `ktsa-550` remains disabled.
- No config-only station is accidentally re-enabled by restart.
- No surprise station enablement appears after restart.
- Rollback command is documented and tested against the intended pre-change snapshot.

## Rollback Command

If DB enablement is changed in the next step, this command restores the current DB-enabled snapshot from this reconciliation:

```powershell
@'
import sqlite3
enabled = [
  "kabc-am-790", "kfi-am-640", "klbj-am-590", "klif-am-570",
  "knth-1070", "ktrh-am-740", "wbap-am-820", "wfla-970",
  "wlw-700", "wsb-am-750",
]
con = sqlite3.connect("/app/data/pipeline.db")
con.execute("UPDATE stations SET enabled = 0")
con.executemany("UPDATE stations SET enabled = 1 WHERE name = ?", [(s,) for s in enabled])
con.commit()
'@ | docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml exec -T worker python -
```

