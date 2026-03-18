-- Add content, artifact, and object reference columns to genai_spans.
-- These store JSON arrays of references attached by weave.otel utilities.
ALTER TABLE genai_spans ADD COLUMN IF NOT EXISTS content_refs String DEFAULT '';
ALTER TABLE genai_spans ADD COLUMN IF NOT EXISTS artifact_refs String DEFAULT '';
ALTER TABLE genai_spans ADD COLUMN IF NOT EXISTS object_refs String DEFAULT '';
