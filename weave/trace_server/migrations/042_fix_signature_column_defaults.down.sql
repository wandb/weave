ALTER TABLE intent_signatures
    MODIFY COLUMN IF EXISTS sentiment LowCardinality(String) DEFAULT 'neutral';
