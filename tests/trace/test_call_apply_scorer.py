import pytest

import weave
from weave.trace.op import OpCallError
from weave.trace.refs import CallRef
from weave.trace.weave_client import ApplyScorerResult, Call, Op, WeaveClient


def do_assertions_for_scorer_op(
    apply_score_res: ApplyScorerResult, call: Call, score_fn: Op, client: WeaveClient
):
    assert apply_score_res.feedback_id is not None
    assert apply_score_res.call_id is not None
    assert apply_score_res.score == 0

    feedbacks = list(call.feedback)
    assert len(feedbacks) == 1
    target_feedback = feedbacks[0]
    assert target_feedback.id == apply_score_res.feedback_id
    assert target_feedback.feedback_type == "wandb.runnable.score_fn"
    assert target_feedback.runnable_ref == score_fn.ref.uri()
    assert (
        target_feedback.call_ref
        == CallRef(
            entity=client.entity, project=client.project, id=apply_score_res.call_id
        ).uri()
    )
    assert target_feedback.payload == {"output": apply_score_res.score}


def test_scorer_op_no_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    def score_fn(x, output):
        return output - x - 1

    _, call = predict.call(1)
    apply_score_res = call.apply_scorer(score_fn)
    do_assertions_for_scorer_op(apply_score_res, call, score_fn, client)

    @weave.op
    def score_fn_with_incorrect_args(y, output):
        return output - y

    with pytest.raises(OpCallError):
        apply_score_res = call.apply_scorer(score_fn_with_incorrect_args)


def test_scorer_op_with_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    def score_fn(x, output, correct_answer):
        return output - correct_answer

    _, call = predict.call(1)
    apply_score_res = call.apply_scorer(
        score_fn, additional_scorer_kwargs={"correct_answer": 2}
    )
    do_assertions_for_scorer_op(apply_score_res, call, score_fn, client)

    @weave.op
    def score_fn_with_incorrect_args(x, output, incorrect_arg):
        return output - incorrect_arg

    with pytest.raises(OpCallError):
        apply_score_res = call.apply_scorer(
            score_fn_with_incorrect_args, additional_scorer_kwargs={"correct_answer": 2}
        )


def test_async_scorer_op(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_no_context(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_with_context(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_with_arg_mapping(client: WeaveClient):
    raise NotImplementedError()


def test_async_scorer_obj(client: WeaveClient):
    raise NotImplementedError()
