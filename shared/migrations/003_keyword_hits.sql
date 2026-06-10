CREATE TABLE IF NOT EXISTS keyword_hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES stations(id),
    keyword TEXT NOT NULL,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    detection_id INTEGER REFERENCES detections(id),
    hit_ts REAL NOT NULL,
    context_excerpt TEXT
);

CREATE INDEX IF NOT EXISTS idx_keyword_hits_station_ts ON keyword_hits(station_id, hit_ts);
CREATE INDEX IF NOT EXISTS idx_keyword_hits_keyword ON keyword_hits(keyword);
CREATE UNIQUE INDEX IF NOT EXISTS idx_keyword_hits_chunk_keyword ON keyword_hits(chunk_id, keyword);
