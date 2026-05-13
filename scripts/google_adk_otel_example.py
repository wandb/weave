"""Example: ship Google ADK OTel spans with the full Weave OTLv2 field set.

ADK already emits OpenTelemetry spans for ``invoke_agent``, ``execute_tool``
and the underlying LLM call, but its attributes don't fully cover the GenAI
semantic-convention superset Weave extracts into dedicated ClickHouse columns
(see ``weave/trace_server/agents/semconv.py``).

``weave.integrations.patch_google_adk()`` patches ADK's tracing entry points
so each emitted span carries the canonical ``gen_ai.*`` keys (and the
Weave-aligned ``gen_ai.tool.call.{arguments,result}`` translation of ADK's
``gcp.vertex.agent.*`` proprietary keys).

This script calls ``weave.init()`` to install Weave's OTLP HTTP exporter
against the GenAI ingest endpoint (``/agents/otel/v1/traces``), tees the
same spans into an in-memory exporter for local verification, drives ADK's
trace functions with realistic mock objects, and prints both the populated
columns and the URLs where the trace landed on Weave.

Run it with:

    uv venv --python 3.12 --clear
    source .venv/bin/activate
    uv pip install -e . 'google-adk>=1.17.0'
    export WANDB_API_KEY=...          # or run ``wandb login`` once
    python scripts/google_adk_otel_example.py

The default project is ``megatruong/adk-test``; override with the
``WEAVE_ADK_EXAMPLE_PROJECT`` env var.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

import weave

# Apply the patch *before* using ADK's tracing functions so the wrappers are
# in place. This mirrors what ``weave.init()`` does together with
# ``weave.integrations.patch_google_adk()``. The constants in the same import
# are the canonical keys we expect on each enriched span — pulled straight
# from ``weave/trace_server/agents/semconv.py`` so the example doubles as a
# contract test for the integration.
from weave.integrations.google_adk.google_adk_sdk import (
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_OUTPUT_TYPE,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_CHOICE_COUNT,
    GEN_AI_REQUEST_FREQUENCY_PENALTY,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_PRESENCE_PENALTY,
    GEN_AI_REQUEST_SEED,
    GEN_AI_REQUEST_STOP_SEQUENCES,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_RESPONSE_ID,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_CALL_RESULT,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_TOOL_DESCRIPTION,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_USAGE_REASONING_TOKENS,
    get_google_adk_patcher,
)
from weave.trace.urls import otel_traces_endpoint, project_weave_root_url
from weave.trace_server.opentelemetry.genai_extraction import extract_genai_span
from weave.trace_server.opentelemetry.python_spans import (
    Resource as WeaveResource,
)
from weave.trace_server.opentelemetry.python_spans import (
    Span as WeaveSpan,
)
from weave.trace_server.opentelemetry.python_spans import (
    SpanKind,
    Status,
    StatusCode,
)

EXPECTED_INVOKE_AGENT_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_REQUEST_MODEL,
}

EXPECTED_EXECUTE_TOOL_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_DESCRIPTION,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_RESULT,
}

EXPECTED_CALL_LLM_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_RESPONSE_ID,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_FREQUENCY_PENALTY,
    GEN_AI_REQUEST_PRESENCE_PENALTY,
    GEN_AI_REQUEST_SEED,
    GEN_AI_REQUEST_STOP_SEQUENCES,
    GEN_AI_REQUEST_CHOICE_COUNT,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_USAGE_REASONING_TOKENS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_OUTPUT_TYPE,
}


# --------------------------------------------------------------------------
# Mocks: shapes ADK's tracing functions actually inspect. Real ADK objects
# work the same way; mocking keeps the example self-contained and lets us
# exercise every branch without API credentials.
# --------------------------------------------------------------------------


@dataclass
class _Part:
    text: str | None = None
    function_call: Any = None
    function_response: Any = None
    inline_data: Any = None
    file_data: Any = None


@dataclass
class _Content:
    role: str
    parts: list[_Part]


@dataclass
class _FunctionDeclaration:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class _Tool:
    function_declarations: list[_FunctionDeclaration]

    def model_dump(self) -> dict[str, Any]:
        return {
            "function_declarations": [
                {
                    "name": fd.name,
                    "description": fd.description,
                    "parameters": fd.parameters,
                }
                for fd in self.function_declarations
            ]
        }


@dataclass
class _GenerateContentConfig:
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    stop_sequences: list[str] | None = None
    candidate_count: int | None = None
    system_instruction: Any = None
    tools: list[_Tool] | None = None

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_output_tokens": self.max_output_tokens,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "seed": self.seed,
                "stop_sequences": self.stop_sequences,
                "candidate_count": self.candidate_count,
            }.items()
            if v is not None
        }


@dataclass
class _LlmRequest:
    model: str
    contents: list[_Content]
    config: _GenerateContentConfig


@dataclass
class _UsageMetadata:
    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    thoughts_token_count: int | None = None
    cached_content_token_count: int | None = None
    cache_creation_token_count: int | None = None


@dataclass
class _FinishReason:
    value: str = "stop"


@dataclass
class _LlmResponse:
    content: _Content
    finish_reason: _FinishReason | None = None
    usage_metadata: _UsageMetadata | None = None
    response_id: str | None = None
    model_version: str | None = None

    def model_dump_json(self, **_: Any) -> str:
        return json.dumps({"response_id": self.response_id})


@dataclass
class _Session:
    id: str
    user_id: str = "demo-user"


@dataclass
class _InvocationContext:
    invocation_id: str
    session: _Session
    agent: Any = None


@dataclass
class _Agent:
    name: str
    description: str
    model: str = "gemini-2.0-flash"


@dataclass
class _BaseTool:
    name: str
    description: str
    custom_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _FunctionResponse:
    id: str
    name: str
    response: dict[str, Any]


@dataclass
class _FunctionResponseContent:
    parts: list[_Part]


@dataclass
class _FunctionResponseEvent:
    id: str
    content: _FunctionResponseContent


# --------------------------------------------------------------------------
# Sample data — chosen so every expected attribute has a non-empty value.
# --------------------------------------------------------------------------


SAMPLE_AGENT = _Agent(
    name="trip-planner",
    description="Helps users plan multi-city itineraries",
    model="gemini-2.0-flash",
)

SAMPLE_CTX = _InvocationContext(
    invocation_id="inv-abc-123",
    session=_Session(id="conv-xyz-456"),
    agent=SAMPLE_AGENT,
)

SAMPLE_TOOL = _BaseTool(
    name="get_weather",
    description="Look up current weather for a city",
)

SAMPLE_TOOL_ARGS = {"city": "Paris", "units": "metric"}

SAMPLE_FUNCTION_RESPONSE_EVENT = _FunctionResponseEvent(
    id="event-789",
    content=_FunctionResponseContent(
        parts=[
            _Part(
                function_response=_FunctionResponse(
                    id="call-001",
                    name="get_weather",
                    response={"temp_c": 18, "conditions": "cloudy"},
                )
            )
        ]
    ),
)

SAMPLE_LLM_REQUEST = _LlmRequest(
    model="gemini-2.0-flash",
    contents=[
        _Content(
            role="user",
            parts=[_Part(text="What's the weather in Paris and Tokyo?")],
        ),
        _Content(role="model", parts=[_Part(text="Let me check both cities.")]),
    ],
    config=_GenerateContentConfig(
        temperature=0.4,
        top_p=0.9,
        max_output_tokens=512,
        frequency_penalty=0.1,
        presence_penalty=0.2,
        seed=42,
        stop_sequences=["END"],
        candidate_count=1,
        system_instruction="You are a helpful travel planner.",
        tools=[
            _Tool(
                function_declarations=[
                    _FunctionDeclaration(
                        name="get_weather",
                        description="Look up current weather for a city",
                        parameters={
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                        },
                    )
                ]
            )
        ],
    ),
)

SAMPLE_LLM_RESPONSE = _LlmResponse(
    content=_Content(
        role="model",
        parts=[_Part(text="It's 18C and cloudy in Paris; 22C and sunny in Tokyo.")],
    ),
    finish_reason=_FinishReason(value="STOP"),
    usage_metadata=_UsageMetadata(
        prompt_token_count=120,
        candidates_token_count=42,
        thoughts_token_count=8,
        cached_content_token_count=15,
        cache_creation_token_count=5,
    ),
    response_id="resp-9988",
    model_version="gemini-2.0-flash-2025-01",
)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def _attribute_summary(span: Any) -> dict[str, Any]:
    """Return a JSON-safe attribute snapshot for an in-memory ReadableSpan."""
    attrs = dict(span.attributes or {})
    summary: dict[str, Any] = {}
    for k, v in attrs.items():
        if isinstance(v, str) and len(v) > 120:
            summary[k] = v[:117] + "..."
        else:
            summary[k] = v
    return summary


def _readable_to_weave_span(readable: Any) -> WeaveSpan:
    """Adapt an OTel SDK ReadableSpan to Weave's internal span shape.

    The trace server's extraction layer accepts the in-process ``WeaveSpan``
    that the OTLP proto path constructs at ingest; reusing it lets the
    example exercise the same code path as a real ``genai_otel_export``.
    """
    attrs = {
        k: list(v) if isinstance(v, tuple) else v
        for k, v in (readable.attributes or {}).items()
    }
    return WeaveSpan(
        resource=WeaveResource(attributes={}),
        name=readable.name,
        trace_id=hex(readable.context.trace_id)[2:].zfill(32),
        span_id=hex(readable.context.span_id)[2:].zfill(16),
        start_time_unix_nano=readable.start_time,
        end_time_unix_nano=readable.end_time,
        attributes=attrs,
        kind=SpanKind.CLIENT,
        status=Status(code=StatusCode.OK),
        events=[],
    )


def _format_extracted(title: str, readable: Any) -> str:
    """Render the dedicated Weave schema columns we expect to populate."""
    weave_span = _readable_to_weave_span(readable)
    row = extract_genai_span(weave_span, project_id="adk-example")
    fields = [
        ("operation_name", row.operation_name),
        ("provider_name", row.provider_name),
        ("agent_name", row.agent_name),
        ("agent_id", row.agent_id),
        ("agent_description", row.agent_description),
        ("conversation_id", row.conversation_id),
        ("request_model", row.request_model),
        ("response_model", row.response_model),
        ("response_id", row.response_id),
        ("input_tokens", row.input_tokens),
        ("output_tokens", row.output_tokens),
        ("reasoning_tokens", row.reasoning_tokens),
        ("cache_read_input_tokens", row.cache_read_input_tokens),
        ("cache_creation_input_tokens", row.cache_creation_input_tokens),
        ("tool_name", row.tool_name),
        ("tool_type", row.tool_type),
        ("tool_call_id", row.tool_call_id),
        ("tool_call_arguments", row.tool_call_arguments),
        ("tool_call_result", row.tool_call_result),
        ("request_temperature", row.request_temperature),
        ("request_top_p", row.request_top_p),
        ("request_max_tokens", row.request_max_tokens),
        ("request_frequency_penalty", row.request_frequency_penalty),
        ("request_presence_penalty", row.request_presence_penalty),
        ("request_seed", row.request_seed),
        ("request_stop_sequences", row.request_stop_sequences),
        ("request_choice_count", row.request_choice_count),
        ("finish_reasons", row.finish_reasons),
        ("output_type", row.output_type),
        ("input_messages", len(row.input_messages)),
        ("output_messages", len(row.output_messages)),
        ("system_instructions", row.system_instructions),
        ("tool_definitions_set", bool(row.tool_definitions)),
    ]
    lines = [f"## {title} — Weave schema columns"]
    for key, value in fields:
        rendered = value[:77] + "..." if isinstance(value, str) and len(value) > 80 else value
        if rendered not in ("", 0, 0.0, [], None, False):
            lines.append(f"    - {key} = {rendered!r}")
    return "\n".join(lines)


def _format_section(title: str, attrs: dict[str, Any], required: set[str]) -> str:
    rendered = [f"## {title}"]
    present = sorted(attrs.keys())
    rendered.append(f"  Attributes set ({len(present)}):")
    for key in present:
        value = attrs[key]
        rendered.append(f"    - {key} = {value!r}")
    missing = sorted(required - set(present))
    if missing:
        rendered.append(f"  MISSING required keys: {missing}")
    return "\n".join(rendered)


def _trace_id_hex(span: Any) -> str:
    return f"{span.context.trace_id:032x}"


def _span_id_hex(span: Any) -> str:
    return f"{span.context.span_id:016x}"


def main() -> None:
    project = os.environ.get("WEAVE_ADK_EXAMPLE_PROJECT", "megatruong/adk-test")

    # ``weave.init()`` installs the global OTel ``TracerProvider`` with a
    # ``BatchSpanProcessor`` pointing at the Weave GenAI ingest endpoint.
    # Spans from ADK's ``gcp.vertex.agent`` tracer ride this provider, so the
    # patched attributes land in the dedicated columns server-side.
    client = weave.init(project)
    entity_name = client.entity
    project_name = client.project

    provider = otel_trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        raise TypeError(
            "weave.init() did not install an OTel TracerProvider. Set "
            "WF_TRACE_SERVER_URL and WANDB_API_KEY, then re-run."
        )

    # Tee every span into an in-memory exporter so we can verify the wire
    # contents locally without round-tripping to the ingest endpoint.
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    patcher = get_google_adk_patcher()
    patched = patcher.attempt_patch()
    if not patched:
        raise RuntimeError(
            "Failed to patch google.adk.telemetry.tracing — is google-adk installed?"
        )

    try:
        from google.adk.telemetry.tracing import (
            trace_agent_invocation,
            trace_call_llm,
            trace_tool_call,
        )

        tracer = otel_trace.get_tracer("weave-adk-example")
        trace_ids: dict[str, str] = {}

        with tracer.start_as_current_span("invoke_agent trip-planner") as invoke_span:
            trace_agent_invocation(invoke_span, SAMPLE_AGENT, SAMPLE_CTX)
            trace_ids["invoke_agent"] = _trace_id_hex(invoke_span)

        with tracer.start_as_current_span("execute_tool get_weather") as tool_span:
            trace_tool_call(
                SAMPLE_TOOL,
                SAMPLE_TOOL_ARGS,
                SAMPLE_FUNCTION_RESPONSE_EVENT,
                error=None,
                span=tool_span,
            )
            trace_ids["execute_tool"] = _trace_id_hex(tool_span)

        with tracer.start_as_current_span("call_llm gemini-2.0-flash") as llm_span:
            trace_call_llm(
                SAMPLE_CTX,
                "event-llm-1",
                SAMPLE_LLM_REQUEST,
                SAMPLE_LLM_RESPONSE,
                span=llm_span,
            )
            trace_ids["call_llm"] = _trace_id_hex(llm_span)

        # ``force_flush`` blocks until every span has been handed to every
        # exporter, including the remote ``BatchSpanProcessor`` that ships to
        # the GenAI ingest endpoint.
        provider.force_flush()

        finished = exporter.get_finished_spans()
        spans_by_name = {span.name: span for span in finished}

        sections: list[str] = []
        all_missing: list[str] = []

        for title, span_name, expected in (
            ("invoke_agent span", "invoke_agent trip-planner", EXPECTED_INVOKE_AGENT_KEYS),
            ("execute_tool span", "execute_tool get_weather", EXPECTED_EXECUTE_TOOL_KEYS),
            ("call_llm span", "call_llm gemini-2.0-flash", EXPECTED_CALL_LLM_KEYS),
        ):
            span = spans_by_name.get(span_name)
            if span is None:
                sections.append(f"## {title}\n  ERROR: span not exported")
                all_missing.append(f"{title} (no span)")
                continue
            attrs = _attribute_summary(span)
            sections.append(_format_section(title, attrs, expected))
            missing = expected - set(attrs.keys())
            if missing:
                all_missing.append(f"{title} missing {sorted(missing)}")

        print("\n\n".join(sections))

        # Replay the spans through Weave's GenAI extractor so the example
        # demonstrates that each enriched attribute reaches its dedicated
        # ClickHouse column on the server side, not just the wire.
        print("\n\n" + "=" * 72)
        print("Spans replayed through extract_genai_span (server-side extraction):")
        print("=" * 72)
        for title, span_name in (
            ("invoke_agent", "invoke_agent trip-planner"),
            ("execute_tool", "execute_tool get_weather"),
            ("call_llm", "call_llm gemini-2.0-flash"),
        ):
            span = spans_by_name.get(span_name)
            if span is not None:
                print("\n" + _format_extracted(title, span))

        if all_missing:
            print("\n\nFAIL: incomplete OTLv2 coverage:")
            for entry in all_missing:
                print(f"  - {entry}")
            raise SystemExit(1)

        print(
            "\n\nOK: every expected OTLv2 attribute is populated on the relevant ADK span."
        )

        print("\n" + "=" * 72)
        print("Spans exported to Weave GenAI OTL v2 endpoint")
        print("=" * 72)
        print(f"  Endpoint:    {otel_traces_endpoint()}")
        print(f"  Project:     {entity_name}/{project_name}")
        print(f"  Project URL: {project_weave_root_url(entity_name, project_name)}")
        print(f"  Agents URL:  {project_weave_root_url(entity_name, project_name)}/agents")
        print("  Trace IDs (hex):")
        for span_kind, trace_id in trace_ids.items():
            print(f"    - {span_kind}: {trace_id}")
    finally:
        patcher.undo_patch()


if __name__ == "__main__":
    main()
