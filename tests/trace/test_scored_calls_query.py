from __future__ import annotations

import pytest

import weave
from weave import Scorer
from weave.trace.op_protocol import Op
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import (
    CallsQueryReq,
    CallsQueryStatsReq,
    Query,
)


def make_op_scorers() -> tuple[Op, Op, Op]:
    @weave.op
    def fn0(x, output):
        return x == output

    @weave.op
    def fn1(x, output):
        return x == output

    fn0_v0 = fn0

    # Must have the same name as fn0
    @weave.op
    def fn0(x, output):
        return x == output + 1

    return fn0_v0, fn0, fn1


def make_obj_scorers() -> tuple[Scorer, Scorer, Scorer]:
    class MyScorer0(weave.Scorer):
        offset: int

        @weave.op
        def score(self, x, output):
            return output - x - self.offset

    class MyScorer1(weave.Scorer):
        offset: int

        @weave.op
        def score(self, x, output):
            return output - x - self.offset + 1

    return MyScorer0(offset=0), MyScorer0(offset=1), MyScorer1(offset=0)


@pytest.mark.asyncio
@pytest.mark.parametrize("make_scorers", [make_op_scorers, make_obj_scorers])
async def test_scorer_query(client: WeaveClient, make_scorers):
    """Query calls by scorer for both op-based and object-based scorers.

    Ensures we can query for calls scored by any scorer type and that we
    correctly differentiate between versions of the same scorer. We also check
    that the low-level mongo query and the high-level `scored_by` api return the
    same results; users should only need the `scored_by` param.
    """
    s0_v0, s0_v1, s1_v0 = make_scorers()

    @weave.op
    def predict(x):
        return x if x % 2 == 0 else x + 1

    _, call_unscored = predict.call(0)
    _, call_scored_by_s0_v0 = predict.call(1)
    await call_scored_by_s0_v0.apply_scorer(s0_v0)

    _, call_scored_by_s1_v0 = predict.call(2)
    await call_scored_by_s1_v0.apply_scorer(s1_v0)

    _, call_scored_by_s0_v0_and_s1_v0 = predict.call(3)
    await call_scored_by_s0_v0_and_s1_v0.apply_scorer(s0_v0)
    await call_scored_by_s0_v0_and_s1_v0.apply_scorer(s1_v0)

    _, call_scored_by_s0_v1 = predict.call(4)
    await call_scored_by_s0_v1.apply_scorer(s0_v1)

    s0_v0_uri = s0_v0.ref.uri
    s0_v0_name = s0_v0.ref.name

    s0_v1_uri = s0_v1.ref.uri
    s0_v1_name = s0_v1.ref.name

    s1_v0_uri = s1_v0.ref.uri
    s1_v0_name = s1_v0.ref.name

    # This is required for the test to work
    assert s0_v0_name == s0_v1_name
    assert s0_v0_name != s1_v0_name

    s0_name = s0_v0_name
    s1_name = s1_v0_name

    """
    The above ordering is quite important. We now have the following scores:
    * call_unscored
    * call_scored_by_s0_v0
        * s0:v0
    * call_scored_by_s1_v0
        * s1:v0
    * call_scored_by_s0_v0_and_s1_v0
        * s0:v0
        * s1:v0
    * call_scored_by_s0_v1
        * s0:v1
    """

    # Verify Baseline
    assert_number_of_calls(client, 10)  # 5 predictions, 5 scores

    # 1. Query for calls that have been scored by s0:*
    expected_ids = call_ids(
        [call_scored_by_s0_v0, call_scored_by_s0_v0_and_s1_v0, call_scored_by_s0_v1]
    )
    query = {"$expr": exists_expr(output_field_for_name(s0_name))}
    calls_low_level = client.server.calls_query(
        CallsQueryReq(project_id=client.project_id, query=query)
    ).calls
    calls_high_level = client.get_calls(scored_by=[s0_name])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids
    count = stats_query(client, query)
    assert len(calls_high_level) == len(calls_low_level) == count

    # 2. Query for calls that have been scored by s0:v0
    expected_ids = call_ids([call_scored_by_s0_v0, call_scored_by_s0_v0_and_s1_v0])
    query = {"$expr": eq_expr(runnable_ref_field_for_name(s0_name), s0_v0_uri)}
    calls_low_level = client.server.calls_query(
        CallsQueryReq(project_id=client.project_id, query=query)
    ).calls
    calls_high_level = client.get_calls(scored_by=[s0_v0_uri])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids
    count = stats_query(client, query)
    assert len(calls_high_level) == len(calls_low_level) == count

    # 3. Query for calls that have been scored by s0:v1
    expected_ids = call_ids([call_scored_by_s0_v1])
    query = {"$expr": eq_expr(runnable_ref_field_for_name(s0_name), s0_v1_uri)}
    calls_low_level = client.server.calls_query(
        CallsQueryReq(project_id=client.project_id, query=query)
    ).calls
    calls_high_level = client.get_calls(scored_by=[s0_v1_uri])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids
    count = stats_query(client, query)
    assert len(calls_high_level) == len(calls_low_level) == count

    # 4. Query for calls that have been scored by s1:*
    expected_ids = call_ids([call_scored_by_s1_v0, call_scored_by_s0_v0_and_s1_v0])
    query = {"$expr": exists_expr(output_field_for_name(s1_name))}
    calls_low_level = client.server.calls_query(
        CallsQueryReq(project_id=client.project_id, query=query)
    ).calls
    calls_high_level = client.get_calls(scored_by=[s1_name])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids
    count = stats_query(client, query)
    assert len(calls_high_level) == len(calls_low_level) == count

    # 5. Query for calls that have been scored by s1:v0
    expected_ids = call_ids([call_scored_by_s1_v0, call_scored_by_s0_v0_and_s1_v0])
    query = {"$expr": eq_expr(runnable_ref_field_for_name(s1_name), s1_v0_uri)}
    calls_low_level = client.server.calls_query(
        CallsQueryReq(project_id=client.project_id, query=query)
    ).calls
    calls_high_level = client.get_calls(scored_by=[s1_v0_uri])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids
    count = stats_query(client, query)
    assert len(calls_high_level) == len(calls_low_level) == count


def assert_number_of_calls(client: WeaveClient, count: int):
    stats = client.server.calls_query_stats(
        CallsQueryStatsReq(
            project_id=client.project_id,
        )
    )
    assert stats.count == count


def output_field_for_name(name: str) -> str:
    return f"feedback.[wandb.runnable.{name}].payload.output"


def runnable_ref_field_for_name(name: str) -> str:
    return f"feedback.[wandb.runnable.{name}].runnable_ref"


def exists_expr(field: str) -> str:
    return {"$not": [{"$eq": [{"$getField": field}, {"$literal": ""}]}]}


def eq_expr(field: str, value: str) -> str:
    return {"$eq": [{"$getField": field}, {"$literal": value}]}


def call_ids(calls: list[weave.Call]) -> list[str]:
    return [c.id for c in calls]


def stats_query(client: WeaveClient, query: Query) -> CallsQueryStatsReq:
    return client.server.calls_query_stats(
        CallsQueryStatsReq(project_id=client.project_id, query=query)
    ).count
