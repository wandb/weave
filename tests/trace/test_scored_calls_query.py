from __future__ import annotations

import pytest

import weave
from weave.scorers import Scorer
from weave.trace.op import Op
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsQueryReq, CallsQueryStatsReq


def assert_number_of_calls(client: WeaveClient, count: int):
    stats = client.server.calls_query_stats(
        CallsQueryStatsReq(
            project_id=client._project_id(),
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


async def perform_scorer_tests(
    client: WeaveClient, s0_v0: Scorer | Op, s0_v1: Scorer | Op, s1_v0: Scorer | Op
):
    """
    This is a unified test for both scorer and op tests. It ensures that we can query for calls
    that have been scored by any type of scorer and ensures that we correctly differentiate between
    versions of the same scorer.

    We also ensure that the low-level and high-level queries return the same results. This is because
    we will likely implement a better query at the service layer and we want to ensure that the high
    level api continues to work correctly. We don't really want users to manually write the mongo
    query, so that part of these tests are just here for correctness.

    The only user-facing api we really want to maintain is the param `scored_by` on the client.
    """

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

    s0_v0_uri = s0_v0.ref.uri()
    s0_v0_name = s0_v0.ref.name

    s0_v1_uri = s0_v1.ref.uri()
    s0_v1_name = s0_v1.ref.name

    s1_v0_uri = s1_v0.ref.uri()
    s1_v0_name = s1_v0.ref.name

    # This is required for the test to work
    assert s0_v0_name == s0_v1_name
    assert s0_v0_name != s1_v0_name

    s0_name = s0_v0_name
    s1_name = s1_v0_name

    """
    The above ordering is quire important. We now have the following scores:
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

    # Now, we will perform a few tests:
    # 1. Query for calls that have been scored by s0:*
    # 2. Query for calls that have been scored by s0:v0
    # 3. Query for calls that have been scored by s0:v1
    # 4. Query for calls that have been scored by s1:*
    # 5. Query for calls that have been scored by s1:v0

    # 1. Query for calls that have been scored by s0:*
    expected_ids = call_ids(
        [call_scored_by_s0_v0, call_scored_by_s0_v0_and_s1_v0, call_scored_by_s0_v1]
    )
    calls_low_level = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
            query={"$expr": exists_expr(output_field_for_name(s0_name))},
        )
    ).calls
    calls_high_level = client.get_calls(scored_by=[s0_name])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids

    # 2. Query for calls that have been scored by s0:v0
    expected_ids = call_ids([call_scored_by_s0_v0, call_scored_by_s0_v0_and_s1_v0])
    calls_low_level = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
            query={"$expr": eq_expr(runnable_ref_field_for_name(s0_name), s0_v0_uri)},
        )
    ).calls
    calls_high_level = client.get_calls(scored_by=[s0_v0_uri])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids

    # 3. Query for calls that have been scored by s0:v1
    expected_ids = call_ids([call_scored_by_s0_v1])
    calls_low_level = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
            query={"$expr": eq_expr(runnable_ref_field_for_name(s0_name), s0_v1_uri)},
        )
    ).calls
    calls_high_level = client.get_calls(scored_by=[s0_v1_uri])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids

    # 4. Query for calls that have been scored by s1:*
    expected_ids = call_ids([call_scored_by_s1_v0, call_scored_by_s0_v0_and_s1_v0])
    calls_low_level = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
            query={"$expr": exists_expr(output_field_for_name(s1_name))},
        )
    ).calls
    calls_high_level = client.get_calls(scored_by=[s1_name])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids

    # 5. Query for calls that have been scored by s1:v0
    expected_ids = call_ids([call_scored_by_s1_v0, call_scored_by_s0_v0_and_s1_v0])
    calls_low_level = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
            query={"$expr": eq_expr(runnable_ref_field_for_name(s1_name), s1_v0_uri)},
        )
    ).calls
    calls_high_level = client.get_calls(scored_by=[s1_v0_uri])
    assert call_ids(calls_low_level) == expected_ids
    assert call_ids(calls_high_level) == expected_ids


@pytest.mark.asyncio
async def test_scorer_query_op(client: WeaveClient):
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

    await perform_scorer_tests(client, fn0_v0, fn0, fn1)


@pytest.mark.asyncio
async def test_scorer_query_obj(client: WeaveClient):
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

    s0_v0 = MyScorer0(offset=0)
    s0_v1 = MyScorer0(offset=1)
    s1_v0 = MyScorer1(offset=0)

    await perform_scorer_tests(client, s0_v0, s0_v1, s1_v0)
