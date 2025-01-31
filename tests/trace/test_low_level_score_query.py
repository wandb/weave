"""
This file is testing the low level scoring query that the UI is making.
We really should move this to the backend to optimize and make a higher
level api for the user.
"""

from __future__ import annotations

import pytest

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsQueryStatsReq


@pytest.mark.asyncio
async def test_scorer_op_query(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    def score_fn(x, output):
        return output - x - 1

    _, call_1 = predict.call(1)
    _, call_2 = predict.call(2)
    _, call_3 = predict.call(3)

    await call_1.apply_scorer(score_fn)
    # Intentionally not calling on call_2
    # await call_2.apply_scorer(score_fn)
    await call_3.apply_scorer(score_fn)

    stats = client.server.calls_query_stats(CallsQueryStatsReq(
        project_id=client._project_id(),
    ))
    assert stats.count == 5
    stats = client.server.calls_query_stats(CallsQueryStatsReq(
        project_id=client._project_id(),
        # There is no way we want a human to write this query.
        query={"$expr":{"$not":[{"$eq":[{"$getField":"feedback.[wandb.runnable.score_fn].payload.output"},{"$literal":""}]}]}}
    ))
    assert stats.count == 2

@pytest.mark.asyncio
async def test_scorer_obj_query(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    class MyScorer(weave.Scorer):
        offset: int

        @weave.op
        def score(self, x, output):
            return output - x - self.offset

    scorer = MyScorer(offset=1)

    _, call_1 = predict.call(1)
    _, call_2 = predict.call(2)
    _, call_3 = predict.call(3)

    await call_1.apply_scorer(scorer)
    # Intentionally not calling on call_2
    # await call_2.apply_scorer(scorer)
    await call_3.apply_scorer(scorer)

    stats = client.server.calls_query_stats(CallsQueryStatsReq(
        project_id=client._project_id(),
    ))
    assert stats.count == 5
    stats = client.server.calls_query_stats(CallsQueryStatsReq(
        project_id=client._project_id(),
        # There is no way we want a human to write this query.
        query={"$expr":{"$not":[{"$eq":[{"$getField":"feedback.[wandb.runnable.MyScorer].payload.output"},{"$literal":""}]}]}}
    ))
    assert stats.count == 2
