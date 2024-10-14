CREATE TABLE llm_token_prices (
     /*
    `id`: The unique identifier for the call. This is typically a UUID.
    */
    id String,
    /*
    `pricing_level`: The level at which the token pricing applies. It can be 'default' for global pricing,
    'project' for project-specific pricing, or 'org' for organization-specific pricing.
    */
    pricing_level String,

    /*
    `pricing_level_id`: The pricing level identifier for the token pricing. It can be 'default' or any other string(e.g. org id or project id). This allow with type to uniquely identify where the pricing applies.
    */
    pricing_level_id String,

    /*
    `provider`: The initial provider of the LLM, some LLMs are provided other than the default provider.
    */
    provider_id String,

    /*
    `llm_id`: The identifier for the language model. This links the pricing to a specific LLM.
    */
    llm_id String,

    /*
    `effective_date`: The date when the token pricing becomes effective.
    */
    effective_date DateTime64(3) DEFAULT now64(3),

    /*
    `prompt_token_cost`: The cost of a prompt token in the specified LLM.
    */
    prompt_token_cost Float,

    /*
    `prompt_token_cost_unit`: The unit of prompt token cost in the specified LLM.
    */
    prompt_token_cost_unit String,

    /*
    `completion_token_cost`: The cost of a completion token in the specified LLM.
    */
    completion_token_cost Float,

    /*
    `completion_token_cost_unit`: The unit of completion token cost in the specified LLM.
    */
    completion_token_cost_unit String,

    /*
    `created_by`: User ID of the user who created the record, or the system if the record was created by the system.
    */
    created_by String,

    /*
    `created_at`: When the record was created.
    */
    created_at DateTime64(3) DEFAULT now64(3),

) ENGINE = MergeTree()
ORDER BY (pricing_level, pricing_level_id, provider_id, llm_id, effective_date);
