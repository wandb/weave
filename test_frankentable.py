"""Frankentable test: sends Weave SDK traces + multi-turn OTel GenAI agent conversations.

Run with:
    devall uv run python test_frankentable.py
"""

import json
import os
import ssl
import time
import uuid

import requests
import weave


TRACE_SERVER_URL = os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345")
API_KEY = os.environ.get("WANDB_API_KEY", "")
ENTITY = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
PROJECT = "frankentable-test"

# Disable SSL verification for local dev
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["WANDB_INSECURE_DISABLE_SSL"] = "true"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""


# ---------------------------------------------------------------------------
# Part 1: Normal Weave SDK traces
# ---------------------------------------------------------------------------

@weave.op()
def summarize(text: str) -> str:
    """A simple user op that doesn't involve LLM calls."""
    return f"Summary of: {text[:50]}..."


@weave.op()
def process_document(doc_name: str, content: str) -> dict:
    """An outer op that calls a sub-op."""
    summary = summarize(content)
    return {"doc": doc_name, "summary": summary, "word_count": len(content.split())}


def send_weave_sdk_traces():
    """Send normal Weave @weave.op() traces — no GenAI, just function calls."""
    print("\n=== Part 1: Weave SDK traces (non-GenAI @weave.op) ===")
    try:
        weave.init(f"{ENTITY}/{PROJECT}")
        result = process_document(
            "quarterly_report.pdf",
            "Revenue grew 15% year over year driven by strong enterprise adoption.",
        )
        print(f"  process_document result: {result}")
        weave.finish()
        print("  Weave SDK traces sent.\n")
    except Exception as e:
        print(f"  Weave SDK failed (expected in some dev envs): {e}\n")
        try:
            weave.finish()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Part 2: OTel GenAI spans — multi-turn agent conversation
# ---------------------------------------------------------------------------

