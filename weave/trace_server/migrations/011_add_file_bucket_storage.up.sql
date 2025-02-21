ALTER TABLE files ADD COLUMN bytes_stored Nullable(UInt32);
ALTER TABLE files ADD COLUMN file_storage_uri Nullable(String);