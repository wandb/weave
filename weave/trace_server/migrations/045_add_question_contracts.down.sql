ALTER TABLE failure_signatures
    DROP COLUMN IF EXISTS ledger,
    DROP COLUMN IF EXISTS completion_state,
    DROP COLUMN IF EXISTS contract_source_turn_index,
    DROP COLUMN IF EXISTS contract_deliverable,
    DROP COLUMN IF EXISTS contract_id;

DROP TABLE IF EXISTS question_contracts;
