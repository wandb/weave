/*
Duplicate select genai metadata from the `spans` table into `feedback`.
Denormalizing the data this ways allows for efficient queries on agent data.
Includes only the data that we frequently want to filter/group on for scores.
This is used only for visualizations and `spans` remains the source of truth.

- `span_agent_name`: display name of the scored agent (from `spans.agent_name`).
- `span_agent_version`: agent version string (from `spans.agent_version`).
- `span_status_code`: status of the scored turn (from `spans.status_code`).
*/
ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS span_agent_name    String DEFAULT '',
    ADD COLUMN IF NOT EXISTS span_agent_version String DEFAULT '',
    ADD COLUMN IF NOT EXISTS span_status_code   Enum8('UNSET'=0, 'OK'=1, 'ERROR'=2) DEFAULT 'UNSET';

/*
Add data-skipping indexes on the columns we want to filter on.
- `idx_span_agent_name`: skip granules with agents not in the query.
- `idx_span_agent_version`: skip granules with versions not in the query.
*/
ALTER TABLE feedback
    ADD INDEX IF NOT EXISTS idx_span_agent_name   span_agent_name    TYPE set(64)  GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_span_agent_version span_agent_version TYPE set(128) GRANULARITY 1;
