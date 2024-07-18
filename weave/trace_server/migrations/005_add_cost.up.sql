CREATE TABLE llm_token_prices (
    /*
    `pricing_level`: The level at which the token pricing applies. It can be 'default' for global pricing,
    'project' for project-specific pricing, or 'org' for organization-specific pricing.
    */
    pricing_level String,

    /*
    `filter_id`: The filter identifier for the token pricing. It can be 'default' or any other string. This allow with type to uniquely identify where the pricing applies.
    */
    filter_id String,

    /*
    `llm_id`: The identifier for the language model. This links the pricing to a specific LLM.
    */
    llm_id String,

    /*
    `effective_date`: The date when the token pricing becomes effective.
    */
    effective_date Date,

    /*
    `input_token_cost`: The cost of an input token in the specified LLM.
    */
    input_token_cost Float,

    /*
    `output_token_cost`: The cost of an output token in the specified LLM.
    */
    output_token_cost Float

) ENGINE = ReplacingMergeTree()
ORDER BY (pricing_level, filter_id, llm_id, effective_date);
