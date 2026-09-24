import datetime
import uuid
from typing import Any

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import get_field_by_name
from weave.trace_server.calls_query_builder.last_turn import LAST_TURN_FIELD
from weave.trace_server.project_version.types import CallsStorageServerMode


@pytest.fixture(params=[CallsStorageServerMode.OFF, CallsStorageServerMode.AUTO])
def last_turn_server(request, trace_server, ch_server):
    ch_server.table_routing_resolver._mode = request.param
    return trace_server


def _insert(server, inputs, output=None, *, attributes=None, summary=None, index=0):
    call_id = str(uuid.uuid4())
    started_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    started_at += datetime.timedelta(seconds=index)
    server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[
                tsi.CompletedCallSchemaForInsert(
                    project_id="shawn/test-project",
                    id=call_id,
                    trace_id=call_id,
                    op_name="chat",
                    started_at=started_at,
                    ended_at=started_at + datetime.timedelta(milliseconds=10),
                    attributes=attributes or {},
                    inputs=inputs,
                    output=output,
                    summary=summary or {},
                )
            ]
        )
    )
    return call_id


def _query(server, **kwargs):
    return list(
        server.calls_query_stream(
            tsi.CallsQueryReq(project_id="shawn/test-project", **kwargs)
        )
    )


def test_provider_projections(last_turn_server):
    examples: list[tuple[dict[str, Any], Any, dict[str, Any], str | None]] = [
        ({"messages": [{"role": "user", "content": "hello"}]}, None, {}, "hello"),
        (
            {"messages": [{"role": "assistant", "content": "last assistant"}]},
            None,
            {},
            "last assistant",
        ),
        (
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "one"},
                            {"type": "image_url", "image_url": {"url": "secret image"}},
                            {"type": "text", "text": "two"},
                        ],
                    }
                ]
            },
            None,
            {},
            "one\ntwo",
        ),
        ({"input": "responses input"}, {}, {}, "responses input"),
        (
            {
                "input": [
                    {"role": "user", "content": "before"},
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "responses text"}],
                    },
                    {"type": "reasoning", "summary": [{"text": "hidden"}]},
                ]
            },
            {},
            {},
            "responses text",
        ),
        (
            {
                "input": [
                    {
                        "type": "function_call",
                        "call_id": "1",
                        "name": "search",
                        "arguments": "{}",
                    },
                    {"type": "function_call_output", "call_id": "1", "output": "found"},
                ]
            },
            {},
            {},
            "search\n{}\nfound",
        ),
        ({"model": "gemini", "contents": "google input"}, {}, {}, "google input"),
        (
            {
                "model": "gemini",
                "contents": [{"role": "user", "parts": [{"text": "google parts"}]}],
            },
            {},
            {},
            "google parts",
        ),
        (
            {"self": {"model_name": "gemini"}, "contents": "legacy gemini"},
            {},
            {},
            "legacy gemini",
        ),
        (
            {
                "messages": [
                    [
                        {
                            "id": ["langchain", "HumanMessage"],
                            "kwargs": {"content": "first batch"},
                        }
                    ],
                    [
                        {
                            "id": ["langchain", "HumanMessage"],
                            "kwargs": {"content": "ignored batch"},
                        }
                    ],
                ]
            },
            {},
            {},
            "first batch",
        ),
        (
            {"prompt": "original"},
            {
                "messages": [
                    {"role": "system", "subtype": "init"},
                    {
                        "role": "assistant",
                        "content": [{"text": "agent output"}, {"thinking": "hidden"}],
                    },
                    {"role": "result", "result": "ignored result"},
                ]
            },
            {},
            "agent output",
        ),
        (
            {
                "history": [
                    {"role": "system", "subtype": "init"},
                    {"role": "user", "content": "agent history"},
                ]
            },
            {},
            {},
            "agent history",
        ),
        (
            {
                "gen_ai.input.messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "content": "otel text"}],
                    }
                ]
            },
            {},
            {"otel_span": {}},
            "otel text",
        ),
        (
            {
                "input.value": {
                    "messages": [{"role": "user", "content": "otel messages"}]
                }
            },
            {},
            {"otel_span": {}},
            "otel messages",
        ),
        ({"gen_ai.prompt": "otel string"}, {}, {"otel_span": {}}, "otel string"),
        ({"model": "gpt-image-1", "prompt": "draw a cat"}, {}, {}, "draw a cat"),
        ({"messages": []}, {}, {}, None),
        ({"messages": [{"role": "user", "content": ""}]}, {}, {}, None),
        (
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": "not text"}}
                        ],
                    }
                ]
            },
            {},
            {},
            None,
        ),
        ({"messages": "malformed"}, {}, {}, None),
        ({"arbitrary": "not chat"}, {}, {}, None),
        ({"messages": [], "system": "system only"}, {}, {}, "system only"),
        (
            {"input": [], "instructions": "instructions only"},
            {},
            {},
            "instructions only",
        ),
        (
            {"contents": [], "config": {"systemInstruction": "google system"}},
            {},
            {},
            "google system",
        ),
        (
            {"gen_ai.prompt": "first", "input.value": "second"},
            {},
            {"otel_span": {}},
            "first",
        ),
        (
            {
                "gcp.vertex.agent.llm_request": {
                    "contents": [{"role": "user", "parts": [{"text": "adk text"}]}]
                }
            },
            {},
            {"otel_span": {}},
            "adk text",
        ),
        (
            {"messages": [{"role": "user", "content": "café 猫 'quoted'\\path"}]},
            {},
            {},
            "café 猫 'quoted'\\path",
        ),
        ({"messages": [None, 42, {"content": "no role"}]}, {}, {}, None),
    ]
    examples.extend(
        [
            (
                {
                    "messages": [
                        {
                            "type": "function_call",
                            "call_id": "1",
                            "name": "search",
                            "arguments": "{}",
                        },
                        {
                            "type": "function_call_output",
                            "call_id": "1",
                            "output": "found",
                        },
                    ]
                },
                {},
                {},
                "search\n{}\nfound",
            ),
            ({"gen_ai.prompt": ["first", "last"]}, {}, {"otel_span": {}}, "last"),
            (
                {"gen_ai.prompt": []},
                {},
                {"otel_span": {}, "system": "otel system"},
                "otel system",
            ),
        ]
    )
    expected = {}
    for inputs, output, attributes, text in examples:
        call_id = _insert(last_turn_server, inputs, output, attributes=attributes)
        expected[call_id] = text
    calls = _query(last_turn_server, columns=["id", LAST_TURN_FIELD])
    assert {
        call.id: call.summary["weave"]["last_turn_text"] for call in calls
    } == expected
    assert [call.inputs for call in calls] == [{}] * len(expected)
    assert [call.output for call in calls] == [None] * len(expected)


