from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents.clickhouse import AgentQueryHandler
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanGroupDistributionSpec,
    AgentSpansQueryReq,
    AgentSpanValueRef,
    AgentTraceMessagesReq,
)
from weave.trace_server.trace_server_interface import FeedbackQueryRes


@dataclass
class _FakeQueryResult:
    column_names: list[str]
    result_rows: list[tuple[Any, ...]]


def test_group_distributions_are_hydrated_with_batched_queries() -> None:
    req = AgentSpansQueryReq(
        project_id="p1",
        group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        group_distributions=[
            AgentSpanGroupDistributionSpec(
                alias="score_distribution",
                value=AgentSpanValueRef(source="custom_attrs_float", key="score"),
                bins=2,
            ),
            AgentSpanGroupDistributionSpec(
                alias="latency_distribution",
                value=AgentSpanValueRef(source="custom_attrs_int", key="latency"),
                bins=3,
            ),
            AgentSpanGroupDistributionSpec(
                alias="env_distribution",
                value=AgentSpanValueRef(source="custom_attrs_string", key="env"),
                top_n=2,
            ),
            AgentSpanGroupDistributionSpec(
                alias="cached_distribution",
                value=AgentSpanValueRef(source="custom_attrs_bool", key="cached"),
                top_n=2,
            ),
        ],
    )
    grouped_row_columns = [
        "conversation_id",
        "span_count",
        "invocation_count",
        "conversation_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_duration_ms",
        "error_count",
        "agent_names",
        "agent_versions",
        "provider_names",
        "request_models",
        "conversation_names",
        "first_seen",
        "last_seen",
    ]
    results = [
        _FakeQueryResult(column_names=[], result_rows=[(1,)]),
        _FakeQueryResult(
            column_names=grouped_row_columns,
            result_rows=[
                (
                    "conv-a",
                    3,
                    0,
                    1,
                    0,
                    0,
                    0,
                    0,
                    [],
                    [],
                    [],
                    [],
                    [],
                    None,
                    None,
                )
            ],
        ),
        _FakeQueryResult(
            column_names=["group_key", "total_count"],
            result_rows=[("conv-a", 3)],
        ),
        _FakeQueryResult(
            column_names=[
                "group_key",
                "alias",
                "bucket_index",
                "bucket_min",
                "bucket_max",
                "count",
                "present_count",
            ],
            result_rows=[
                ("conv-a", "score_distribution", 0, 0.1, 0.5, 2, 2),
                ("conv-a", "latency_distribution", 0, 10.0, 20.0, 1, 1),
            ],
        ),
        _FakeQueryResult(
            column_names=["group_key", "alias", "value", "count", "present_count"],
            result_rows=[
                ("conv-a", "env_distribution", "prod", 2, 3),
                ("conv-a", "cached_distribution", "true", 1, 1),
            ],
        ),
        # Conversation grouping also triggers the bounded message-preview query.
        _FakeQueryResult(
            column_names=[
                "conversation_id",
                "first_input_messages",
                "last_output_messages",
            ],
            result_rows=[("conv-a", [], [])],
        ),
    ]
    calls: list[tuple[str, dict[str, Any]]] = []

    def query(sql: str, params: dict[str, Any]) -> _FakeQueryResult:
        calls.append((sql, params))
        return results.pop(0)

    handler = AgentQueryHandler(query, lambda req: FeedbackQueryRes(result=[]))

    res = handler.spans_query(req)

    assert len(calls) == 6
    assert not results

    numeric_params = calls[3][1]
    assert "score_distribution" in numeric_params.values()
    assert "latency_distribution" in numeric_params.values()

    categorical_params = calls[4][1]
    assert "env_distribution" in categorical_params.values()
    assert "cached_distribution" in categorical_params.values()

    group = res.groups[0]
    assert [bin.count for bin in group.distributions["score_distribution"].bins] == [2]
    assert [bin.count for bin in group.distributions["latency_distribution"].bins] == [
        1
    ]
    assert [
        (v.value, v.count) for v in group.distributions["env_distribution"].values
    ] == [("prod", 2)]
    assert [
        (v.value, v.count) for v in group.distributions["cached_distribution"].values
    ] == [("true", 1)]


