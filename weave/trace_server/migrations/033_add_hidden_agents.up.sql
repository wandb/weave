-- Per-(project, agent) visibility toggle for the Agents tab.
--
-- An "agent" is not a stored entity. It is a derived aggregation over `spans`
-- (see migration 030). There is no row to flip a flag on, so hide/unhide is
-- tracked in this small side table instead.
--
-- ReplacingMergeTree keyed by (project_id, agent_name): the latest row by
-- `updated_at` wins, so hide and unhide are both plain INSERTs and the toggle
-- is fully reversible. Read-side queries resolve current state without FINAL
-- via `GROUP BY agent_name HAVING argMax(is_hidden, updated_at) = true`.
--
-- Visibility is project-wide: a hide applies to everyone
-- in the project.
CREATE TABLE IF NOT EXISTS hidden_agents (
    project_id String,
    agent_name String,
    is_hidden  Bool DEFAULT true,                -- true = hidden, false = visible
    updated_at DateTime64(3) DEFAULT now64(3)    -- ReplacingMergeTree version
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (project_id, agent_name);
