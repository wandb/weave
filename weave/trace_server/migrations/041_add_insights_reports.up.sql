-- Versioned report sections for the evolving Insights/Pulse report model.
--
-- New report snapshots receive a new report_id. To destructively replace one
-- section within an existing report, write the same project_id/report_id/
-- section_id with a later created_at. Read paths must collapse versions with
-- argMax(..., created_at), not FINAL.
CREATE TABLE IF NOT EXISTS insights_reports (
    project_id String,
    report_id UUID,
    -- Stable within a report so a section can be replaced independently.
    section_id UUID,
    section_type LowCardinality(String),
    period_days UInt16,
    -- UTC, exclusive end of the reporting window.
    period_end DateTime64(3),
    title String DEFAULT '',
    subtitle String DEFAULT '',
    description String DEFAULT '',
    -- Version of the JSON contract for this section type.
    section_schema_version UInt16,
    section_json String CODEC(ZSTD(6)),
    -- Raw 32-byte SHA-256 digest, not a 64-character hex string.
    section_json_hash FixedString(32),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(created_at)
-- Monthly partitions support the two-year retention policy without creating a
-- partition per reporting day.
PARTITION BY toYYYYMM(period_end)
-- The primary read is a full report scoped to a project and report ID.
ORDER BY (project_id, report_id, section_id)
TTL period_end + INTERVAL 2 YEAR DELETE
SETTINGS min_bytes_for_wide_part = 0;
