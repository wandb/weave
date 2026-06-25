from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents.clickhouse import AgentQueryHandler
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanGroupDistributionSpec,
    AgentSpansQueryReq,
    AgentSpanValueRef,
    AgentTraceMessagesReq,
    AgentTraceMessagesRes,
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

    # 3 queries: count, grouped list, bounded preview. The grouped list query
    # never reads the wide message columns; the preview is scoped by conversation_id.
    assert len(calls) == 3
    assert calls[1] == (
        "\n        SELECT s.conversation_id AS conversation_id,\n"
        "               count() AS span_count,\n"
        "               countIf(s.operation_name = 'invoke_agent') AS invocation_count,\n"
        "               uniqExact(s.conversation_id) AS conversation_count,\n"
        "               sum(s.input_tokens) AS total_input_tokens,\n"
        "               sum(s.cache_creation_input_tokens) AS total_cache_creation_input_tokens,\n"
        "               sum(s.cache_read_input_tokens) AS total_cache_read_input_tokens,\n"
        "               sum(s.output_tokens) AS total_output_tokens,\n"
        "               sum(s.reasoning_tokens) AS total_reasoning_tokens,\n"
        "               sum(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS total_duration_ms,\n"
        "               countIf(s.status_code = 'ERROR') AS error_count,\n"
        "               groupUniqArray(s.agent_name) AS agent_names,\n"
        "               groupUniqArray(s.agent_version) AS agent_versions,\n"
        "               groupUniqArray(s.provider_name) AS provider_names,\n"
        "               groupUniqArray(s.request_model) AS request_models,\n"
        "               groupUniqArray(s.conversation_name) AS conversation_names,\n"
        "               min(s.started_at) AS first_seen,\n"
        "               max(s.started_at) AS last_seen\n"
        "        FROM (\n"
        "  SELECT * EXCEPT (agent_name, agent_version, agent_id, conversation_id, has_own_agent_identity, fb_agent_identity, fb_conversation_id),\n"
        "    if(has_own_agent_identity, agent_name, fb_agent_identity.1) AS agent_name,\n"
        "    if(has_own_agent_identity, agent_version, fb_agent_identity.2) AS agent_version,\n"
        "    if(has_own_agent_identity, agent_id, fb_agent_identity.3) AS agent_id,\n"
        "    if(conversation_id != '', conversation_id, fb_conversation_id) AS conversation_id\n"
        "  FROM (\n"
        "    SELECT s0.*, (s0.agent_name != '') AS has_own_agent_identity, tf.fb_agent_identity, tf.fb_conversation_id\n"
        "    FROM spans s0\n"
        "    LEFT JOIN (\n"
        "      SELECT\n"
        "          trace_id,\n"
        "          argMinIf((agent_name, agent_version, agent_id), started_at, agent_name != '')\n"
        "            AS fb_agent_identity,\n"
        "          anyIf(conversation_id, conversation_id != '') AS fb_conversation_id\n"
        "      FROM spans\n"
        "      WHERE project_id = {genai_5:String}\n"
        "      GROUP BY trace_id\n"
        "    ) tf ON s0.trace_id = tf.trace_id\n"
        "    WHERE s0.project_id = {genai_5:String}\n"
        "  )\n"
        ") s\n"
        "        WHERE s.project_id = {genai_2:String}\n"
        "        GROUP BY conversation_id\n"
        "        \n"
        "        ORDER BY last_seen DESC\n"
        "        LIMIT {genai_3:UInt64} OFFSET {genai_4:UInt64}\n"
        "    "
    )
    assert calls[2] == (
        "\n        SELECT s.conversation_id AS conversation_id,\n"
        "               argMinIf(s.input_messages, s.started_at, length(s.input_messages) > 0) AS first_input_messages,\n"
        "               argMaxIf(s.output_messages, s.ended_at, length(s.output_messages) > 0) AS last_output_messages\n"
        "        FROM spans s\n"
        "        WHERE s.project_id = {genai_0:String} AND s.conversation_id IN {genai_1:Array(String)}\n"
        "        GROUP BY conversation_id\n"
        "    "
    )

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
        column_names=["role", "content", "min_created_at"],
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

    assert res == AgentTraceMessagesRes(
        messages=[
            NormalizedMessage(role="system", content="be helpful"),
            NormalizedMessage(role="user", content="hi"),
            NormalizedMessage(role="assistant", content="hello"),
        ]
    )
    assert len(calls) == 1
    assert "t1" in calls[0][1].values()
