# Recommended migration (NOT applied automatically)
#
# Apply manually after operator review if keyword_hits should store classifier metadata.
# Until then, classifier_name / classifier_version / taxonomy_version are logged only.

ALTER TABLE keyword_hits ADD COLUMN classifier_name TEXT;
ALTER TABLE keyword_hits ADD COLUMN classifier_version TEXT;
ALTER TABLE keyword_hits ADD COLUMN taxonomy_version TEXT;

CREATE INDEX IF NOT EXISTS idx_keyword_hits_classifier_version
    ON keyword_hits(classifier_version);
