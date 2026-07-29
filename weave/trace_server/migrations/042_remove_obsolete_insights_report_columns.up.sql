-- Migration 041 was initially applied with these columns. Updating its
-- CREATE TABLE IF NOT EXISTS source cannot change databases that already ran
-- it, so remove the obsolete physical columns in a separate forward migration.
ALTER TABLE insights_reports
    DROP COLUMN IF EXISTS section_order,
    DROP COLUMN IF EXISTS report_version;