def test_grouped_rows_hydrate_message_previews() -> None:
    """Conversation groupings get first/last message previews from a second,
    bounded query (scoped to the page's conversation_ids) — the main grouped
    query never reads the wide message columns.
    """
    req = AgentSpansQueryReq(
        project_id="p1",
        group_by=[AgentGroupByRef(source="column", key="conversation_id")],
    )
    grouped_row_columns = [
        "conversation_id",
        "span_count",
        "invocation_count",
        "conversation_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_duration_ms",
        "error_count",
        "agent_names",
        "agent_versions",
        "provider_names",
        "request_models",
        "conversation_names",
        "first_seen",
        "last_seen",
    ]
    results = [
        # count query
        _FakeQueryResult(column_names=[], result_rows=[(2,)]),
        # grouped list query — note: no message columns
        _FakeQueryResult(
            column_names=grouped_row_columns,
            result_rows=[
                ("conv-a", 3, 0, 1, 0, 0, 0, 0, [], [], [], [], [], None, None),
                ("conv-empty", 1, 0, 1, 0, 0, 0, 0, [], [], [], [], [], None, None),
            ],
        ),
        # bounded preview query, keyed by conversation_id. ClickHouse returns
        # Array(Tuple(role, content, finish_reason)); first span carries a
        # system + user prompt and the user text wins.
        _FakeQueryResult(
            column_names=[
                "conversation_id",
                "first_input_messages",
                "last_output_messages",
            ],
            result_rows=[
                (
                    "conv-a",
                    [("system", "be helpful", ""), ("user", "what is 2+2?", "")],
                    [("assistant", "It is 4.", "stop")],
                ),
                ("conv-empty", [], []),
            ],
        ),
    ]
    calls: list[str] = []

    def query(sql: str, params: dict[str, Any]) -> _FakeQueryResult:
        calls.append(sql)
        return results.pop(0)

    handler = AgentQueryHandler(query, lambda req: FeedbackQueryRes(result=[]))
    res = handler.spans_query(req)

    # 3 queries: count, grouped list, bounded preview.
    assert len(calls) == 3
    assert "conversation_id IN" in calls[2]
    # The main grouped list query must NOT touch the wide message columns.
    assert "input_messages" not in calls[1]
    assert "output_messages" not in calls[1]

    first, empty = res.groups
    assert first.first_message is not None
    assert first.first_message.role == "user_message"
    assert first.first_message.text == "what is 2+2?"
    assert first.last_message is not None
    assert first.last_message.role == "assistant_message"
    assert first.last_message.text == "It is 4."

    # No renderable text → no preview, so the UI falls back to the conversation id.
    assert empty.first_message is None
    assert empty.last_message is None


def test_trace_messages_maps_rows_to_normalized_messages() -> None:
    result = _FakeQueryResult(
        column_names=["role", "content", "ordered_at"],
        result_rows=[
            ("system", "be helpful", None),
            ("user", "hi", None),
            ("assistant", "hello", None),
        ],
    )
    calls: list[tuple[str, dict[str, Any]]] = []

    def query(sql: str, params: dict[str, Any]) -> _FakeQueryResult:
        calls.append((sql, params))
        return result

    handler = AgentQueryHandler(query, lambda req: FeedbackQueryRes(result=[]))

    res = handler.trace_messages(
        AgentTraceMessagesReq(project_id="p1", trace_id="t1", limit=100)
    )

    assert [(m.role, m.content) for m in res.messages] == [
        ("system", "be helpful"),
        ("user", "hi"),
        ("assistant", "hello"),
    ]
    assert len(calls) == 1
    assert "t1" in calls[0][1].values()
