"""Unit tests for genai_extraction.py — OTel span → schema extraction.

Per griffin's review: the per-helper tests (TestExtractProvider,
TestExtractOperationName, etc.) duplicated what one comprehensive
`extract_genai_span` test already covers. Collapsed into a single
success-path test that exercises every extractor plus one error-status
test since that's a separate code path (Status object vs attributes).
"""

import base64
import datetime
import json
from typing import Any
from unittest.mock import MagicMock

from weave.trace_server.agents import semconv
from weave.trace_server.opentelemetry.genai_extraction import (
    extract_genai_span,
    strip_inline_blobs_from_span,
)
from weave.trace_server.opentelemetry.python_spans import (
    Resource,
    Span,
    SpanKind,
    Status,
    StatusCode,
)
from weave.trace_server.trace_server_interface import FileCreateRes, ObjCreateRes


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
            # Eval linkage
            "weave.eval.run_id": "eval-run-001",
            "weave.eval.predict_and_score_call_id": "pas-001",
            "weave.eval.kind": "agent",
            "weave.eval.row_digest": "row-digest-001",
            "weave.eval.example_id": "example-001",
            "weave.eval.trial_index": 2,
            "weave.eval.evaluation_name": "travel-bot-eval",
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
    assert result.eval_run_id == "eval-run-001"
    assert result.eval_predict_and_score_call_id == "pas-001"
    assert result.eval_kind == "agent"
    assert result.eval_row_digest == "row-digest-001"
    assert result.eval_example_id == "example-001"
    assert result.eval_trial_index == 2
    assert result.eval_evaluation_name == "travel-bot-eval"
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
    # structured parts are JSON-serialized into content
    parts = json.loads(result.output_messages[0].content)
    assert parts == [
        {"type": "reasoning", "content": "Let me think..."},
        {"type": "text", "content": "Done."},
    ]
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
    assert "weave.eval.run_id" not in result.custom_attrs_string
    assert "weave.eval.trial_index" not in result.custom_attrs_int

    # Raw dumps populated for debugging
    assert result.raw_span_dump != ""
    assert result.attributes_dump != ""


def test_extract_genai_span_defaults_missing_eval_trial_index() -> None:
    result = extract_genai_span(
        _make_span(attrs={"weave.eval.run_id": "eval-run-001"}),
        project_id="p1",
    )

    assert result.eval_run_id == "eval-run-001"
    # -1 is the ClickHouse storage sentinel for "unset" (the column can't hold
    # NULL ints). The read path (AgentSpanSchema) surfaces it to callers as None
    # -- see test_genai_agent_queries.test_eval_trial_index_unset_reads_as_none.
    assert result.eval_trial_index == -1


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


def test_multi_alias_extraction_recognises_every_form() -> None:
    """For any attribute with multiple OTel aliases, the extractor must
    populate its column from a span carrying the value under any recognised
    key — canonical weave.* form, primary OTel alias, or any parallel /
    historical alias. ``USAGE_REASONING_TOKENS`` is used here as a concrete
    example; the same contract applies to any multi-alias semconv attribute.
    """
    for key in semconv.USAGE_REASONING_TOKENS.lookup_keys:
        result = extract_genai_span(_make_span(attrs={key: 42}), project_id="p1")
        assert result.reasoning_tokens == 42, f"key {key!r} did not populate column"


def test_multi_alias_extraction_canonical_weave_key_wins() -> None:
    """When a span carries both the canonical weave.* key and parallel OTel
    aliases, the weave.* value wins (extractor probes lookup_keys in order).
    ``USAGE_REASONING_TOKENS`` is used here as a concrete example; the same
    contract applies to any multi-alias semconv attribute.
    """
    result = extract_genai_span(
        _make_span(
            attrs={
                semconv.USAGE_REASONING_TOKENS.key: 99,
                **dict.fromkeys(semconv.USAGE_REASONING_TOKENS.gen_ai_aliases, 10),
            }
        ),
        project_id="p1",
    )
    assert result.reasoning_tokens == 99


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


def _mock_trace_server() -> MagicMock:
    trace_server = MagicMock()
    trace_server.file_create = MagicMock(
        side_effect=lambda req: FileCreateRes(digest=f"digest_{req.name}")
    )
    # Auto-conversion publishes each converted blob as a weave object and embeds
    # its ref, so obj_create must be stubbed with a deterministic digest.
    trace_server.obj_create = MagicMock(return_value=ObjCreateRes(digest="obj_digest"))
    return trace_server