def _build_otel_conversation() -> bytes:
    """Build a multi-turn agent conversation with 2 turns, each with LLM + tool calls."""
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource
    from opentelemetry.proto.trace.v1.trace_pb2 import (
        ResourceSpans,
        ScopeSpans,
        Span,
        Status,
    )

    conv_id = f"conv-ft-{uuid.uuid4().hex[:8]}"
    now_ns = int(time.time() * 1e9)

    def kv(key: str, val: str | int | float) -> KeyValue:
        if isinstance(val, int):
            return KeyValue(key=key, value=AnyValue(int_value=val))
        elif isinstance(val, float):
            return KeyValue(key=key, value=AnyValue(double_value=val))
        return KeyValue(key=key, value=AnyValue(string_value=str(val)))

    def kv_json(key: str, items: list[dict]) -> KeyValue:
        return KeyValue(key=key, value=AnyValue(string_value=json.dumps(items)))

    resource = Resource(
        attributes=[
            kv("service.name", "frankentable-agent"),
            kv("wandb.project", PROJECT),
            kv("wandb.entity", ENTITY),
        ]
    )

    all_spans: list[Span] = []

    # ===== Turn 1: "What's the weather in Tokyo?" =====
    turn1_trace = uuid.uuid4().bytes

    # Agent root
    t1_agent_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=turn1_trace,
        span_id=t1_agent_id,
        name="invoke_agent TravelBot",
        kind=Span.SpanKind.SPAN_KIND_INTERNAL,
        start_time_unix_nano=now_ns - 5_000_000_000,
        end_time_unix_nano=now_ns - 3_000_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "invoke_agent"),
            kv("gen_ai.agent.name", "TravelBot"),
            kv("gen_ai.system", "openai"),
            kv("gen_ai.conversation.id", conv_id),
            kv("gen_ai.conversation.name", "Travel Planning"),
            kv("wandb.thread_id", conv_id),
        ],
    ))

    # LLM call
    t1_chat_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=turn1_trace,
        span_id=t1_chat_id,
        parent_span_id=t1_agent_id,
        name="chat gpt-4o",
        kind=Span.SpanKind.SPAN_KIND_CLIENT,
        start_time_unix_nano=now_ns - 4_800_000_000,
        end_time_unix_nano=now_ns - 4_000_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "chat"),
            kv("gen_ai.system", "openai"),
            kv("gen_ai.request.model", "gpt-4o"),
            kv("gen_ai.response.model", "gpt-4o-2024-08-06"),
            kv("gen_ai.usage.input_tokens", 128),
            kv("gen_ai.usage.output_tokens", 34),
            kv("gen_ai.request.temperature", 0.7),
            kv("gen_ai.request.max_tokens", 500),
            kv("gen_ai.conversation.id", conv_id),
            kv("wandb.thread_id", conv_id),
            kv_json("gen_ai.input.messages", [
                {"role": "system", "content": "You are TravelBot, a helpful travel planning assistant. Use tools to look up weather and flights."},
                {"role": "user", "content": "What's the weather like in Tokyo this week?"},
            ]),
            kv_json("gen_ai.output.messages", [
                {"role": "assistant", "content": "Let me check the weather in Tokyo for you."},
            ]),
        ],
    ))

    # Tool call: get_weather
    t1_tool_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=turn1_trace,
        span_id=t1_tool_id,
        parent_span_id=t1_agent_id,
        name="execute_tool get_weather",
        kind=Span.SpanKind.SPAN_KIND_INTERNAL,
        start_time_unix_nano=now_ns - 3_900_000_000,
        end_time_unix_nano=now_ns - 3_500_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "execute_tool"),
            kv("gen_ai.tool.name", "get_weather"),
            kv("gen_ai.tool.call.arguments", json.dumps({"city": "Tokyo", "days": 7})),
            kv("gen_ai.conversation.id", conv_id),
            kv("wandb.thread_id", conv_id),
        ],
    ))

    # ===== Turn 2: "Find me flights from SFO" =====
    turn2_trace = uuid.uuid4().bytes

    t2_agent_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=turn2_trace,
        span_id=t2_agent_id,
        name="invoke_agent TravelBot",
        kind=Span.SpanKind.SPAN_KIND_INTERNAL,
        start_time_unix_nano=now_ns - 2_500_000_000,
        end_time_unix_nano=now_ns - 500_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "invoke_agent"),
            kv("gen_ai.agent.name", "TravelBot"),
            kv("gen_ai.system", "openai"),
            kv("gen_ai.conversation.id", conv_id),
            kv("gen_ai.conversation.name", "Travel Planning"),
            kv("wandb.thread_id", conv_id),
        ],
    ))

    # LLM call for turn 2
    t2_chat_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=turn2_trace,
        span_id=t2_chat_id,
        parent_span_id=t2_agent_id,
        name="chat gpt-4o",
        kind=Span.SpanKind.SPAN_KIND_CLIENT,
        start_time_unix_nano=now_ns - 2_300_000_000,
        end_time_unix_nano=now_ns - 1_500_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "chat"),
            kv("gen_ai.system", "openai"),
            kv("gen_ai.request.model", "gpt-4o"),
            kv("gen_ai.response.model", "gpt-4o-2024-08-06"),
            kv("gen_ai.usage.input_tokens", 256),
            kv("gen_ai.usage.output_tokens", 67),
            kv("gen_ai.request.temperature", 0.7),
            kv("gen_ai.conversation.id", conv_id),
            kv("wandb.thread_id", conv_id),
            kv_json("gen_ai.input.messages", [
                {"role": "system", "content": "You are TravelBot, a helpful travel planning assistant."},
                {"role": "user", "content": "Great! Now find me flights from SFO to Tokyo next week."},
            ]),
            kv_json("gen_ai.output.messages", [
                {"role": "assistant", "content": "I'll search for flights from SFO to Tokyo. Let me check available options."},
            ]),
        ],
    ))

    # Tool call: search_flights
    t2_tool_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=turn2_trace,
        span_id=t2_tool_id,
        parent_span_id=t2_agent_id,
        name="execute_tool search_flights",
        kind=Span.SpanKind.SPAN_KIND_INTERNAL,
        start_time_unix_nano=now_ns - 1_400_000_000,
        end_time_unix_nano=now_ns - 800_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "execute_tool"),
            kv("gen_ai.tool.name", "search_flights"),
            kv("gen_ai.tool.call.arguments", json.dumps({"origin": "SFO", "destination": "NRT", "date": "2026-04-01"})),
            kv("gen_ai.conversation.id", conv_id),
            kv("wandb.thread_id", conv_id),
        ],
    ))

    # ===== Separate trace: standalone chat (no agent, no conversation) =====
    standalone_trace = uuid.uuid4().bytes
    standalone_id = uuid.uuid4().bytes[:8]
    all_spans.append(Span(
        trace_id=standalone_trace,
        span_id=standalone_id,
        name="chat claude-3.5-sonnet",
        kind=Span.SpanKind.SPAN_KIND_CLIENT,
        start_time_unix_nano=now_ns - 1_000_000_000,
        end_time_unix_nano=now_ns - 200_000_000,
        status=Status(code=Status.StatusCode.STATUS_CODE_OK),
        attributes=[
            kv("gen_ai.operation.name", "chat"),
            kv("gen_ai.system", "anthropic"),
            kv("gen_ai.request.model", "claude-3.5-sonnet"),
            kv("gen_ai.response.model", "claude-3-5-sonnet-20241022"),
            kv("gen_ai.usage.input_tokens", 89),
            kv("gen_ai.usage.output_tokens", 201),
            kv("gen_ai.request.temperature", 1.0),
            kv("gen_ai.request.max_tokens", 1024),
            kv_json("gen_ai.input.messages", [
                {"role": "user", "content": "Explain quantum computing in one paragraph."},
            ]),
            kv_json("gen_ai.output.messages", [
                {"role": "assistant", "content": "Quantum computing harnesses quantum mechanical phenomena like superposition and entanglement to process information in fundamentally different ways than classical computers. While classical bits exist as either 0 or 1, quantum bits (qubits) can exist in multiple states simultaneously, enabling quantum computers to explore many solutions in parallel."},
            ]),
        ],
    ))

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=resource,
                scope_spans=[ScopeSpans(spans=all_spans)],
            )
        ]
    )

    print(f"  Conversation ID: {conv_id}")
    print(f"  Turn 1 trace: {turn1_trace.hex()}")
    print(f"  Turn 2 trace: {turn2_trace.hex()}")
    print(f"  Standalone trace: {standalone_trace.hex()}")
    print(f"  Total spans: {len(all_spans)}")

    return request.SerializeToString()


