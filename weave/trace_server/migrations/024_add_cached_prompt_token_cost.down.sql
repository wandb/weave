ALTER TABLE llm_token_prices
    DROP COLUMN cached_prompt_token_cost_unit;

ALTER TABLE llm_token_prices
    DROP COLUMN cached_prompt_token_cost;
