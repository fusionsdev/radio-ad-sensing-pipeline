CREATE TABLE IF NOT EXISTS raw_discovery_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    raw_text TEXT,
    title TEXT,
    author_or_publisher TEXT,
    published_at REAL,
    market TEXT,
    state TEXT,
    raw_json TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_discovery_source
    ON raw_discovery_items(source_type, created_at DESC);

CREATE TABLE IF NOT EXISTS candidate_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_item_id INTEGER REFERENCES raw_discovery_items(id),
    candidate_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    vertical TEXT,
    sub_vertical TEXT,
    evidence_text TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    source_confidence REAL NOT NULL DEFAULT 0.0,
    extraction_confidence REAL NOT NULL DEFAULT 0.0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidate_terms_vertical
    ON candidate_terms(vertical, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_terms_normalized
    ON candidate_terms(normalized_text);

CREATE TABLE IF NOT EXISTS novelty_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate_terms(id),
    normalized_text TEXT NOT NULL,
    novelty_status TEXT NOT NULL,
    novelty_score REAL NOT NULL,
    opportunity_score REAL NOT NULL,
    known_match TEXT,
    known_match_type TEXT,
    similarity_score REAL,
    reason TEXT,
    report_eligible INTEGER NOT NULL DEFAULT 0,
    report_suppressed_reason TEXT,
    reviewed_status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_novelty_results_status
    ON novelty_results(novelty_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_novelty_results_report
    ON novelty_results(report_eligible, created_at DESC);

CREATE TABLE IF NOT EXISTS keyword_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate_terms(id),
    opportunity_text TEXT NOT NULL,
    opportunity_type TEXT NOT NULL,
    vertical TEXT,
    sub_vertical TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    evidence_text TEXT,
    novelty_score REAL NOT NULL,
    opportunity_score REAL NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    suggested_action TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_keyword_opportunities_status
    ON keyword_opportunities(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_keyword_opportunities_vertical
    ON keyword_opportunities(vertical, created_at DESC);
