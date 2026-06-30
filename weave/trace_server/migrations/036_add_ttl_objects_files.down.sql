-- Rollback Migration 036: remove object/table_rows/files TTL.
-- Drop the TTL clauses before the expire_at columns they reference.

ALTER TABLE files REMOVE TTL;
ALTER TABLE files DROP COLUMN expire_at;

ALTER TABLE table_rows MODIFY COLUMN val_dump REMOVE TTL;
ALTER TABLE table_rows DROP COLUMN expire_at;

ALTER TABLE object_versions MODIFY COLUMN val_dump REMOVE TTL;
ALTER TABLE object_versions DROP COLUMN expire_at;
