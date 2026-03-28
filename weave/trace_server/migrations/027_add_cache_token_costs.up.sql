-- Add cache token pricing columns to llm_token_prices
ALTER TABLE llm_token_prices ADD COLUMN IF NOT EXISTS cache_read_input_token_cost Float64 DEFAULT 0;
ALTER TABLE llm_token_prices ADD COLUMN IF NOT EXISTS cache_write_input_token_cost Float64 DEFAULT 0;
