from __future__ import annotations

import pytest

import weave
from weave.flow.scorer import ApplyScorerResult
from weave.trace.op import OpCallError
from weave.trace.refs import CallRef
from weave.trace.weave_client import Call, Op, WeaveClient


def do_assertions_for_scorer_op(
    apply_score_res: ApplyScorerResult,
    call: Call,
    score_fn: Op | weave.Scorer,
    client: WeaveClient,
):
    assert apply_score_res.score_call.id is not None
    assert apply_score_res.result == 0

    feedbacks = list(call.feedback)
    assert len(feedbacks) == 1
    target_feedback = feedbacks[0]
    scorer_name = (
        score_fn.name if isinstance(score_fn, Op) else score_fn.__class__.__name__
    )
    assert target_feedback.feedback_type == "wandb.runnable." + scorer_name
    assert target_feedback.runnable_ref == score_fn.ref.uri()
    assert (
        target_feedback.call_ref
        == CallRef(
            entity=client.entity,
            project=client.project,
            id=apply_score_res.score_call.id,
        ).uri()
    )
    assert target_feedback.payload == {"output": apply_score_res.result}


@pytest.mark.asyncio
async def test_scorer_op_no_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    def score_fn(x, output):
        return output - x - 1

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(score_fn)
    do_assertions_for_scorer_op(apply_score_res, call, score_fn, client)

    @weave.op
    def score_fn_with_incorrect_args(y, output):
        return output - y

    with pytest.raises(OpCallError):
        apply_score_res = await call.apply_scorer(score_fn_with_incorrect_args)


@pytest.mark.asyncio
async def test_scorer_op_with_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    def score_fn(x, output, correct_answer):
        return output - correct_answer

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(
        score_fn, additional_scorer_kwargs={"correct_answer": 2}
    )
    do_assertions_for_scorer_op(apply_score_res, call, score_fn, client)

    @weave.op
    def score_fn_with_incorrect_args(x, output, incorrect_arg):
        return output - incorrect_arg

    with pytest.raises(OpCallError):
        apply_score_res = await call.apply_scorer(
            score_fn_with_incorrect_args, additional_scorer_kwargs={"correct_answer": 2}
        )


@pytest.mark.asyncio
async def test_async_scorer_op(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    async def score_fn(x, output):
        return output - x - 1

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(score_fn)
    do_assertions_for_scorer_op(apply_score_res, call, score_fn, client)

    @weave.op
    async def score_fn_with_incorrect_args(y, output):
        return output - y

    with pytest.raises(OpCallError):
        apply_score_res = await call.apply_scorer(score_fn_with_incorrect_args)


@pytest.mark.asyncio
async def test_scorer_obj_no_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    class MyScorer(weave.Scorer):
        offset: int

        @weave.op
        def score(self, x, output):
            return output - x - self.offset

    scorer = MyScorer(offset=1)

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(scorer)
    do_assertions_for_scorer_op(apply_score_res, call, scorer, client)

    class MyScorerWithIncorrectArgs(weave.Scorer):
        offset: int

        @weave.op
        def score(self, y, output):
            return output - y - self.offset

    with pytest.raises(OpCallError):
        apply_score_res = await call.apply_scorer(MyScorerWithIncorrectArgs(offset=1))


@pytest.mark.asyncio
async def test_scorer_obj_with_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    class MyScorer(weave.Scorer):
        offset: int

        @weave.op
        def score(self, x, output, correct_answer):
            return output - correct_answer - self.offset

    scorer = MyScorer(offset=0)

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(
        scorer, additional_scorer_kwargs={"correct_answer": 2}
    )
    do_assertions_for_scorer_op(apply_score_res, call, scorer, client)

    class MyScorerWithIncorrectArgs(weave.Scorer):
        offset: int

        @weave.op
        def score(self, y, output, incorrect_arg):
            return output - incorrect_arg - self.offset

    with pytest.raises(OpCallError):
        apply_score_res = await call.apply_scorer(
            MyScorerWithIncorrectArgs(offset=0),
            additional_scorer_kwargs={"incorrect_arg": 2},
        )

    class MyScorerWithIncorrectArgsButCorrectColumnMapping(weave.Scorer):
        offset: int

        @weave.op
        def score(self, y, output, incorrect_arg):
            return output - incorrect_arg - self.offset

    scorer = MyScorerWithIncorrectArgsButCorrectColumnMapping(
        offset=0, column_map={"y": "x", "incorrect_arg": "correct_answer"}
    )

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(
        scorer, additional_scorer_kwargs={"correct_answer": 2}
    )
    do_assertions_for_scorer_op(apply_score_res, call, scorer, client)


@pytest.mark.asyncio
async def test_async_scorer_obj(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    class MyScorer(weave.Scorer):
        offset: int

        @weave.op
        async def score(self, x, output):
            return output - x - 1

    scorer = MyScorer(offset=0)

    _, call = predict.call(1)
    apply_score_res = await call.apply_scorer(
        scorer, additional_scorer_kwargs={"correct_answer": 2}
    )
    do_assertions_for_scorer_op(apply_score_res, call, scorer, client)


@pytest.mark.asyncio
async def test_scorer_with_pydantic_output(client: WeaveClient):
    @weave.op
    def score():
        return WeaveScorerResult(passed=False, metadata={"score": 0.8, "score_2": 0.8})

    _, call = score.call()
    apply_score_res = await call.apply_scorer(score)

    assert apply_score_res.score_call.id is not None
    assert isinstance(apply_score_res.result, dict)
    assert apply_score_res.result == {
        "passed": False,
        "metadata": {"score": 0.8, "score_2": 0.8},
    }

    feedbacks = list(call.feedback)
    assert len(feedbacks) == 1
    target_feedback = feedbacks[0]
    assert target_feedback.feedback_type == "wandb.runnable.WeaveScorerResult"
