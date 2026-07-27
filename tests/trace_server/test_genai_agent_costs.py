"""Integration tests for query-time costs on GenAI agent spans.

Runs against the ClickHouse backend. Seeds a project-scoped price row in
`llm_token_prices`, ingests spans referencing that model, and asserts the cost
columns surfaced by the spans query and stats APIs. Project-level pricing keeps
each test deterministic and isolated from the migration-seeded default prices.
"""

import datetime
import uuid

import pytest

from tests.trace_server.helpers import make_project_id as _make_project_id
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpansQueryReq,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsReq,
    AgentSpanValueRef,
    AgentsQueryReq,
    AgentTraceChatReq,
    AgentVersionsQueryReq,
)

# Per-token prices used by the tests. Small, exact, and unlikely to collide
# with a real model's seeded default price.
_PROMPT_COST = 0.00001
_COMPLETION_COST = 0.00003
_CACHE_READ_COST = 0.000005
_CACHE_CREATION_COST = 0.0000125


def _insert_project_price(ch_client, project_id: str, llm_id: str) -> None:
    """Insert a project-level price row for `llm_id`."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    ch_client.insert(
        "llm_token_prices",
        [
            (
                str(uuid.uuid4()),
                "project",
                project_id,
                "test-provider",
                llm_id,
                now,
                _PROMPT_COST,
                "USD",
                _COMPLETION_COST,
                "USD",
                _CACHE_READ_COST,
                _CACHE_CREATION_COST,
                "system",
                now,
            )
        ],
        column_names=[
            "id",
            "pricing_level",
            "pricing_level_id",
            "provider_id",
            "llm_id",
            "effective_date",
            "prompt_token_cost",
            "prompt_token_cost_unit",
            "completion_token_cost",
            "completion_token_cost_unit",
            "cache_read_input_token_cost",
            "cache_creation_input_token_cost",
            "created_by",
            "created_at",
        ],
    )


def _make_span(project_id: str, **overrides: object) -> AgentSpanCHInsertable:
    defaults = {
        "project_id": project_id,
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex,
        "span_name": "test-span",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "status_code": "OK",
        "operation_name": "chat",
        "agent_name": "test-agent",
        "provider_name": "test-provider",
        "input_tokens": 1000,
        "output_tokens": 500,
    }
    defaults.update(overrides)
    return AgentSpanCHInsertable(**defaults)


def _insert_spans(ch_client, spans: list[AgentSpanCHInsertable]) -> None:
    rows = [genai_span_to_row(s) for s in spans]
    ch_client.insert("spans", data=rows, column_names=ALL_SPAN_INSERT_COLUMNS)


def test_spans_query_includes_costs(ch_server):
    """Ungrouped spans query returns per-span costs when include_costs=True."""
    project_id = _make_project_id("span-costs")
    model = f"test-cost-model-{uuid.uuid4().hex}"
    _insert_project_price(ch_server.ch_client, project_id, model)
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                request_model=model,
                input_tokens=1000,
                output_tokens=500,
            )
        ],
    )

    # Without include_costs, no cost is computed.
    res = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    assert res.spans[0].total_cost_usd is None

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, include_costs=True)
    )
    span = res.spans[0]
    assert span.input_cost_usd == pytest.approx(1000 * _PROMPT_COST)
    assert span.output_cost_usd == pytest.approx(500 * _COMPLETION_COST)
    assert span.total_cost_usd == pytest.approx(
        1000 * _PROMPT_COST + 500 * _COMPLETION_COST
    )


def test_spans_query_cost_subtracts_cache_tokens(ch_server):
    """Cached input tokens are billed at the cache rate, not the input rate."""
    project_id = _make_project_id("span-costs-cache")
    model = f"test-cost-model-{uuid.uuid4().hex}"
    _insert_project_price(ch_server.ch_client, project_id, model)
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                request_model=model,
                input_tokens=1000,
                output_tokens=500,
                cache_read_input_tokens=200,
                cache_creation_input_tokens=100,
            )
        ],
    )

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, include_costs=True)
    )
    span = res.spans[0]
    expected_input = (1000 - 200 - 100) * _PROMPT_COST
    expected_total = (
        expected_input
        + 500 * _COMPLETION_COST
        + 200 * _CACHE_READ_COST
        + 100 * _CACHE_CREATION_COST
    )
    assert span.input_cost_usd == pytest.approx(expected_input)
    assert span.cache_read_cost_usd == pytest.approx(200 * _CACHE_READ_COST)
    assert span.cache_creation_cost_usd == pytest.approx(100 * _CACHE_CREATION_COST)
    assert span.total_cost_usd == pytest.approx(expected_total)


def test_spans_query_unpriced_model_has_none_cost(ch_server):
    """A span whose model has no matching price gets None (not 0) costs."""
    project_id = _make_project_id("span-costs-none")
    _insert_spans(
        ch_server.ch_client,
        [_make_span(project_id, request_model=f"unpriced-{uuid.uuid4().hex}")],
    )
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, include_costs=True)
    )
    assert res.spans[0].total_cost_usd is None
    assert res.spans[0].input_cost_usd is None


def test_grouped_spans_query_sums_costs(ch_server):
    """Grouped spans query sums per-span costs into total_cost_usd."""
    project_id = _make_project_id("span-costs-grouped")
    model = f"test-cost-model-{uuid.uuid4().hex}"
    conversation_id = uuid.uuid4().hex
    _insert_project_price(ch_server.ch_client, project_id, model)
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                request_model=model,
                conversation_id=conversation_id,
                input_tokens=1000,
                output_tokens=500,
            )
            for _ in range(3)
        ],
    )

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            include_costs=True,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        )
    )
    group = next(
        g for g in res.groups if g.group_keys.get("conversation_id") == conversation_id
    )
    per_span = 1000 * _PROMPT_COST + 500 * _COMPLETION_COST
    assert group.total_cost_usd == pytest.approx(3 * per_span)
    assert group.total_input_cost_usd == pytest.approx(3 * 1000 * _PROMPT_COST)
    assert group.total_output_cost_usd == pytest.approx(3 * 500 * _COMPLETION_COST)


def test_spans_stats_total_cost_metric(ch_server):
    """Stats API aggregates the total_cost_usd derived metric over time."""
    project_id = _make_project_id("span-costs-stats")
    model = f"test-cost-model-{uuid.uuid4().hex}"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    _insert_project_price(ch_server.ch_client, project_id, model)
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                request_model=model,
                started_at=now,
                input_tokens=1000,
                output_tokens=500,
            )
            for _ in range(2)
        ],
    )

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=now - datetime.timedelta(hours=1),
            end=now + datetime.timedelta(hours=1),
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="cost",
                    value_type="number",
                    aggregations=["sum"],
                    value=AgentSpanValueRef(source="derived", key="total_cost_usd"),
                )
            ],
        )
    )
    per_span = 1000 * _PROMPT_COST + 500 * _COMPLETION_COST
    total = sum(float(row.get("sum_cost") or 0) for row in res.rows)
    assert total == pytest.approx(2 * per_span)


def test_trace_chat_includes_cost(ch_server):
    """The trace chat view sums per-span cost into the trace total."""
    project_id = _make_project_id("span-costs-chat")
    model = f"test-cost-model-{uuid.uuid4().hex}"
    trace_id = uuid.uuid4().hex
    _insert_project_price(ch_server.ch_client, project_id, model)
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                trace_id=trace_id,
                span_id=uuid.uuid4().hex,
                request_model=model,
                operation_name="invoke_agent",
                output_messages=[{"role": "assistant", "content": "hello"}],
                input_tokens=1000,
                output_tokens=500,
            )
        ],
    )

    res = ch_server.agent_traces_chat(
        AgentTraceChatReq(project_id=project_id, trace_id=trace_id)
    )
    per_span = 1000 * _PROMPT_COST + 500 * _COMPLETION_COST
    assert res.total_cost_usd == pytest.approx(per_span)
    assistant = next(m for m in res.messages if m.type == "assistant_message")
    assert assistant.assistant_message.total_cost_usd == pytest.approx(per_span)


def test_agents_query_includes_cost(ch_server):
    """agents_query / agent_versions_query fill total_cost_usd when include_costs is set."""
    project_id = _make_project_id("span-costs-agents")
    model = f"test-cost-model-{uuid.uuid4().hex}"
    agent_name = f"agent-{uuid.uuid4().hex}"
    version = "v1"
    _insert_project_price(ch_server.ch_client, project_id, model)
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                request_model=model,
                agent_name=agent_name,
                agent_version=version,
                operation_name="invoke_agent",
                input_tokens=1000,
                output_tokens=500,
            )
            for _ in range(2)
        ],
    )
    per_span = 1000 * _PROMPT_COST + 500 * _COMPLETION_COST

    res = ch_server.agent_agents_query(
        AgentsQueryReq(project_id=project_id, include_costs=True)
    )
    agent = next(a for a in res.agents if a.agent_name == agent_name)
    assert agent.total_cost_usd == pytest.approx(2 * per_span)

    # Without include_costs, total_cost_usd stays None.
    res_no_cost = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    agent_no_cost = next(a for a in res_no_cost.agents if a.agent_name == agent_name)
    assert agent_no_cost.total_cost_usd is None

    versions = ch_server.agent_versions_query(
        AgentVersionsQueryReq(
            project_id=project_id, agent_name=agent_name, include_costs=True
        )
    )
    v = next(x for x in versions.versions if x.agent_version == version)
    assert v.total_cost_usd == pytest.approx(2 * per_span)
