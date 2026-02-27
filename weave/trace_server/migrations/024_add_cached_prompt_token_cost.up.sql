-- Add cached prompt/input token pricing to llm_token_prices.
-- Defaults preserve existing behavior for rows that predate this migration.
ALTER TABLE llm_token_prices
    ADD COLUMN cached_prompt_token_cost Float DEFAULT prompt_token_cost;

ALTER TABLE llm_token_prices
    ADD COLUMN cached_prompt_token_cost_unit String DEFAULT prompt_token_cost_unit;
