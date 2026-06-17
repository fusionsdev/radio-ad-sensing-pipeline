CREATE TABLE IF NOT EXISTS station_pool (
    station_id TEXT PRIMARY KEY,
    replacement_eligible INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 100,
    market TEXT,
    vertical TEXT,
    needs_stream_resolution INTEGER NOT NULL DEFAULT 0,
    stream_validation_status TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_station_pool_eligible
    ON station_pool(replacement_eligible, priority);
