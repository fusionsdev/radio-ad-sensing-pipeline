CREATE TABLE IF NOT EXISTS novelty_review_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT,
    reason TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_novelty_review_actions_target
    ON novelty_review_actions(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_novelty_review_actions_created
    ON novelty_review_actions(created_at DESC);

CREATE TABLE IF NOT EXISTS known_terms_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    term_type TEXT NOT NULL,
    vertical TEXT,
    reason TEXT,
    source_candidate_id INTEGER REFERENCES candidate_terms(id),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_known_terms_pending_status
    ON known_terms_pending(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_known_terms_pending_term
    ON known_terms_pending(term);
