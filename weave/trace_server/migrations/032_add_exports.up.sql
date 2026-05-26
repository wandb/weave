-- Bulk export audit log. Append-only. One EXPORT_START row per
-- POST /export/start and one EXPORT_MINT row per successful
-- GET /export/{job_id} URL mint. In-flight query state lives in
-- system.query_log and is never duplicated here.
CREATE TABLE IF NOT EXISTS exports (
    request_id      UUID,
    action          LowCardinality(String),
    project_id      String,
    job_id          UUID,
    requested_by    String,
    minted_by       String DEFAULT '',
    table_name      LowCardinality(String),
    request_json    String DEFAULT '',
    output_uri      String DEFAULT '',
    ts              DateTime64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (project_id, job_id, action, ts)
TTL toDateTime(ts) + INTERVAL 7 YEAR;
