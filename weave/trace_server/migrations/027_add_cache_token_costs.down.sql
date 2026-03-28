-- Remove cache token pricing columns from llm_token_prices
ALTER TABLE llm_token_prices DROP COLUMN IF EXISTS cache_read_input_token_cost;
ALTER TABLE llm_token_prices DROP COLUMN IF EXISTS cache_write_input_token_cost;
