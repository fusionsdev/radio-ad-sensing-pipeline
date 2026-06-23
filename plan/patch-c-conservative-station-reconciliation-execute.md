# Patch C Execute - Conservative Station Reconciliation

Date: 2026-06-23

Goal: make live DB station enablement and `config/stations.yaml` agree before any ingestor restart.

No ingestor restart, worker scaling, station add, database setting change, or classifier change was performed.

## Backup

Live DB backup:

`H:\DEV\projects\radio-ad-sensing-pipeline\backups\pipeline-pre-station-reconcile-25690623-055154.db`

Backup size:

`151191552` bytes

Previous enabled station snapshot:

`H:\DEV\projects\radio-ad-sensing-pipeline\backups\stations-enabled-pre-reconcile-25690623-055154.json`

Station pool snapshot before applying the live control-layer guard:

`H:\DEV\projects\radio-ad-sensing-pipeline\backups\station-pool-pre-reconcile-guard-25690623-055748.json`

## Previous DB Enabled Set

```text
kabc-am-790
kfi-am-640
klbj-am-590
klif-am-570
knth-1070
ktrh-am-740
wbap-am-820
wfla-970
wlw-700
wsb-am-750
```

## Intended Temporary Harvest Set

```text
klif-am-570
wbap-am-820
```

## Actions Performed

1. Backed up live DB from `worker:/app/data/pipeline.db`.
2. Saved current DB enabled station snapshot.
3. Updated live DB `stations.enabled` flags so only `klif-am-570` and `wbap-am-820` are enabled.
4. Updated `config/stations.yaml` so restart will not re-enable paused stations.
5. Observed live drift from the existing ingestor/watchdog control layer:
   - `watchdog` auto-promoted backup stations while active count was below its target.
   - running ingestor station threads with old in-memory config could write their station back to enabled during in-flight chunks.
6. Applied a conservative live DB guard:
   - set `station_pool.replacement_eligible = 0` for all rows to stop auto-promotion during this temporary harvest.
   - queued `disable_station` commands for non-intended station threads.
   - re-applied `stations.enabled` after disable commands completed to close the in-flight race.
7. Confirmed DB enabled set equals config enabled set after two control/watchdog poll windows.
8. Did not restart or recreate `ingestor`.

## Config Changes

Set these stations to `enabled: false` in `config/stations.yaml`:

```text
ktrh-am-740
woai-am-1200
whbo-1040
wsb-am-750
wtam-am-1100
wibc-fm-931
wwtn-fm-997
```

Kept these stations enabled:

```text
klif-am-570
wbap-am-820
```

## New DB Enabled Set

```text
klif-am-570
wbap-am-820
```

## Config Enabled Set

```text
klif-am-570
wbap-am-820
```

## DB/Config Diff After Reconciliation

```text
config_enabled_minus_db_enabled: []
db_enabled_minus_config_enabled: []
```

Result: DB enabled station set and config enabled station set match.

## Control-Layer Guard

`station_pool.replacement_eligible` was set to `0` for all live DB rows. This was required because the running watchdog was auto-promoting backup stations back into the harvest after the first DB enablement update.

```text
station_pool replacement_eligible count: 0
```

Disable commands queued for non-intended stations:

```text
command ids: 122-136
done: 9
failed: 6
```

The failed disable commands were for stations that were not running in the ingestor process at the time of command processing. They did not re-enable those stations.

Final pending/processing station control commands:

```text
[]
```

## KTSA Confirmation

`ktsa-550` remains disabled in the live DB.

```text
ktsa-550 enabled: 0
```

## Runtime Guardrail

No container restart or worker scaling command was run.

Current observed services:

```text
ingestor: up, existing container unchanged
worker: two existing healthy replicas, unchanged
```

Important guardrail: do not recreate `watchdog` before adding an explicit config-level pool policy. Current code treats disabled config stations as replacement-eligible backups by default when watchdog starts and syncs `station_pool`.

## Validation Commands Run

Config enabled set via YAML parse:

```text
["klif-am-570", "wbap-am-820"]
```

Config enabled set via `shared.config.load_stations`:

```text
['klif-am-570', 'wbap-am-820']
```

Live DB enabled set:

```text
["klif-am-570", "wbap-am-820"]
```

Final live DB control state:

```text
ktsa_enabled: 0
station_pool_replacement_eligible_count: 0
pending_or_processing_commands: []
```

## Rollback Command

This restores the previous live DB enabled station set captured before reconciliation and restores the station pool eligibility snapshot saved before the live control-layer guard.

```powershell
$poolJson = Get-Content .\backups\station-pool-pre-reconcile-guard-25690623-055748.json -Raw
$rollbackScript = @'
import json
import sqlite3
import sys

pool_rows = json.loads(sys.stdin.read())
enabled = [
  "kabc-am-790",
  "kfi-am-640",
  "klbj-am-590",
  "klif-am-570",
  "knth-1070",
  "ktrh-am-740",
  "wbap-am-820",
  "wfla-970",
  "wlw-700",
  "wsb-am-750",
]
con = sqlite3.connect("/app/data/pipeline.db")
con.execute("BEGIN IMMEDIATE")
con.execute("UPDATE stations SET enabled = 0")
con.executemany("UPDATE stations SET enabled = 1 WHERE name = ?", [(s,) for s in enabled])
for row in pool_rows:
    con.execute(
        """
        UPDATE station_pool
        SET replacement_eligible = ?,
            priority = ?,
            market = ?,
            vertical = ?,
            needs_stream_resolution = ?,
            stream_validation_status = ?,
            updated_at = ?
        WHERE station_id = ?
        """,
        (
            row["replacement_eligible"],
            row["priority"],
            row["market"],
            row["vertical"],
            row["needs_stream_resolution"],
            row["stream_validation_status"],
            row["updated_at"],
            row["station_id"],
        ),
    )
con.commit()
'@
$poolJson | docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml exec -T worker python -c $rollbackScript
```

Note: this restores DB enablement and the live station pool DB snapshot only. To make rollback restart-safe, also revert the `config/stations.yaml` enablement changes before restarting `ingestor`. To restore stopped station threads without an ingestor restart, enqueue `promote_station` commands for the restored stations.

## Next Command To Restart/Recreate Ingestor

Do not run until operator approval.

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d --no-deps --force-recreate ingestor
```

Do not recreate `watchdog` with this command.
