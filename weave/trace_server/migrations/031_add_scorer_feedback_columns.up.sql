/*
Typed columns for `wandb.agent_monitor` scorer feedback. Non-null with empty
defaults, so existing rows need no backfill.

Reasons and confidences are split by whether they attach to a tag or a rating.
Map keys are the plain tag/rating name (no `tag.<name>` / `rating.<name>` prefix).

- `scorer_tags`: string labels assigned by a scorer.
- `scorer_tag_reasons`: optional reason text per tag, keyed by tag name.
- `scorer_tag_confidences`: optional confidence per tag, keyed by tag name.
- `scorer_ratings`: numeric scores keyed by rating name (e.g. `_rating_`).
- `scorer_rating_reasons`: optional reason text per rating, keyed by rating name.
- `scorer_rating_confidences`: optional confidence per rating, keyed by rating name.
*/
ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS scorer_tags               Array(String)         DEFAULT [],
    ADD COLUMN IF NOT EXISTS scorer_tag_reasons        Map(String, String)   DEFAULT map(),
    ADD COLUMN IF NOT EXISTS scorer_tag_confidences    Map(String, Float64)  DEFAULT map(),
    ADD COLUMN IF NOT EXISTS scorer_ratings            Map(String, Float64)  DEFAULT map(),
    ADD COLUMN IF NOT EXISTS scorer_rating_reasons     Map(String, String)   DEFAULT map(),
    ADD COLUMN IF NOT EXISTS scorer_rating_confidences Map(String, Float64)  DEFAULT map();
