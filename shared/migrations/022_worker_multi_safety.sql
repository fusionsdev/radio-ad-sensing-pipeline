ALTER TABLE chunks ADD COLUMN processing_started_at REAL;
ALTER TABLE chunks ADD COLUMN processing_heartbeat_at REAL;
ALTER TABLE chunks ADD COLUMN processed_at REAL;
ALTER TABLE chunks ADD COLUMN worker_id TEXT;

CREATE INDEX IF NOT EXISTS idx_chunks_processing_started_at
    ON chunks(status, processing_started_at);

CREATE INDEX IF NOT EXISTS idx_chunks_processing_heartbeat_at
    ON chunks(status, processing_heartbeat_at);

CREATE INDEX IF NOT EXISTS idx_chunks_processed_at
    ON chunks(processed_at);

CREATE INDEX IF NOT EXISTS idx_chunks_worker_processed
    ON chunks(worker_id, processed_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_chunk_id_unique
    ON transcripts(chunk_id);
