-- One row per distilled intent occurrence, with its embedding and trace
-- provenance inline.
--
-- This table separates two kinds of pipeline change, because their consequences
-- differ:
--
--   embedding_version   Embedding model, dimensions, output normalization.
--                       Vectors under different values cannot be compared, and
--                       a dimensionality change makes cosineDistance throw, so
--                       these rows must coexist and must never meet in one
--                       distance computation. In the sorting key AND the
--                       partition key.
--   judge_model,        Changes what text got embedded, not whether vectors
--   prompt_version,     compare. Payload only. A re-extraction REPLACES its
--   category            predecessor through record_version.
--
-- What that split buys, which is the whole point of it:
--   * A judge or prompt change rewrites rows in place and adds no partition.
--   * An embedding change is a backfill. Write the new version alongside the
--     old, verify coverage, flip the server-side active version, then
--     DROP PARTITION the old one. Neither PARTITION BY nor ORDER BY can be
--     altered on a populated table, so that path has to exist up front.
--   * Readers never pass a version. The server resolves one active
--     embedding_version per project.
--
-- The one case replacement does not cover: id is content-addressed, so a
-- re-extraction that stops producing a signature leaves its old row behind. A
-- backfill therefore closes with a DELETE scoped to its window, selecting on
-- pipeline_recipe_sha256.
CREATE TABLE IF NOT EXISTS intent_records
(
    project_id String,
    -- Hash of (conversation_id, turn_index, lens, signature_id,
    -- toDate(source_started_at)). signature_id rather than an ordinal, so a
    -- judge that reorders its output does not churn rows. Excludes
    -- embedding_version so a re-embed reuses the id, which is how new-version
    -- coverage is checked before a cutover.
    id String,
    -- Hash of (lens, canonicalized signature): groups occurrences of one intent
    -- while keeping the same text as an intent distinct from it as a failure.
    -- Downstream cluster tables key on this with no lens column.
    signature_id FixedString(16),
    -- 'intent' or 'failure'. No DEFAULT: it is folded into id and signature_id,
    -- so a row whose column disagrees with its own hashes is undetectable, and
    -- an empty lens that matches no run fails louder.
    lens LowCardinality(String),
    embedding_version UInt32,                -- 32-bit digest of (embedding model, dimensions, output normalization)
    record_version UInt64,                   -- ReplacingMergeTree version, highest for a key wins

    -- Closed taxonomy, one Enum over the union of both lenses. Excluded from
    -- identity because a label can be corrected without changing the text or
    -- the embedding. Numbers are permanent: never renumber or reuse one, and
    -- append new labels inside that lens's block (11-20 intent, 32+ failure).
    -- Appending to an Enum is metadata-only, so growing this costs no rewrite.
    -- 'other' is a member of BOTH taxonomies, and the writer maps an
    -- unrecognized judge label to it rather than failing the batch. '' = 0 has
    -- no DEFAULT for the same reason as lens: an omitted category reads back
    -- empty instead of silently claiming to be the first label.
    -- weave/trace_server/intent_records_taxonomy.py is the writer's copy of this
    -- list, and the migrator functional test asserts the two match.
    category Enum8(
        '' = 0,
        'action_request' = 1, 'information_request' = 2, 'problem_report' = 3,
        'feedback' = 4, 'approval' = 5, 'rejection' = 6, 'correction' = 7,
        'clarification' = 8, 'bad_faith' = 9, 'other' = 10,
        'task_misunderstanding' = 21, 'context_loss' = 22, 'wrong_output' = 23,
        'requirement_violation' = 24, 'tool_misuse' = 25, 'tool_failure' = 26,
        'system_error' = 27, 'unproductive_loop' = 28, 'capability_gap' = 29,
        'improper_refusal' = 30, 'safety_violation' = 31
    ),
    signature String,
    -- ISO 639-1, or the ISO 639-2 'und' sentinel when indeterminate, which is
    -- also the DEFAULT so unknown has one value. Signatures are
    -- English-normalized, so this is the only record of the source language.
    language LowCardinality(String) DEFAULT 'und',

    -- sentiment_score is an ALIAS so the ordinal scale has one home: rescoring
    -- is a migration, not a row rewrite.
    sentiment LowCardinality(String) DEFAULT '',
    sentiment_confidence Float32 DEFAULT 0,
    sentiment_score Float32 ALIAS transform(sentiment, ['frustrated', 'dissatisfied', 'neutral', 'satisfied', 'delighted'], [-1., -0.5, 0., 0.5, 1.], 0.),

    embedding_model LowCardinality(String),  -- human-readable companion to embedding_version
    vector Array(Float32),                   -- searched by exact cosine distance, intentionally no ANN index. length(vector) is the dimensionality

    judge_model LowCardinality(String) DEFAULT '',   -- payload, see header: a new judge replaces, it does not coexist
    prompt_version LowCardinality(String) DEFAULT '',
    -- Lowercase hex over the whole recipe. There is no recipe registry table,
    -- so this is the audit trail and the marker a backfill sweep selects on.
    pipeline_recipe_sha256 String DEFAULT '',

    trace_id String DEFAULT '',
    span_id String DEFAULT '',               -- root span of the source turn, the pointer back into spans
    conversation_id String DEFAULT '',
    turn_index UInt16 DEFAULT 0,             -- (conversation_id, turn_index) is the turn identity
    user_id String DEFAULT '',               -- pseudonymous source subject, distinct from the writer

    -- Execution context of the source turn, denormalized at extraction. A
    -- turn's rows all repeat these, lens='failure' included.
    agent_name LowCardinality(String) DEFAULT '',
    agent_version String DEFAULT '',          -- free-form version label, so plain String
    provider LowCardinality(String) DEFAULT '',
    request_model LowCardinality(String) DEFAULT '', -- model the source turn called, not judge_model or embedding_model
    surface LowCardinality(String) DEFAULT '',
    status_code Enum8('UNSET' = 0, 'OK' = 1, 'ERROR' = 2) DEFAULT 'UNSET', -- same vocabulary as spans.status_code, so the two join without a cast
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    turn_summary String DEFAULT '',           -- describes the assistant response, so it repeats across a turn's rows

    -- Snapshot of the source turn's start time, taken at extraction and never
    -- re-read, so it is the analysis clock rather than the pipeline clock.
    source_started_at DateTime64(6, 'UTC'),
    intent_extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3),
    -- Per-row retention override, default effectively never. Retention only:
    -- logical retraction uses a lightweight DELETE, because TTL is asynchronous
    -- and a row still awaiting its merge still answers reads.
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    -- The Enum alone cannot stop a failure label landing on an intent row, so
    -- state the pairing. Listed explicitly rather than keyed off the number
    -- blocks, so a new label omitted here is rejected loudly instead of being
    -- silently gated to the wrong lens. 'other' appears under both lenses
    -- because it belongs to both taxonomies, not as an exception to them.
    -- ADD/DROP CONSTRAINT does not validate existing rows, so amending this
    -- later is metadata-only too.
    CONSTRAINT category_matches_lens CHECK
        category = ''
        OR (lens = 'intent' AND category IN (
            'action_request', 'information_request', 'problem_report',
            'feedback', 'approval', 'rejection', 'correction',
            'clarification', 'bad_faith', 'other'))
        OR (lens = 'failure' AND category IN (
            'task_misunderstanding', 'context_loss', 'wrong_output',
            'requirement_violation', 'tool_misuse', 'tool_failure',
            'system_error', 'unproductive_loop', 'capability_gap',
            'improper_refusal', 'safety_violation', 'other')),

    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(record_version)
-- Source month so retention and range reads follow user activity, and
-- embedding_version so a cutover retires the old vectors as a metadata
-- operation. A backfill spanning >100 months needs a raised
-- max_partitions_per_insert_block.
PARTITION BY (toYYYYMM(source_started_at), embedding_version)
-- embedding_version leads because every read pins exactly one, resolved
-- server-side. toDate(source_started_at) precedes id so a sub-month read prunes
-- granules. Day rather than the raw timestamp keeps the replacement identity as
-- coarse as it can be while still pruning.
ORDER BY (project_id, embedding_version, lens, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
