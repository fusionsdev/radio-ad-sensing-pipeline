CREATE TABLE IF NOT EXISTS station_control_commands (
    id INTEGER PRIMARY KEY,
    station_id TEXT NOT NULL,
    command TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_station_control_commands_pending
    ON station_control_commands(status, created_at);
