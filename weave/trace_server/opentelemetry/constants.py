from weave.trace_server.opentelemetry.helpers import try_parse_int, try_parse_timestamp

"""
The constants defined in this file map attribute keys from various telemetry standards
to a common format used by Weave. This enables Weave to ingest traces and spans from
different instrumentation libraries while normalizing the data into a consistent format.

For INPUT_KEYS and OUTPUT_KEYS we respect the original source key when placing it into
our input and output fields respectively.

E.g. If a value is discovered in the `input.value` field of attributes the dict dumped
to clickhouse is:
{ "input.value": SOME_JSON_OR_STR_VALUE, }

For prefix values with nested keys (such as `gen_ai.prompt`) we might see attributes like:

gen_ai.prompt.0.role: user
gen_ai.prompt.0.content: abc

gen_ai.prompt.1.role: user
gen_ai.prompt.1.content: def

the dict dumped to clickhouse is:
{ "gen_ai.prompt": [{ "role": user, "content": abc }, { "role": user, "content": def }] }

For these fields, once a value is discovered in the attributes, so the ordering of these keys matters.


For the other key mappings, a dict is dumped with each of the top level keys in the dict.
The inner list of those key represents the attributes which are checked similarly to
how INPUT_KEYS and OUTPUT_KEYS are checked, where the first one found is used.

If we recieved attributes where:
gen_ai.usage.prompt_tokens: 30
gen_ai.usage.completion_tokens: 40
gen_ai.usage.llm.usage.total_tokens: 70

This would be the resulting dict dumped to clickhouse:
{ "prompt_tokens": 30, "completion_tokens": 40, "total_tokens": 70 }
"""

# These mappings prioritize standards in a specific order for each attribute type.

# INPUT_KEYS: Maps attribute keys that represent user prompts or inputs to LLMs
# Priority is given to standards in this order:
# This is used to populate the `inputs_dump` column in clickhouse
from weave.trace_server.opentelemetry.helpers import try_parse_int

INPUT_KEYS = [
    "ai.prompt",  # Vercel
    "gen_ai.prompt",  # From OpenTelemetry AI semantic conventions
    "input.value",  # From OpenInference standard
    "mlflow.spanInputs",  # From MLFlow's tracking format
    "traceloop.entity.input"  # From Traceloop's conventions
    "input",  # Generic fallback for Pydantic models - lowest priority
]

# OUTPUT_KEYS: Maps attribute keys that represent model completions or outputs
# Priority is given to standards in this order:
# This is used to populate the `output_dump` column in clickhouse
OUTPUT_KEYS = [
    "ai.response",  # Vercel
    "gen_ai.completion",  # From OpenTelemetry AI semantic conventions
    "output.value",  # From OpenInference standard - highest priority
    "mlflow.spanOutputs",  # From MLFlow's tracking format
    "gen_ai.content.completion",  # From OpenLit project's format
    "traceloop.entity.output",  # From Traceloop's conventions
    "output",  # Generic fallback for Pydantic models - lowest priority
]

# USAGE_KEYS: Maps internal Weave usage metric names to their equivalent keys in
# various telemetry standards. Used for token counting and usage statistics.
# Used to populate the usage field of `summary_dump` in clickhouse
# The tuples represent handlers which the value should be passed through when found
# Never assume that the value is of a certain type or error, conventions provide no guarantees
USAGE_KEYS = {
    # Maps Weave's "prompt_tokens" to keys from different standards
    "input_tokens": [
        ("gen_ai.usage.input_tokens", try_parse_int),
    ],
    # Maps Weave's "completion_tokens" to keys from different standards
    "completion_tokens": [
        ("gen_ai.usage.output_tokens", try_parse_int),
    ],
    "prompt_tokens": [
        ("gen_ai.usage.prompt_tokens", try_parse_int),
        ("llm.token_count.prompt", try_parse_int),
        ("ai.usage.promptTokens", try_parse_int),  # Vercel
    ],
    # Maps Weave's "completion_tokens" to keys from different standards
    "completion_tokens": [
        ("gen_ai.usage.completion_tokens", try_parse_int),
        ("llm.token_count.completion", try_parse_int),
        ("ai.usage.completionTokens", try_parse_int),  # Vercel
    ],
    # Maps Weave's "total_tokens" to keys from different standards
    "total_tokens": [
        ("llm.usage.total_tokens", try_parse_int),
        ("llm.token_count.total", try_parse_int),
    ],
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
    "model": ["gen_ai.response.model", "llm.model_name", "ai.model.id"],
    # Provider/vendor of the model
    "provider": [
        "llm.provider",  # Common across standards
        "ai.model.provider",  # Vercel
    ],
    # Model generation parameters (temperature, max_tokens, etc.)
    "model_parameters": ["gen_ai.request", "llm.invocation_parameters"],
}

# WB_KEYS: Wandb/Weave specific attributes for enhanced visualization and reporting
WB_KEYS = {
    # Custom display name for the call in the UI
    "display_name": ["wandb.display_name"],
}

# These represent fields that are set by a provider which override top level span information
# Langfuse relies on these attributes to give the real start and end time for spans
SPAN_OVERRIDES = {
    "start_time": [("langfuse.startTime", try_parse_timestamp)],
    "end_time": [("langfuse.endTime", try_parse_timestamp)],
}
