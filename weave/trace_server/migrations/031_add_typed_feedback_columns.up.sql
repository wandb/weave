/*
This migration adds the following typed columns to the feedback table:
- `label`: A short string tag.
- `score`: A numeric score.
- `is_success`: A boolean pass/fail.

Scorer results are currently written to `payload_dump` as opaque JSON. That
makes results hard to display, hard to filter, and slow to query at scale.

These columns are populated by a new `wandb.typed` feedback type. Existing
feedback types are unchanged.
*/
ALTER TABLE feedback
    /*
    `label`: A short string tag associated with a ref (similar to Signals).
    Multiple typed feedback rows may share the same weave_ref with different labels.
    */
    ADD COLUMN label Nullable(String) DEFAULT NULL,
    /*
    `score`: A numeric score associated with a ref.
    */
    ADD COLUMN score Nullable(Float64) DEFAULT NULL,
    /*
    `is_success`: A boolean pass/fail associated with a ref.
    */
    ADD COLUMN is_success Nullable(Bool) DEFAULT NULL;
