"""Unit tests for genai_extraction.py — OTel span → schema extraction.

Per griffin's review: the per-helper tests (TestExtractProvider,
TestExtractOperationName, etc.) duplicated what one comprehensive
`extract_genai_span` test already covers. Collapsed into a single
success-path test that exercises every extractor plus one error-status
test since that's a separate code path (Status object vs attributes).
"""

import datetime
from typing import Any

from weave.trace_server.opentelemetry.genai_extraction import extract_genai_span
from weave.trace_server.opentelemetry.python_spans import (
    Resource,
    Span,
    SpanKind,
    Status,
    StatusCode,
)


def _make_span(
    attrs: dict[str, Any] | None = None,
    name: str = "test-span",
    events: list | None = None,
    status: Status | None = None,
) -> Span:
    """Build a minimal Span for testing."""
    now_ns = int(datetime.datetime.now().timestamp() * 1_000_000_000)
    return Span(
        resource=Resource(attributes={}),
        name=name,
        trace_id="abc123",
        span_id="def456",
        start_time_unix_nano=now_ns,
        end_time_unix_nano=now_ns + 100_000_000,
        attributes=attrs or {},
        kind=SpanKind.CLIENT,
        status=status or Status(code=StatusCode.OK),
        events=events or [],
    )


def test_extract_genai_span_comprehensive() -> None:
    """One span that exercises every extractor: chat/tool/agent fields,
    weave vs gen_ai precedence, tokens + total computation, messages,
    finish reasons, custom attrs (str/int/float), weave extensions
    (compaction, content_refs), reasoning content, and raw dumps.
    """
    span = _make_span(
        name="invoke_agent travel-bot",
        attrs={
            # Provider / operation / agent — weave.* wins over gen_ai.*
            "weave.provider.name": "openai",
            "gen_ai.provider.name": "ignored",
            "weave.operation.name": "invoke_agent",
            "weave.agent.name": "travel-bot",
            "gen_ai.agent.id": "agent-001",
            "gen_ai.agent.version": "1.2.3",
            "gen_ai.conversation.id": "conv-abc",
            "weave.conversation.name": "My Chat",
            # Model + tokens
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.response.model": "gpt-4o-2024-05-13",
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 50,
            "weave.usage.reasoning_tokens": 30,
            "gen_ai.response.finish_reasons": ["stop"],
            "gen_ai.request.temperature": 0.7,
            # Not promoted yet; these should fall through to custom attrs.
            "gen_ai.request.top_k": 40,
            "gen_ai.request.encoding_formats": ["float"],
            "gen_ai.data_source.id": "ds-1",
            "gen_ai.retrieval.query.text": "Paris weather",
            # Messages (normalized)
            "gen_ai.input.messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Plan my trip."},
            ],
            "gen_ai.output.messages": [
                {
                    "role": "assistant",
                    "parts": [
                        {"type": "reasoning", "content": "Let me think..."},
                        {"type": "text", "content": "Done."},
                    ],
                    "finish_reason": "stop",
                },
            ],
            # Tool call fields (would normally be on an execute_tool span; here
            # just verifying extraction populates the columns)
            "gen_ai.tool.name": "get_weather",
            "gen_ai.tool.type": "function",
            "gen_ai.tool.call.id": "call_123",
            "weave.tool.call.arguments": '{"city": "Paris"}',
            "weave.tool.call.result": '{"temp": 20}',
            # Weave extensions
            "weave.compaction.summary": "Summarized 10 items",
            "weave.compaction.items_before": 10,
            "weave.compaction.items_after": 3,
            "weave.content_refs": ["ref1", "ref2"],
            # Custom attrs spill to typed maps
            "my.custom.string": "hello",
            "my.custom.int": 42,
            "my.custom.float": 3.14,
        },
    )
    result = extract_genai_span(
        span, project_id="proj-1", wb_user_id="user-1", wb_run_id="run-1"
    )

    # Project metadata
    assert result.project_id == "proj-1"
    assert result.wb_user_id == "user-1"
    assert result.wb_run_id == "run-1"
    assert result.status_code == "OK"

    # weave.* beats gen_ai.*
    assert result.provider_name == "openai"
    assert result.operation_name == "invoke_agent"
    assert result.agent_name == "travel-bot"
    assert result.conversation_name == "My Chat"

    # Other gen_ai.* fields pass through
    assert result.agent_id == "agent-001"
    assert result.agent_version == "1.2.3"
    assert result.conversation_id == "conv-abc"
    assert result.request_model == "gpt-4o"
    assert result.response_model == "gpt-4o-2024-05-13"
    assert result.request_temperature == 0.7

    # Token usage
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.reasoning_tokens == 30

    assert result.finish_reasons == ["stop"]

    # Messages normalized from dicts to typed schemas
    assert len(result.input_messages) == 2
    assert result.input_messages[0].role == "system"
    assert result.input_messages[1].role == "user"
    # parts concatenate into content; finish_reason passes through
    assert result.output_messages[0].content == "Let me think...\nDone."
    assert result.output_messages[0].finish_reason == "stop"

    # Reasoning content extracted from output message parts
    assert "Let me think" in result.reasoning_content

    # Tool call
    assert result.tool_name == "get_weather"
    assert result.tool_type == "function"
    assert result.tool_call_id == "call_123"
    assert result.tool_call_arguments == '{"city": "Paris"}'
    assert result.tool_call_result == '{"temp": 20}'

    # Weave extensions
    assert result.compaction_summary == "Summarized 10 items"
    assert result.compaction_items_before == 10
    assert result.compaction_items_after == 3
    assert result.content_refs == ["ref1", "ref2"]

    # Custom attrs spill into typed maps
    assert result.custom_attrs_string["my.custom.string"] == "hello"
    assert result.custom_attrs_int["my.custom.int"] == 42
    assert result.custom_attrs_float["my.custom.float"] == 3.14
    assert result.custom_attrs_int["gen_ai.request.top_k"] == 40
    assert result.custom_attrs_string["gen_ai.request.encoding_formats"] == '["float"]'
    assert result.custom_attrs_string["gen_ai.data_source.id"] == "ds-1"
    assert result.custom_attrs_string["gen_ai.retrieval.query.text"] == "Paris weather"

    # Raw dumps populated for debugging
    assert result.raw_span_dump != ""
    assert result.attributes_dump != ""


