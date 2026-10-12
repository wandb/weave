ALTER TABLE feedback
    DROP COLUMN IF EXISTS scorer_tags,
    DROP COLUMN IF EXISTS scorer_tag_reasons,
    DROP COLUMN IF EXISTS scorer_tag_confidences,
    DROP COLUMN IF EXISTS scorer_ratings,
    DROP COLUMN IF EXISTS scorer_rating_reasons,
    DROP COLUMN IF EXISTS scorer_rating_confidences;
