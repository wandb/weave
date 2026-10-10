import datetime
import json
import uuid
from pathlib import Path

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


def test_frontend_parity(last_turn_server):
    fixtures = json.loads(
        (Path(__file__).parent / "fixtures" / "last_turn_frontend.json").read_text()
    )["cases"]
    expected = {}
    names = {}
    for fixture in fixtures:
        call = (
            json.loads(fixture["raw_call"])
            if "raw_call" in fixture
            else fixture["call"]
        )
        call_id = _insert(
            last_turn_server,
            call["inputs"],
            call["output"],
            attributes=call["attributes"],
        )
        expected[call_id] = fixture["expected"]
        names[call_id] = fixture["name"]
    calls = _query(last_turn_server, columns=["id", LAST_TURN_FIELD])
    assert {
        names[call.id]: call.summary["weave"]["last_turn_text"] for call in calls
    } == {names[call_id]: text for call_id, text in expected.items()}
    assert [call.inputs for call in calls] == [{}] * len(expected)
    assert [call.output for call in calls] == [None] * len(expected)
    filtered = _query(
        last_turn_server,
        columns=["id", LAST_TURN_FIELD],
        query={
            "$expr": {
                "$contains": {
                    "input": {"$getField": LAST_TURN_FIELD},
                    "substr": {"$literal": "found"},
                }
            }
        },
    )
    assert {call.id: call.summary["weave"]["last_turn_text"] for call in filtered} == {
        call_id: text
        for call_id, text in expected.items()
        if text is not None and "found" in text
    }
    sorted_calls = _query(
        last_turn_server,
        columns=["id", LAST_TURN_FIELD],
        sort_by=[{"field": LAST_TURN_FIELD, "direction": "asc"}],
    )
    assert [call.summary["weave"]["last_turn_text"] for call in sorted_calls] == sorted(
        expected.values(), key=lambda value: (value is None, value or "")
    )
    stats = last_turn_server.calls_query_stats(
        tsi.CallsQueryStatsReq(
            project_id="shawn/test-project",
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": LAST_TURN_FIELD},
                        {"$literal": '{"value":100000000000000000000}'},
                    ]
                }
            },
        )
    )
    assert stats.count == 1


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
        output={},
    )
    calls = _query(last_turn_server, columns=[LAST_TURN_FIELD])
    assert [c.summary["weave"]["last_turn_text"] for c in calls] == [
        'search\n{"q":"cat"}\nfound'
    ]


@pytest.mark.parametrize("include_costs", [False, True])
def test_filter_sort_and_paginate(last_turn_server, include_costs):
    ids = [
        _insert(
            last_turn_server,
            {"category": "chat", "messages": [{"role": "user", "content": text}]},
            index=i,
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
                "$and": [
                    {"$eq": [{"$getField": "inputs.category"}, {"$literal": "chat"}]},
                    {
                        "$contains": {
                            "input": {"$getField": LAST_TURN_FIELD},
                            "substr": {"$literal": "ALP"},
                            "case_insensitive": True,
                        }
                    },
                ]
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
        include_costs=include_costs,
        limit=1,
        query={"$expr": {"$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": None}]}},
    )
    assert [(c.id, c.summary["weave"]["last_turn_text"]) for c in null_calls] == [
        (ids[3], None)
    ]
    assert (
        _query(
            last_turn_server,
            columns=[LAST_TURN_FIELD],
            include_costs=include_costs,
            limit=1,
            query={
                "$expr": {
                    "$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": "absent"}]
                }
            },
        )
        == []
    )


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


def test_staged_mixed_filters_and_pagination(last_turn_server):
    ids = [
        _insert(
            last_turn_server,
            {
                "score": score,
                "expected": expected,
                "messages": [{"role": "user", "content": text}],
            },
            index=index,
        )
        for index, (text, score, expected) in enumerate(
            [("alpha", 30, "alpha"), ("beta", 20, "different"), ("gamma", 10, "gamma")]
        )
    ]
    calls = _query(
        last_turn_server,
        columns=[LAST_TURN_FIELD],
        sort_by=[{"field": "inputs.score", "direction": "asc"}],
        limit=1,
        offset=1,
    )
    assert [(c.id, c.summary["weave"]["last_turn_text"]) for c in calls] == [
        (ids[1], "beta")
    ]
    query = {
        "$expr": {
            "$or": [
                {"$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": "alpha"}]},
                {
                    "$and": [
                        {"$gt": [{"$getField": "inputs.score"}, {"$literal": 15}]},
                        {
                            "$not": [
                                {
                                    "$eq": [
                                        {"$getField": LAST_TURN_FIELD},
                                        {"$literal": "gamma"},
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        }
    }
    calls = _query(
        last_turn_server,
        columns=["id"],
        query=query,
        sort_by=[
            {"field": "inputs.score", "direction": "asc"},
            {"field": LAST_TURN_FIELD, "direction": "desc"},
        ],
        limit=1,
        offset=1,
    )
    assert [c.id for c in calls] == [ids[0]]
    assert (
        last_turn_server.calls_query_stats(
            tsi.CallsQueryStatsReq(project_id="shawn/test-project", query=query)
        ).count
        == 2
    )
    calls = _query(
        last_turn_server,
        columns=["id"],
        query={
            "$expr": {
                "$eq": [
                    {"$getField": LAST_TURN_FIELD},
                    {"$getField": "inputs.expected"},
                ]
            }
        },
    )
    assert {c.id for c in calls} == {ids[0], ids[2]}
    calls = _query(
        last_turn_server,
        columns=[LAST_TURN_FIELD],
        query={
            "$expr": {"$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": "absent"}]}
        },
    )
    assert calls == []


def test_staged_feedback_deduplication(last_turn_server):
    call_id = _insert(
        last_turn_server, {"messages": [{"role": "user", "content": "alpha"}]}
    )
    for user in ("alice", "bob"):
        last_turn_server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id="shawn/test-project",
                weave_ref=f"weave:///shawn/test-project/call/{call_id}",
                feedback_type="wandb.reaction.1",
                payload={"emoji": "👍"},
                wb_user_id=user,
            )
        )
    query = {
        "$expr": {
            "$or": [
                {"$eq": [{"$getField": LAST_TURN_FIELD}, {"$literal": "alpha"}]},
                {
                    "$eq": [
                        {"$getField": "feedback.[wandb.reaction.1].payload.emoji"},
                        {"$literal": "👍"},
                    ]
                },
            ]
        }
    }
    calls = _query(
        last_turn_server,
        columns=[LAST_TURN_FIELD],
        query=query,
        sort_by=[{"field": LAST_TURN_FIELD, "direction": "asc"}],
    )
    assert [(c.id, c.summary["weave"]["last_turn_text"]) for c in calls] == [
        (call_id, "alpha")
    ]
    assert (
        last_turn_server.calls_query_stats(
            tsi.CallsQueryStatsReq(project_id="shawn/test-project", query=query)
        ).count
        == 1
    )
