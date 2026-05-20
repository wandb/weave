/*
Typed columns for `wandb.agent_monitor` scorer feedback. Non-null with empty
defaults, so existing rows need no backfill.

- `scorer_tags`: string labels assigned by a scorer.
- `scorer_ratings`: numeric scores keyed by rating name (e.g. `_rating_`).
    LowCardinality keys — the set of rating names is small.
- `scorer_reasons`: optional reason text, keyed by `tag.<name>` / `rating.<name>`.
- `scorer_confidences`: optional confidence per tag/rating, same key convention.
*/
ALTER TABLE feedback
    ADD COLUMN scorer_tags Array(String) DEFAULT [],
    ADD COLUMN scorer_ratings Map(LowCardinality(String), Float64) DEFAULT map(),
    ADD COLUMN scorer_reasons Map(String, String) DEFAULT map(),
    ADD COLUMN scorer_confidences Map(String, Float64) DEFAULT map();
