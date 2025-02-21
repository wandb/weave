ALTER TABLE files
    ADD COLUMN bytes_stored Nullable(Int)
    ADD COLUMN file_storage_uri Nullable(String);