def send_otel_genai_spans():
    """Send OTel GenAI spans."""
    print("=== Part 2: OTel GenAI spans (multi-turn agent + standalone chat) ===")

    payload = _build_otel_conversation()

    url = f"{TRACE_SERVER_URL}/otel/v1/traces"
    headers = {
        "Content-Type": "application/x-protobuf",
    }
    if API_KEY:
        headers["wandb-api-key"] = API_KEY

    resp = requests.post(url, data=payload, headers=headers)
    print(f"  POST {url} → {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Response: {resp.text[:500]}")
    else:
        print("  OTel spans sent successfully.")
    print()


# ---------------------------------------------------------------------------
# Part 3: Verify via direct ClickHouse query
# ---------------------------------------------------------------------------

def verify_via_clickhouse():
    """Query ClickHouse directly to verify GenAI columns are populated."""
    print("=== Part 3: Verifying via ClickHouse ===")
    time.sleep(1)

    try:
        resp = requests.get("http://localhost:8123/", params={
            "query": """
                SELECT
                    id, op_name, operation_name, provider_name, request_model,
                    input_tokens, output_tokens, agent_name, conversation_id,
                    tool_name, thread_id,
                    length(input_messages) as in_msgs,
                    length(output_messages) as out_msgs
                FROM default.calls_complete
                ORDER BY started_at DESC
                LIMIT 20
                FORMAT JSONEachRow
            """
        })

        if resp.status_code != 200:
            print(f"  ClickHouse query failed: {resp.status_code}")
            return

        lines = [l for l in resp.text.strip().split("\n") if l.strip()]
        print(f"  Found {len(lines)} calls in calls_complete:\n")

        for line in lines:
            row = json.loads(line)
            op = row.get("op_name", "?").split("/")[-1][:50]
            op_type = row.get("operation_name", "")
            model = row.get("request_model", "")
            provider = row.get("provider_name", "")
            agent = row.get("agent_name", "")
            conv = row.get("conversation_id", "")
            thread = row.get("thread_id", "")
            tool = row.get("tool_name", "")
            in_t = row.get("input_tokens", 0)
            out_t = row.get("output_tokens", 0)
            in_m = row.get("in_msgs", 0)
            out_m = row.get("out_msgs", 0)

            flags = []
            if op_type:
                flags.append(f"op={op_type}")
            if model:
                flags.append(f"model={model}")
            if provider:
                flags.append(f"provider={provider}")
            if agent:
                flags.append(f"agent={agent}")
            if conv:
                flags.append(f"conv={conv[:20]}")
            if thread:
                flags.append(f"thread={thread[:20]}")
            if tool:
                flags.append(f"tool={tool}")
            if in_t or out_t:
                flags.append(f"tokens={in_t}/{out_t}")
            if in_m or out_m:
                flags.append(f"msgs={in_m}/{out_m}")

            prefix = "  [GENAI]" if op_type else "  [CALL] "
            print(f"{prefix} {op}")
            if flags:
                print(f"          {', '.join(flags)}")

    except requests.ConnectionError:
        print("  Could not connect to ClickHouse at localhost:8123")


if __name__ == "__main__":
    print(f"Trace server: {TRACE_SERVER_URL}")
    print(f"Project: {ENTITY}/{PROJECT}\n")

    send_weave_sdk_traces()
    send_otel_genai_spans()
    verify_via_clickhouse()
