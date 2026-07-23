"""Exact SQL assertions for the server-paginated agent Signals query."""

import sqlparse

from weave.trace_server.agents.types import AgentSignalsQueryReq
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_signals_query_builder import (
    make_agent_signals_count_query,
    make_agent_signals_list_query,
)


def test_count_query_reuses_aggregate_filter_semantics() -> None:
    pb = ParamBuilder("signals")
    query = make_agent_signals_count_query(
        pb,
        AgentSignalsQueryReq(
            project_id="entity/project",
            after_ms=1_000,
            before_ms=2_000,
            feedback_types=["wandb.agent_monitor"],
            tags=["unsafe"],
            rating_min=0.25,
            rating_max=0.75,
            scorer_ids=["judge"],
            span_agent_names=["support-bot"],
            span_types=["agent_turn"],
        ),
    )

    expected = """
        SELECT count()
        FROM feedback
        WHERE (
          project_id = {signals_0:String}
          AND created_at >= fromUnixTimestamp64Milli({signals_1:Int64})
          AND created_at < fromUnixTimestamp64Milli({signals_2:Int64})
          AND (startsWith(feedback_type, {signals_3:String}))
          AND (
            splitByChar(':', splitByChar('/', ifNull(runnable_ref, ''))[-1])[1]
              = {signals_4:String}
          )
          AND span_agent_name IN {signals_5:Array(String)}
          AND (splitByChar('/', weave_ref)[-2] = {signals_6:String})
          AND hasAny(scorer_tags, {signals_7:Array(String)})
          AND mapContains(scorer_ratings, {signals_8:String})
          AND scorer_ratings[{signals_8:String}] >= {signals_9:Float64}
          AND scorer_ratings[{signals_8:String}] <= {signals_10:Float64}
        )
        AND (notEmpty(scorer_tags) OR notEmpty(scorer_ratings))
    """
    assert (
        query == sqlparse.format(expected, reindent=True, keyword_case="upper").strip()
    )
    assert pb.get_params() == {
        "signals_0": "entity/project",
        "signals_1": 1_000,
        "signals_2": 2_000,
        "signals_3": "wandb.agent_monitor",
        "signals_4": "judge",
        "signals_5": ["support-bot"],
        "signals_6": "agent_turn",
        "signals_7": ["unsafe"],
        "signals_8": "_rating_",
        "signals_9": 0.25,
        "signals_10": 0.75,
    }


def test_created_at_sort_pages_before_pricing() -> None:
    pb = ParamBuilder("signals")
    query = make_agent_signals_list_query(
        pb,
        AgentSignalsQueryReq(
            project_id="entity/project",
            after_ms=1_000,
            before_ms=2_000,
            limit=50,
            offset=100,
        ),
    )
    compact = " ".join(query.split())

    assert "page_feedback AS" in compact
    assert "FROM page_feedback" in compact
    assert "ORDER BY f.created_at DESC, f.id DESC" in compact
    assert query.index("page_feedback AS") < query.index("scorer_costs AS")


def test_cost_sort_prices_filtered_set_before_stable_page() -> None:
    pb = ParamBuilder("signals")
    query = make_agent_signals_list_query(
        pb,
        AgentSignalsQueryReq(
            project_id="entity/project",
            after_ms=1_000,
            before_ms=2_000,
            sort_by={"field": "total_cost_usd", "direction": "asc"},
            limit=50,
            offset=100,
        ),
    )
    compact = " ".join(query.split())

    assert "page_feedback AS" not in compact
    assert "FROM filtered_feedback" in compact
    assert "LEFT ANY JOIN scorer_costs" in compact
    assert (
        "ORDER BY c.total_cost_usd ASC NULLS LAST, f.created_at DESC, f.id DESC"
        in compact
    )
