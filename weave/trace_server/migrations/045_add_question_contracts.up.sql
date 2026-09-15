-- Every question contract the failure funnel has verified, one row per (contract, turn).
-- ReplacingMergeTree on (project_id, conversation_id, contract_id, last_turn_index): a
-- redelivered turn rewrites its own verdict, and a later turn adds a new one.
CREATE TABLE IF NOT EXISTS question_contracts
(
    project_id String,
    conversation_id String,
    -- Derived from (project, conversation, source trace, deliverable), so a redelivery
    -- and a re-extraction of the same ask land on the same contract.
    contract_id UUID,
    config_sha LowCardinality(String),

    -- Where the obligation was raised.
    source_trace_id String,
    source_turn_index UInt32,
    source_message_indices Array(UInt32),
    request_type LowCardinality(String),
    deliverable String,
    completion_criterion String DEFAULT '',
    constraints Array(String) DEFAULT [],
    required_gate String DEFAULT '',

    -- The verifier's verdict on the turn named by last_trace_id.
    state LowCardinality(String),
    last_trace_id String,
    last_turn_index UInt32,
    -- Consecutive verifications that returned insufficient_evidence; expiry counts these.
    idle_turns UInt8 DEFAULT 0,
    -- Every event the verifier saw, as JSON refs resolvable to spans across turns.
    ledger String DEFAULT '',
    evidence_span_ids Array(String) DEFAULT [],

    trace_started_at DateTime64(6, 'UTC'),
    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(trace_started_at)
ORDER BY (project_id, conversation_id, contract_id, last_turn_index)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- A failure row now names the contract it came from and stores the verifier's ledger.
ALTER TABLE failure_signatures
    ADD COLUMN IF NOT EXISTS contract_id UUID DEFAULT toUUID('00000000-0000-0000-0000-000000000000') AFTER evidence_span_ids,
    ADD COLUMN IF NOT EXISTS contract_deliverable String DEFAULT '' AFTER contract_id,
    ADD COLUMN IF NOT EXISTS contract_source_turn_index Int32 DEFAULT -1 AFTER contract_deliverable,
    ADD COLUMN IF NOT EXISTS completion_state LowCardinality(String) DEFAULT '' AFTER contract_source_turn_index,
    ADD COLUMN IF NOT EXISTS ledger String DEFAULT '' AFTER completion_state;
