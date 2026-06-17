CREATE TABLE IF NOT EXISTS advertiser_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    vertical TEXT NOT NULL,
    domain TEXT,
    source_type TEXT NOT NULL DEFAULT 'radio_transcript',
    confidence TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'needs_review',
    trademark_entity_id INTEGER REFERENCES trademark_entities(id),
    evidence_path TEXT,
    hit_advertiser_alerted INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_advertiser_entities_normalized
    ON advertiser_entities(normalized_name);

CREATE TABLE IF NOT EXISTS advertiser_entity_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    advertiser_entity_id INTEGER NOT NULL REFERENCES advertiser_entities(id),
    detection_id INTEGER NOT NULL REFERENCES detections(id),
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    station_id INTEGER NOT NULL REFERENCES stations(id),
    station_display_name TEXT,
    market TEXT,
    hit_ts REAL NOT NULL,
    audio_clip_path TEXT,
    audio_clip_start_sec REAL,
    audio_clip_end_sec REAL,
    transcript TEXT,
    website TEXT,
    phone_number TEXT,
    cta TEXT,
    offer_summary TEXT,
    key_claims TEXT,
    detection_confidence REAL,
    created_at REAL NOT NULL,
    UNIQUE(advertiser_entity_id, detection_id)
);

CREATE INDEX IF NOT EXISTS idx_advertiser_entity_detections_entity
    ON advertiser_entity_detections(advertiser_entity_id, hit_ts DESC);