def test_extract_genai_span_error_status() -> None:
    """ERROR status code comes from the Span's Status object, not attributes —
    different code path than the OK case.
    """
    span = _make_span(
        attrs={"error.type": "RateLimitError"},
        status=Status(code=StatusCode.ERROR, message="rate limited"),
    )
    result = extract_genai_span(span, project_id="p1")

    assert result.status_code == "ERROR"
    assert result.status_message == "rate limited"
    assert result.error_type == "RateLimitError"


def test_extract_genai_span_preserves_unset_status() -> None:
    span = _make_span(status=Status(code=StatusCode.UNSET))
    result = extract_genai_span(span, project_id="p1")

    assert result.status_code == "UNSET"


def test_normalize_message_missing_role_and_finish_reason() -> None:
    span = _make_span(
        attrs={
            "gen_ai.output.messages": [
                {"content": "hello", "finish_reason": None},
            ],
        },
    )
    result = extract_genai_span(span, project_id="p1")

    assert result.output_messages[0].role == "assistant"
    assert result.output_messages[0].finish_reason == ""


def test_normalize_input_messages_without_role_uses_user_role() -> None:
    result = extract_genai_span(
        _make_span(
            attrs={
                "gen_ai.input.messages": [
                    "plain prompt",
                    {"content": "structured prompt"},
                ],
            },
        ),
        project_id="p1",
    )

    assert [(m.role, m.content) for m in result.input_messages] == [
        ("user", "plain prompt"),
        ("user", "structured prompt"),
    ]


def test_genai_prompt_attr_becomes_user_message() -> None:
    result = extract_genai_span(
        _make_span(attrs={"gen_ai.prompt": "hello"}),
        project_id="p1",
    )

    assert [(m.role, m.content) for m in result.input_messages] == [("user", "hello")]
    assert result.custom_attrs_string["gen_ai.prompt"] == "hello"


def test_system_instructions_support_json_blocks() -> None:
    result = extract_genai_span(
        _make_span(
            attrs={
                "gen_ai.system_instructions": [
                    {"content": "content instruction"},
                    {"text": "text instruction"},
                    "plain instruction",
                ],
            }
        ),
        project_id="p1",
    )

    assert result.system_instructions == [
        "content instruction",
        "text instruction",
        "plain instruction",
    ]


