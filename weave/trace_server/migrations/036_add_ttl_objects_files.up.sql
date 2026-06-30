-- Migration 036: TTL for stored objects, dataset rows, and files.
--
-- Mirrors the calls-TTL pattern (029): a non-null expire_at column defaulting to
-- the 2100-01-01 sentinel, then a TTL clause. object_versions and table_rows get
-- a column TTL clearing only the heavy val_dump payload (the metadata row
-- survives), files get a row TTL. Bucket blobs expire via object-store
-- lifecycle, not here.
--
-- Safe to deploy alone: every row defaults to the sentinel, so nothing expires
-- until a write path stamps a real expire_at. The toDateTime() wrapper is
-- required for CH < 25.6 compatibility (PR #80710).

-- Objects: column TTL nulls val_dump, keeps refs/lineage/aliases.
ALTER TABLE object_versions
    ADD COLUMN expire_at DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3);
ALTER TABLE object_versions
    MODIFY COLUMN val_dump String TTL toDateTime(expire_at);

-- Dataset rows: same column-TTL treatment.
ALTER TABLE table_rows
    ADD COLUMN expire_at DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3);
ALTER TABLE table_rows
    MODIFY COLUMN val_dump String TTL toDateTime(expire_at);

-- Files: row TTL drops the CH row and inline val_bytes (exactly like calls).
ALTER TABLE files
    ADD COLUMN expire_at DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3);
ALTER TABLE files
    MODIFY TTL toDateTime(expire_at) DELETE;