def test_strip_inline_blobs_then_extract_strips_base64() -> None:
    """After ``strip_inline_blobs_from_span``, inline base64 in messages is a ref.

    Mirrors the non-OTel calls path. The image field value becomes a compact
    weave object ref inside the JSON-serialized NormalizedMessage content.
    """
    b64 = base64.b64encode(b"a" * 12000).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"
    attrs = {
        "gen_ai.input.messages": json.dumps(
            [
                {
                    "role": "user",
                    "parts": [
                        {"type": "text", "content": "describe this"},
                        {"type": "image", "url": data_uri},
                    ],
                }
            ]
        )
    }
    trace_server = _mock_trace_server()
    span = _make_span(attrs=attrs)

    strip_inline_blobs_from_span(span, "p1", trace_server)
    result = extract_genai_span(span, project_id="p1")

    content = json.loads(result.input_messages[0].content)
    assert content[0] == {"type": "text", "content": "describe this"}
    assert content[1]["url"].startswith("weave-trace-internal:///p1/object/")
    assert content[1]["url"].endswith(":obj_digest")
    assert b64 not in result.input_messages[0].content
    assert trace_server.file_create.call_count == 2


def test_extract_genai_span_leaves_base64_without_strip_step() -> None:
    """Without the strip step, ``extract_genai_span`` leaves base64 inline."""
    b64 = base64.b64encode(b"a" * 12000).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"
    attrs = {
        "gen_ai.input.messages": json.dumps(
            [{"role": "user", "parts": [{"type": "image", "url": data_uri}]}]
        )
    }

    result = extract_genai_span(_make_span(attrs=attrs), project_id="p1")

    assert data_uri in result.input_messages[0].content


def test_extract_genai_span_preserves_multimodal_content_parts() -> None:
    """OpenAI-style list ``content`` (text + image) is preserved as a JSON parts
    array; non-text parts must not be dropped during normalization.
    """
    attrs = {
        "gen_ai.input.messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/x.png"},
                    },
                ],
            }
        ]
    }

    result = extract_genai_span(_make_span(attrs=attrs), project_id="p1")

    parts = json.loads(result.input_messages[0].content)
    assert parts == [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}},
    ]


def test_extract_genai_span_normalizes_indexed_prompt_dict() -> None:
    """Legacy ``gen_ai.prompt.{i}`` / ``gen_ai.completion.{i}`` unflatten to a
    numeric-keyed dict; it must be converted to a message list (as the
    non-agents path does) so input/output messages are populated.
    """
    attrs = {
        "gen_ai": {
            "prompt": {
                "0": {"role": "user", "content": "hello"},
                "1": {"role": "assistant", "content": "hi there"},
            },
            "completion": {"0": {"role": "assistant", "content": "done"}},
        }
    }

    result = extract_genai_span(_make_span(attrs=attrs), project_id="p1")

    assert [m.role for m in result.input_messages] == ["user", "assistant"]
    assert result.input_messages[0].content == "hello"
    assert result.input_messages[1].content == "hi there"
    assert [m.role for m in result.output_messages] == ["assistant"]
    assert result.output_messages[0].content == "done"


def test_ingest_flow_strips_base64_from_span_attribute_dumps() -> None:
    """Replicates AgentWriteHandler.insert_otel_spans: converting span.attributes
    before extraction strips base64 from the lossless attributes_dump /
    raw_span_dump columns (the OpenLLMetry ``gen_ai.prompt.{i}`` shape unflattens
    to a numeric-keyed dict with a structured content array).
    """
    b64 = base64.b64encode(b"a" * 15000).decode("ascii")
    attrs = {
        "gen_ai": {
            "prompt": {
                "0": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            }
        }
    }
    trace_server = _mock_trace_server()
    span = _make_span(attrs=attrs)

    # AgentWriteHandler strips inline blobs in place before extraction.
    strip_inline_blobs_from_span(span, "p1", trace_server)
    result = extract_genai_span(span, project_id="p1")

    assert b64 not in result.attributes_dump
    assert b64 not in result.raw_span_dump
    # Base64 is replaced by a compact weave object ref, not an inline object.
    assert "weave-trace-internal:///p1/object/" in result.attributes_dump
    assert "CustomWeaveType" not in result.attributes_dump
    assert trace_server.file_create.call_count == 2


def test_strip_inline_blobs_attributes_obj_create_to_wb_user_id() -> None:
    """The OTel agents path attributes converted Content objects to the caller.

    ``strip_inline_blobs_from_span``'s ``wb_user_id`` must reach the
    ``ObjSchemaForInsert`` used to publish each Content object via ``obj_create``.
    Here the base64 is buried inside a JSON-encoded ``gen_ai.input.messages``
    string, so the conversion happens on the message-payload pass
    (``_strip_message_attr`` -> ``replace_base64_in_raw_messages``).
    """
    b64 = base64.b64encode(b"a" * 12000).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"
    attrs = {
        "gen_ai.input.messages": json.dumps(
            [{"role": "user", "parts": [{"type": "image", "url": data_uri}]}]
        )
    }
    trace_server = _mock_trace_server()
    span = _make_span(attrs=attrs)

    strip_inline_blobs_from_span(span, "p1", trace_server, wb_user_id="u-9")

    assert trace_server.obj_create.call_count == 1
    obj_create_req = trace_server.obj_create.call_args.args[0]
    assert obj_create_req.obj.wb_user_id == "u-9"