def test_extract_custom_attrs_caps_total_entries() -> None:
    """A span with more than MAX_CUSTOM_ATTRS_PER_SPAN attributes has the
    excess silently dropped so a single misbehaving client can't blow up the
    insert.
    """
    from weave.trace_server.agents.constants import MAX_CUSTOM_ATTRS_PER_SPAN

    attrs = {
        f"lorem.key_{i:05d}": f"val_{i}" for i in range(MAX_CUSTOM_ATTRS_PER_SPAN + 500)
    }
    result = extract_genai_span(_make_span(attrs=attrs), project_id="p1")

    total = (
        len(result.custom_attrs_string)
        + len(result.custom_attrs_int)
        + len(result.custom_attrs_float)
    )
    assert total == MAX_CUSTOM_ATTRS_PER_SPAN


def test_extract_custom_attrs_skips_empty_strings() -> None:
    result = extract_genai_span(
        _make_span(attrs={"lorem.empty": "", "lorem.nonempty": "x"}),
        project_id="p1",
    )

    assert "lorem.empty" not in result.custom_attrs_string
    assert result.custom_attrs_string["lorem.nonempty"] == "x"


def test_extract_custom_attrs_truncates_large_string_values() -> None:
    """String values larger than MAX_CUSTOM_ATTR_VALUE_CHARS are truncated
    with a marker suffix so downstream tools can tell truncation happened.
    """
    from weave.trace_server.agents.constants import MAX_CUSTOM_ATTR_VALUE_CHARS

    huge = "x" * (MAX_CUSTOM_ATTR_VALUE_CHARS + 50_000)
    result = extract_genai_span(
        _make_span(attrs={"lorem.big_string": huge}),
        project_id="p1",
    )

    stored = result.custom_attrs_string["lorem.big_string"]
    assert len(stored) <= MAX_CUSTOM_ATTR_VALUE_CHARS
    assert stored.endswith("chars]")
    assert "truncated from" in stored


def test_extract_custom_attrs_truncates_large_json_values() -> None:
    """Non-primitive, non-dict values (e.g. lists) get JSON-encoded then
    truncated the same way. Dicts get flattened by `_flatten_attrs` so
    they never hit the JSON-encoding branch.
    """
    from weave.trace_server.agents.constants import MAX_CUSTOM_ATTR_VALUE_CHARS

    huge_list = ["x" * 100] * 5000  # JSON encoding ~500KB
    result = extract_genai_span(
        _make_span(attrs={"lorem.big_list": huge_list}),
        project_id="p1",
    )

    stored = result.custom_attrs_string["lorem.big_list"]
    assert len(stored) <= MAX_CUSTOM_ATTR_VALUE_CHARS
    assert "truncated from" in stored


def test_extract_custom_attrs_routes_bool_to_bool_map() -> None:
    """Bool values land in custom_attrs_bool, not custom_attrs_string or
    custom_attrs_int.

    Ordering matters: Python `bool` is a subclass of `int`, so the
    extractor's bool check must come before the int check (otherwise
    `isinstance(True, int)` matches first and the value ends up in
    custom_attrs_int).
    """
    result = extract_genai_span(
        _make_span(
            attrs={
                "lorem.is_active": True,
                "lorem.is_cached": False,
                "lorem.int_looks_like_bool": 1,
            }
        ),
        project_id="p1",
    )

    assert result.custom_attrs_bool["lorem.is_active"] is True
    assert result.custom_attrs_bool["lorem.is_cached"] is False
    # A plain int stays in custom_attrs_int even though 0/1 look bool-ish.
    assert result.custom_attrs_int["lorem.int_looks_like_bool"] == 1
    # Bools don't leak into the other maps.
    assert "lorem.is_active" not in result.custom_attrs_string
    assert "lorem.is_active" not in result.custom_attrs_int
    assert "lorem.is_active" not in result.custom_attrs_float


def test_extract_custom_attrs_skips_non_finite_floats() -> None:
    """NaN and +/-Inf must not reach custom_attrs_float — they break JSON
    serialization and have no aggregation semantics.
    """
    result = extract_genai_span(
        _make_span(
            attrs={
                "lorem.nan": float("nan"),
                "lorem.pos_inf": float("inf"),
                "lorem.neg_inf": float("-inf"),
                "lorem.finite": 3.14,
            }
        ),
        project_id="p1",
    )

    assert "lorem.finite" in result.custom_attrs_float
    assert result.custom_attrs_float["lorem.finite"] == 3.14
    for key in ("lorem.nan", "lorem.pos_inf", "lorem.neg_inf"):
        assert key not in result.custom_attrs_float
        assert key not in result.custom_attrs_string
        assert key not in result.custom_attrs_int
