-- Add set index, 100 max unique wb_run_ids in the index per (1) granule
ALTER TABLE calls_merged ADD INDEX idx_wb_run_id (wb_run_id) TYPE set(100) GRANULARITY 1;
-- Materialize the index, actually generating index marks for all the granules
ALTER TABLE calls_merged MATERIALIZE INDEX idx_wb_run_id;