def test_trailing_tool_interaction(last_turn_server):
    messages = [
        {
            "role": "assistant",
            "content": "do not include narration",
            "tool_calls": [
                {"id": "old", "function": {"name": "old_tool", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "old", "content": "old result"},
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "a", "function": {"name": "search", "arguments": '{"q":"cat"}'}},
                {"id": "b", "function": {"name": "lookup", "arguments": "{}"}},
            ],
        },
        {"role": "tool", "tool_call_id": "b", "content": "lookup result"},
        {"role": "tool", "tool_call_id": "a", "content": "search result"},
    ]
    call_id = _insert(last_turn_server, {"messages": messages})
    result = _query(last_turn_server, columns=[LAST_TURN_FIELD])
    assert [(c.id, c.summary["weave"]["last_turn_text"]) for c in result] == [
        (call_id, 'search\n{"q":"cat"}\nlookup\n{}\nlookup result\nsearch result')
    ]


def test_anthropic_tool_interaction(last_turn_server):
    _insert(
        last_turn_server,
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "a",
                            "name": "search",
                            "input": {"q": "cat"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "a",
                            "content": [{"type": "text", "text": "found"}],
                        }
                    ],
                },
            ]
        },
    )
    calls = _query(last_turn_server, columns=[LAST_TURN_FIELD])
    assert [c.summary["weave"]["last_turn_text"] for c in calls] == [
        'search\n{"q":"cat"}\nfound'
    ]


