import weave
from weave.trace.refs import CallRef
from weave.trace.weave_client import WeaveClient


def test_scorer_op_no_context(client: WeaveClient):
    @weave.op
    def predict(x):
        return x + 1

    @weave.op
    def score_fn(x, output):
        return output - x

    _, call = predict.call(1)
    apply_score_res = call.apply_scorer(score_fn)
    assert apply_score_res.feedback_id is not None
    assert apply_score_res.call_id is not None
    assert apply_score_res.score == 1

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
    assert target_feedback.payload == {"output": 1}


def test_scorer_op_with_context(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_op_incorrect_args(client: WeaveClient):
    raise NotImplementedError()


def test_async_scorer_op(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_no_context(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_with_context(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_incorrect_args(client: WeaveClient):
    raise NotImplementedError()


def test_scorer_obj_with_arg_mapping(client: WeaveClient):
    raise NotImplementedError()


def test_async_scorer_obj(client: WeaveClient):
    raise NotImplementedError()
