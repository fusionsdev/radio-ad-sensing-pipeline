CREATE TABLE IF NOT EXISTS advertiser_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical TEXT NOT NULL,
    station_id INTEGER NOT NULL REFERENCES stations(id),
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    keyword_hit_id INTEGER REFERENCES keyword_hits(id),
    company_name TEXT,
    domain TEXT,
    phone_number TEXT,
    vanity_phone TEXT,
    offer_summary TEXT,
    cta TEXT,
    hit_ts REAL NOT NULL,
    audio_clip_path TEXT,
    source_keywords TEXT NOT NULL,
    confidence REAL,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_advertiser_opp_vertical_ts
    ON advertiser_opportunities(vertical, hit_ts DESC);
CREATE INDEX IF NOT EXISTS idx_advertiser_opp_station_ts
    ON advertiser_opportunities(station_id, hit_ts DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_advertiser_opp_chunk_vertical
    ON advertiser_opportunities(chunk_id, vertical);