@pytest.mark.parametrize("include_costs", [False, True])
def test_filter_sort_and_paginate(last_turn_server, include_costs):
    ids = [
        _insert(
            last_turn_server, {"messages": [{"role": "user", "content": text}]}, index=i
        )
        for i, text in enumerate(["zulu", "beta", "alpha", ""])
    ]
    calls = _query(
        last_turn_server,
        columns=[LAST_TURN_FIELD],
        sort_by=[{"field": LAST_TURN_FIELD, "direction": "asc"}],
        limit=1,
        offset=1,
        include_costs=include_costs,
    )
    assert [(c.id, c.summary["weave"]["last_turn_text"]) for c in calls] == [
        (ids[1], "beta")
    ]
    calls = _query(
        last_turn_server,
        columns=["id"],
        sort_by=[{"field": "started_at", "direction": "asc"}],
        limit=1,
        include_costs=include_costs,
        query={
            "$expr": {
                "$contains": {
                    "input": {"$getField": LAST_TURN_FIELD},
                    "substr": {"$literal": "ALP"},
                    "case_insensitive": True,
                }
            }
        },
    )
    assert [c.id for c in calls] == [ids[2]]
    assert [c.summary["weave"].get("last_turn_text", "absent") for c in calls] == [
        "absent"
    ]
    calls = _query(
        last_turn_server,
        columns=["id"],
        sort_by=[{"field": LAST_TURN_FIELD, "direction": "desc"}],
        limit=1,
        include_costs=include_costs,
    )
    assert [c.id for c in calls] == [ids[0]]
    stats = last_turn_server.calls_query_stats(
        tsi.CallsQueryStatsReq(
            project_id="shawn/test-project",
            query={
                "$expr": {
                    "$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": "alpha"}]
                }
            },
        )
    )
    assert stats.count == 1
    null_calls = _query(
        last_turn_server,
        columns=[LAST_TURN_FIELD],
        query={"$expr": {"$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": None}]}},
    )
    assert [(c.id, c.summary["weave"]["last_turn_text"]) for c in null_calls] == [
        (ids[3], None)
    ]


def test_default_projection_is_unchanged(last_turn_server):
    _insert(
        last_turn_server,
        {"messages": [{"role": "user", "content": "hello"}]},
        summary={"weave": {"last_turn_text": "stale stored value"}},
    )
    calls = _query(last_turn_server)
    assert [c.summary["weave"] for c in calls] == [
        {"status": "success", "trace_name": "chat", "latency_ms": 10}
    ]
    calls = _query(last_turn_server, columns=["summary", LAST_TURN_FIELD])
    assert [c.summary["weave"]["last_turn_text"] for c in calls] == ["hello"]


def test_last_turn_is_heavy():
    assert get_field_by_name(LAST_TURN_FIELD).is_heavy() is True
    assert get_field_by_name("summary.weave.latency_ms").is_heavy() is False


def test_agent_output_from_separate_call_parts(trace_server, ch_server):
    ch_server.table_routing_resolver._mode = CallsStorageServerMode.OFF
    start = tsi.StartedCallSchemaForInsert(
        project_id="shawn/test-project",
        op_name="agent",
        started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        attributes={},
        inputs={"prompt": "original"},
    )
    call = trace_server.call_start(tsi.CallStartReq(start=start))
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=start.project_id,
                id=call.id,
                ended_at=start.started_at + datetime.timedelta(seconds=1),
                output={
                    "messages": [
                        {"role": "system", "subtype": "init"},
                        {"role": "assistant", "content": [{"text": "final answer"}]},
                    ]
                },
                summary={},
            )
        )
    )
    calls = _query(
        trace_server,
        columns=["inputs", "output", "summary", LAST_TURN_FIELD],
        query={
            "$expr": {
                "$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": "final answer"}]
            }
        },
    )
    assert [(c.id, c.inputs, c.summary["weave"]["last_turn_text"]) for c in calls] == [
        (call.id, {"prompt": "original"}, "final answer")
    ]
