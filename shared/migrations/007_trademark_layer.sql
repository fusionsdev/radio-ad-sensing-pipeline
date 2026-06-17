CREATE TABLE IF NOT EXISTS trademark_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    review_status TEXT NOT NULL DEFAULT 'new',
    trademark_risk TEXT NOT NULL DEFAULT 'unknown',
    ad_copy_allowed INTEGER NOT NULL DEFAULT 0,
    landing_page_allowed INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    notes TEXT,
    cfpb_company_entity_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trademark_entities_normalized
    ON trademark_entities(normalized_name);

CREATE TABLE IF NOT EXISTS trademark_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trademark_entity_id INTEGER NOT NULL REFERENCES trademark_entities(id),
    alias_name TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trademark_aliases_entity
    ON trademark_aliases(trademark_entity_id);

CREATE TABLE IF NOT EXISTS trademark_keyword_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trademark_entity_id INTEGER NOT NULL REFERENCES trademark_entities(id),
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    variant_type TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'new',
    ad_copy_allowed INTEGER NOT NULL DEFAULT 0,
    confidence REAL DEFAULT 0,
    score REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trademark_keywords_entity
    ON trademark_keyword_candidates(trademark_entity_id);
CREATE INDEX IF NOT EXISTS idx_trademark_keywords_status
    ON trademark_keyword_candidates(status);
