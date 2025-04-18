'''
The constants defined in this file map attribute keys from various telemetry standards
to a common format used by Weave. This enables Weave to ingest traces and spans from
different instrumentation libraries while normalizing the data into a consistent format.
'''

# These mappings prioritize standards in a specific order for each attribute type.

# INPUT_KEYS: Maps attribute keys that represent user prompts or inputs to LLMs
# Priority is given to standards in this order:
# This is used to populate the `inputs_dump` column in clickhouse
INPUT_KEYS = [
    "input.value",  # From OpenInference standard - highest priority
    "gen_ai.prompt",  # From OpenTelemetry AI semantic conventions
    "mlflow.spanInputs",  # From MLFlow's tracking format
    "traceloop.entity.input"  # From Traceloop's conventions
    "input",  # Generic fallback for Pydantic models - lowest priority
]

# OUTPUT_KEYS: Maps attribute keys that represent model completions or outputs
# Priority is given to standards in this order:
# This is used to populate the `output_dump` column in clickhouse
OUTPUT_KEYS = [
    "output.value",  # From OpenInference standard - highest priority
    "gen_ai.completion",  # From OpenTelemetry AI semantic conventions
    "mlflow.spanOutputs",  # From MLFlow's tracking format
    "gen_ai.content.completion",  # From OpenLit project's format
    "traceloop.entity.output",  # From Traceloop's conventions
    "output",  # Generic fallback for Pydantic models - lowest priority
]

# USAGE_KEYS: Maps internal Weave usage metric names to their equivalent keys in
# various telemetry standards. Used for token counting and usage statistics.
# Used to populate the usage field of `summary_dump` in clickhouse
USAGE_KEYS = {
    # Maps Weave's "prompt_tokens" to keys from different standards
    "prompt_tokens": ["gen_ai.usage.prompt_tokens", "llm.token_count.prompt"],

    # Maps Weave's "completion_tokens" to keys from different standards
    "completion_tokens": [
        "gen_ai.usage.completion_tokens",
        "llm.token_count.completion",
    ],

    # Maps Weave's "total_tokens" to keys from different standards
    "total_tokens": ["llm.usage.total_tokens", "llm.token_count.total"],
}

# ATTRIBUTE_KEYS: Maps common LLM call metadata attributes to the types of attributes expected in weave traces
# This is used to populate the `attributes_dump` column in clickhouse
# Prior to dumping, the full span is dumped under another key not listed here called `otel_span`
ATTRIBUTE_KEYS = {
    # System prompt/instructions
    "system": [
        "gen_ai.system",  # OpenTelemetry AI
        "llm.system",  # OpenInference
    ],

    # Span kind - identifies the type of operation
    "kind": [
        "weave.span.kind",  # Weave-specific
        "traceloop.span.kind",  # Traceloop
        "openinference.span.kind",  # OpenInference
    ],

    # Model name/identifier
    "model": ["llm.model_name", "gen_ai.response.model"],

    # Provider/vendor of the model
    "provider": [
        "llm.provider",  # Common across standards
    ],

    # Model generation parameters (temperature, max_tokens, etc.)
    "model_parameters": ["gen_ai.request", "llm.invocation_parameters"],
}

# WB_KEYS: Wandb/Weave specific attributes for enhanced visualization and reporting
WB_KEYS = {
    # Custom display name for the call in the UI
    "display_name": ["wandb.display_name"],
}
