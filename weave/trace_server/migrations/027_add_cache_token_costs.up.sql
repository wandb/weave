ALTER TABLE llm_token_prices ADD COLUMN IF NOT EXISTS cache_read_input_token_cost Float DEFAULT 0;
ALTER TABLE llm_token_prices ADD COLUMN IF NOT EXISTS cache_creation_input_token_cost Float DEFAULT 0;
