CREATE TABLE IF NOT EXISTS station_daily (
    station_id INTEGER NOT NULL REFERENCES stations(id),
    date TEXT NOT NULL,
    chunks_count INTEGER NOT NULL DEFAULT 0,
    gap_count INTEGER NOT NULL DEFAULT 0,
    keyword_hits INTEGER NOT NULL DEFAULT 0,
    unique_keywords INTEGER NOT NULL DEFAULT 0,
    loan_detections INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (station_id, date)
);

CREATE INDEX IF NOT EXISTS idx_station_daily_date ON station_daily(date);
