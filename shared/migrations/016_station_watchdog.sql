CREATE TABLE IF NOT EXISTS station_health (
    station_id TEXT PRIMARY KEY,
    health_state TEXT NOT NULL DEFAULT 'unknown',
    enabled INTEGER DEFAULT 0,
    last_chunk_at TEXT,
    last_success_at TEXT,
    last_failure_at TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    restart_count_today INTEGER DEFAULT 0,
    promoted_at TEXT,
    disabled_at TEXT,
    cool_down_until TEXT,
    active_slot INTEGER,
    last_error TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_station_health_state ON station_health(health_state);

CREATE TABLE IF NOT EXISTS station_recovery_events (
    id INTEGER PRIMARY KEY,
    station_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_state TEXT,
    new_state TEXT,
    reason TEXT,
    action_taken TEXT,
    replacement_station_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_station_recovery_events_station
    ON station_recovery_events(station_id, created_at DESC);
