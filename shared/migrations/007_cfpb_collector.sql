-- CFPB Consumer Complaint Trademark Collector (WP-1)

CREATE TABLE IF NOT EXISTS cfpb_complaints_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT UNIQUE,
    date_received TEXT,
    product TEXT,
    sub_product TEXT,
    issue TEXT,
    sub_issue TEXT,
    consumer_complaint_narrative TEXT,
    company_public_response TEXT,
    company TEXT,
    state TEXT,
    zip_code TEXT,
    tags TEXT,
    consumer_consent_provided TEXT,
    submitted_via TEXT,
    date_sent_to_company TEXT,
    company_response_to_consumer TEXT,
    timely_response TEXT,
    consumer_disputed TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cfpb_complaints_state ON cfpb_complaints_raw(state);
CREATE INDEX IF NOT EXISTS idx_cfpb_complaints_product ON cfpb_complaints_raw(product);
CREATE INDEX IF NOT EXISTS idx_cfpb_complaints_company ON cfpb_complaints_raw(company);

CREATE TABLE IF NOT EXISTS cfpb_company_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_raw TEXT NOT NULL,
    company_normalized TEXT NOT NULL,
    company_canonical TEXT,
    product_mix_json TEXT,
    states_json TEXT,
    complaint_count INTEGER DEFAULT 0,
    narrative_count INTEGER DEFAULT 0,
    first_seen_at TEXT,
    last_seen_at TEXT,
    confidence REAL DEFAULT 0,
    trademark_candidate_score REAL DEFAULT 0,
    review_status TEXT DEFAULT 'new',
    notes TEXT,
    trademark_entity_id INTEGER REFERENCES trademark_entities(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cfpb_company_normalized
    ON cfpb_company_entities(company_normalized);

CREATE TABLE IF NOT EXISTS cfpb_brand_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfpb_company_entity_id INTEGER REFERENCES cfpb_company_entities(id),
    candidate_name TEXT NOT NULL,
    normalized_candidate TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    source TEXT DEFAULT 'cfpb_complaints',
    source_product TEXT,
    source_state TEXT,
    source_complaint_id TEXT,
    evidence_text TEXT,
    confidence REAL DEFAULT 0,
    score REAL DEFAULT 0,
    verification_status TEXT DEFAULT 'needs_verification',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cfpb_candidates_entity
    ON cfpb_brand_candidates(cfpb_company_entity_id);
CREATE INDEX IF NOT EXISTS idx_cfpb_candidates_score
    ON cfpb_brand_candidates(score DESC);

CREATE TABLE IF NOT EXISTS cfpb_collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    source_mode TEXT,
    date_from TEXT,
    date_to TEXT,
    target_states_json TEXT,
    target_products_json TEXT,
    records_seen INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    entities_created INTEGER DEFAULT 0,
    candidates_created INTEGER DEFAULT 0,
    status TEXT,
    error_message TEXT
);
