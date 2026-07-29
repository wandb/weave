-- Down migrations are not applied automatically. Recreate the table from the
-- prior migration if rolling a development database back before migration 042.
ALTER TABLE insights_reports
    ADD COLUMN IF NOT EXISTS section_order UInt16 DEFAULT 0,
    ADD COLUMN IF NOT EXISTS report_version UInt32 DEFAULT 0;
