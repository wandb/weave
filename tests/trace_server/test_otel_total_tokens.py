"""Provider-reported token totals through both OTel ingestion paths."""

import datetime
import uuid

import pytest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from tests.trace_server.helpers import make_project_id
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanGroupFilter,
    AgentSpanMeasureSpec,
    AgentSpansQueryReq,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsNumericBucketSpec,
    AgentSpanStatsReq,
    AgentSpanValueRef,
    GenAIOTelExportReq,
)
from weave.trace_server.interface.query import Query

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
END = START + datetime.timedelta(hours=1)


def _processed_span(
    attributes: dict[str, int | float | bool | str],
) -> tsi.ProcessedResourceSpans:
    attributes = {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": "gemini-test",
        "gen_ai.conversation.id": "conversation-test",
        **attributes,
    }
    value_fields = {
        bool: "bool_value",
        int: "int_value",
        float: "double_value",
        str: "string_value",
    }
    span = Span(
        name="chat gemini-test",
        trace_id=uuid.uuid4().bytes,
        span_id=uuid.uuid4().bytes[:8],
        start_time_unix_nano=int(START.timestamp() * 1_000_000_000),
        end_time_unix_nano=int(START.timestamp() * 1_000_000_000) + 1_000_000_000,
        attributes=[
            KeyValue(key=key, value=AnyValue(**{value_fields[type(value)]: value}))
            for key, value in attributes.items()
        ],
    )
    return tsi.ProcessedResourceSpans(
        entity="test-entity",
        project="test-project",
        run_id=None,
        resource_spans=ResourceSpans(scope_spans=[ScopeSpans(spans=[span])]),
    )


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens", "reasoning_tokens", "reported", "expected"),
    [
        pytest.param(12, 7, 3, 31, 31, id="provider-total"),
        pytest.param(12, 10, 3, 22, 22, id="reasoning-included-in-output"),
        pytest.param(12, 7, 3, 0, 0, id="explicit-zero"),
        pytest.param(0, 0, 0, 17, 17, id="total-only"),
        pytest.param(12, 7, 3, None, 22, id="missing-total"),
        pytest.param(0, 0, 0, None, 0, id="no-usage"),
        pytest.param(12, 7, 3, -1, 22, id="negative-total"),
        pytest.param(12, 7, 3, "31", 22, id="string-total"),
        pytest.param(12, 7, 3, 31.0, 22, id="float-total"),
        pytest.param(12, 7, 3, True, 22, id="boolean-total"),
    ],
)
def test_agent_reported_total_tokens(
    ch_server, input_tokens, output_tokens, reasoning_tokens, reported, expected
):
    project_id = make_project_id("total_tokens")
    attributes = {
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.usage.reasoning.output_tokens": reasoning_tokens,
    }
    if reported is not None:
        attributes["gen_ai.usage.total_tokens"] = reported
    processed = _processed_span(attributes)
    exported = ch_server.genai_otel_export(
        GenAIOTelExportReq(project_id=project_id, processed_spans=[processed])
    )
    assert exported.accepted_spans == 1
    assert exported.rejected_spans == 0

    stats = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=START,
            end=END,
            granularity=3600,
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="tokens",
                    value_type="number",
                    value=AgentSpanValueRef(source="derived", key="total_tokens"),
                    aggregations=["sum"],
                )
            ],
        )
    )
    assert [row["sum_tokens"] for row in stats.rows] == [expected]

    spans = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [{"$getField": "total_tokens"}, {"$literal": expected}]
                    }
                }
            ),
        )
    )
    span_id = processed.resource_spans.scope_spans[0].spans[0].span_id.hex()
    assert [span.span_id for span in spans.spans] == [span_id]
    assert [
        (span.input_tokens, span.output_tokens, span.reasoning_tokens)
        for span in spans.spans
    ] == [(input_tokens, output_tokens, reasoning_tokens)]


def test_agent_total_tokens_group_filters_and_histogram(ch_server):
    project_id = make_project_id("group_total_tokens")
    exported = ch_server.genai_otel_export(
        GenAIOTelExportReq(
            project_id=project_id,
            processed_spans=[
                _processed_span(
                    {
                        "gen_ai.conversation.id": conversation,
                        "gen_ai.usage.input_tokens": 12,
                        "gen_ai.usage.output_tokens": 7,
                        "gen_ai.usage.reasoning.output_tokens": 3,
                        **usage,
                    }
                )
                for conversation, usage in [
                    ("a", {"gen_ai.usage.total_tokens": 31}),
                    ("a", {"gen_ai.usage.total_tokens": 0}),
                    ("b", {}),
                ]
            ],
        )
    )
    assert exported.accepted_spans == 3
    assert exported.rejected_spans == 0

    total = AgentSpanValueRef(source="derived", key="total_tokens")
    measure = AgentSpanMeasureSpec(
        alias="tokens", aggregation="sum", value=total, value_type="number"
    )
    filtered = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=START,
            end=END,
            granularity=3600,
            group_filters=[AgentSpanGroupFilter(measure=measure, min=30, max=32)],
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="tokens",
                    value_type="number",
                    value=total,
                    aggregations=["sum", "count"],
                )
            ],
        )
    )
    assert [(row["sum_tokens"], row["count_tokens"]) for row in filtered.rows] == [
        (31, 2)
    ]

    histogram = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=START,
            end=END,
            bucket_by=AgentSpanStatsNumericBucketSpec(
                type="number",
                bins=2,
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measure=measure,
            ),
            metrics=[],
        )
    )
    assert histogram.bucket_type == "number"
    assert [row["count"] for row in histogram.rows] == [1, 1]
    assert histogram.rows[0]["bucket_min"] == 22
    assert histogram.rows[-1]["bucket_max"] == 31


@pytest.mark.parametrize(
    ("totals", "expected"),
    [
        pytest.param({"gen_ai.usage.total_tokens": 31}, 31, id="provider-total"),
        pytest.param({"gen_ai.usage.total_tokens": 0}, 0, id="explicit-zero"),
        pytest.param({}, 19, id="missing-total"),
        pytest.param({"llm.usage.total_tokens": 42}, 42, id="legacy-total"),
        pytest.param(
            {"gen_ai.usage.total_tokens": 0, "llm.usage.total_tokens": 42},
            0,
            id="gen-ai-precedence",
        ),
    ],
)
def test_calls_otel_reported_total_tokens(client, totals, expected):
    processed = _processed_span(
        {
            "gen_ai.usage.input_tokens": 12,
            "gen_ai.usage.output_tokens": 7,
            "gen_ai.usage.reasoning.output_tokens": 3,
            **totals,
        }
    )
    client.server.otel_export(
        tsi.OTelExportReq(
            project_id=client.project_id,
            processed_spans=[processed],
            wb_user_id="test-user",
        )
    )
    calls = client.server.calls_query(tsi.CallsQueryReq(project_id=client.project_id))
    assert [call.summary["usage"]["gemini-test"] for call in calls.calls] == [
        {
            "input_tokens": 12,
            "output_tokens": 7,
            "total_tokens": expected,
            "prompt_tokens": None,
            "completion_tokens": None,
            "requests": None,
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
        }
    ]
