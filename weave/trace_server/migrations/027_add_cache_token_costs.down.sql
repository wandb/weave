ALTER TABLE llm_token_prices DROP COLUMN IF EXISTS cache_read_input_token_cost;
ALTER TABLE llm_token_prices DROP COLUMN IF EXISTS cache_creation_input_token_cost;
