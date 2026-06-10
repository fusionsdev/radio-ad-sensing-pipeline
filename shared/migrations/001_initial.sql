CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    format TEXT,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS canonical_ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT,
    phone_norm TEXT,
    category TEXT,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    airing_count INTEGER NOT NULL DEFAULT 0,
    archived_audio_path TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES stations(id),
    path TEXT NOT NULL,
    start_ts REAL NOT NULL,
    end_ts REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    known_ad_id INTEGER REFERENCES canonical_ads(id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status);
CREATE INDEX IF NOT EXISTS idx_chunks_station_id ON chunks(station_id);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL UNIQUE REFERENCES chunks(id),
    text TEXT NOT NULL,
    asr_duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    canonical_ad_id INTEGER REFERENCES canonical_ads(id),
    is_ad INTEGER NOT NULL,
    ad_category TEXT,
    company_name TEXT,
    phone_number TEXT,
    website TEXT,
    offer_summary TEXT,
    key_claims TEXT,
    confidence REAL,
    alerted INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_detections_canonical_ad_id ON detections(canonical_ad_id);

CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES stations(id),
    start_ts REAL NOT NULL,
    end_ts REAL,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_ad_id INTEGER NOT NULL REFERENCES canonical_ads(id),
    chromaprint_vector BLOB NOT NULL,
    duration REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS status (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL
);
