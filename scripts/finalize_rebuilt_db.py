from shared.db import migrate
import sqlite3
from pathlib import Path

rebuilt = Path("data/pipeline_rebuilt.db")
live = Path("data/pipeline.db")
corrupt = Path("data/pipeline.db.corrupt")

c = sqlite3.connect(rebuilt)
# company_entities was dropped on corrupt DB; recreate from 007 schema
c.executescript(
    """
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
    """
)
c.commit()
print("integrity", c.execute("PRAGMA integrity_check").fetchone()[0])
print("raw", c.execute("SELECT COUNT(*) FROM cfpb_complaints_raw").fetchone()[0])
print("entities exists", c.execute("SELECT name FROM sqlite_master WHERE name='cfpb_company_entities'").fetchone())
c.close()

if not corrupt.exists():
    live.rename(corrupt)
elif live.exists():
    live.unlink()
rebuilt.rename(live)
print("swapped pipeline_rebuilt.db -> pipeline.db")
