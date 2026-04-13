-- Add bloom filter index on id column to speed up single-ID lookups (call_read).
--
-- The existing minmax index (idx_id) is ineffective for random IDs like OTel
-- span IDs because every granule's min/max range spans the entire ID space.
-- A bloom filter can skip ~99% of granules for equality/IN checks regardless
-- of ID distribution.
--
-- We add a new index (idx_id_bloom) alongside the existing minmax rather than
-- replacing it, so this migration is safe to run on any cluster state.
ALTER TABLE calls_complete
    ADD INDEX IF NOT EXISTS idx_id_bloom id TYPE bloom_filter(0.01) GRANULARITY 1
    SETTINGS alter_sync = 1;

-- Materialize the index for existing data
ALTER TABLE calls_complete
    MATERIALIZE INDEX idx_id_bloom
    SETTINGS mutations_sync = 1;
