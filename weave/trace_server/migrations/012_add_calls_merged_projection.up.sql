ALTER TABLE calls_merged ADD PROJECTION calls_merged_projection (
    SELECT * ORDER BY project_id, id, started_at
);

ALTER TABLE calls_merged MATERIALIZE PROJECTION calls_merged_projection;