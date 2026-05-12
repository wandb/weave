-- Migration 031: Add centralized sampling rules
--
-- Stores per-project sampling rules as an append-only audit log. The latest
-- active state is read with argMax(rate/enabled, updated_at), mirroring
-- project_ttl_settings.

CREATE TABLE sampling_rules (
    project_id   String,
    scope        LowCardinality(String),
    op_pattern   String DEFAULT '',
    rate         Float64,
    enabled      UInt8 DEFAULT 1,
    updated_at   DateTime64(3) DEFAULT now64(3),
    updated_by   String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (project_id, scope, op_pattern, updated_at)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;
