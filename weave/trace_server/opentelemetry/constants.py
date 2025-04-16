INPUT_KEYS = {
    "value": [
        "weave.input",  # Weave
        "input.value",  # OpenInference
        "gen_ai.prompt",  # OpenTelemetry
        "mlflow.spanInputs",  # MLFlow
        "traceloop.entity.input"  # Traceloop
        "input",  # Pydantic - This must execute after checking input.value
    ],
    "type": [
        "input.mime_type",  # OpenInference
        "gen_ai.input.type",
    ],
}

OUTPUT_KEYS = {
    "value": [
        "weave.output",  # Weave
        "output.value",  # OpenInference
        "gen_ai.completion",  # OTEL Semconv
        "mlflow.spanOutputs",  # MLFlow
        "gen_ai.content.completion",  # OpenLit
        "traceloop.entity.output",  # Traceloop
        "output",  # Pydantic - This must execute after checking output.value
    ],
    "type": [
        "output.mime_type",  # OpenInference
        "gen_ai.output.type",  # OTEL Semconv
    ],
}

USAGE_KEYS = {
    "prompt_tokens": ["gen_ai.usage.prompt_tokens", "llm.token_count.prompt"],
    "completion_tokens": [
        "gen_ai.usage.completion_tokens",
        "llm.token_count.completion",
    ],
    "total_tokens": ["llm.usage.total_tokens", "llm.token_count.total"],
}

ATTRIBUTE_KEYS = {
    "system": [
        "gen_ai.system",
        "llm.system",  # OpenInference
    ],
    "kind": [
        "weave.span.kind",  # Weave
        "traceloop.span.kind",  # Traceloop
        "openinference.span.kind",  # OpenInference
    ],
    "model": ["llm.model_name", "gen_ai.response.model"],
    "provider": [
        "llm.provider",
    ],
    "model_parameters": ["gen_ai.request", "llm.invocation_parameters"],
}
