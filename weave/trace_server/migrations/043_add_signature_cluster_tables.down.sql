ALTER TABLE failure_signatures
    DROP COLUMN IF EXISTS span_id,
    DROP COLUMN IF EXISTS trace_ended_at,
    DROP COLUMN IF EXISTS turn_signature_count,
    DROP COLUMN IF EXISTS turn_cache_read_input_tokens,
    DROP COLUMN IF EXISTS turn_cache_creation_input_tokens,
    DROP COLUMN IF EXISTS turn_reasoning_tokens,
    DROP COLUMN IF EXISTS turn_output_tokens,
    DROP COLUMN IF EXISTS turn_input_tokens;

ALTER TABLE intent_signatures
    DROP COLUMN IF EXISTS span_id,
    DROP COLUMN IF EXISTS trace_ended_at,
    DROP COLUMN IF EXISTS turn_signature_count,
    DROP COLUMN IF EXISTS turn_cache_read_input_tokens,
    DROP COLUMN IF EXISTS turn_cache_creation_input_tokens,
    DROP COLUMN IF EXISTS turn_reasoning_tokens,
    DROP COLUMN IF EXISTS turn_output_tokens,
    DROP COLUMN IF EXISTS turn_input_tokens;

DROP VIEW IF EXISTS signature_cluster_assignments_by_conversation_mv;

DROP TABLE IF EXISTS signature_cluster_assignments_by_conversation;

DROP TABLE IF EXISTS signature_cluster_assignments;

DROP TABLE IF EXISTS signature_clusters;

DROP TABLE IF EXISTS signature_cluster_runs;
