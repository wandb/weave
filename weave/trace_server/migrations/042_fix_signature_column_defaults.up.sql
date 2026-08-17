/*
Align intent_signatures.sentiment with the absent-label convention the write path
enforces: '' means the judge emitted no usable label, and 'neutral' is a real
taxonomy label a judge can choose. Migration 041 defaulted the column to
'neutral', which would silently turn a missing label into a real one. Its sibling
failure_signatures.severity already defaults to '' and carries that comment.

Metadata only: the writer supplies the column on every row, so no stored row was
ever written from the old default and nothing needs backfilling.
*/
ALTER TABLE intent_signatures
    MODIFY COLUMN IF EXISTS sentiment LowCardinality(String) DEFAULT '';
