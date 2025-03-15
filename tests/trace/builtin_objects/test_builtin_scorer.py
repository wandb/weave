# Tests:
# 1. Publishing alignment & class alignment
# 2. Local Create, Local Direct Score
# 3. Local Create, Remote Direct Score
# 4. Remote Create, Local Direct Score
# 5. Remote Create, Remote Direct Score
from __future__ import annotations

import weave
from weave.builtin_objects.scorers.LLMJudgeScorer import LLMJudgeScorer
from weave.trace.weave_client import ApplyScorerResult, Call, WeaveClient
from weave.trace_server import trace_server_interface as tsi

scorer_args = {
    "model": "gpt-4o",
    "system_prompt": "You are a judge that scores the correctness of a response.",
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "Correctness",
            "schema": {
                "type": "object",
                "properties": {
                    "is_correct": {"type": "boolean"},
                },
            },
        },
    },
}

score_input = {"inputs": {"question": "What color is the sky?"}, "output": "blue"}

expected_score = {"is_correct": True}


def test_scorer_publishing_alignment(client: WeaveClient):
    model = LLMJudgeScorer(**scorer_args)
    publish_ref = weave.publish(model, name="CorrectnessJudge")

    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "CorrectnessJudge",
                    "val": scorer_args,
                    "builtin_object_class": "LLMJudgeScorer",
                }
            }
        )
    )

    assert obj_create_res.digest == publish_ref.digest

    gotten_model = weave.ref(publish_ref.uri()).get()
    assert isinstance(gotten_model, LLMJudgeScorer)


def make_simple_call():
    @weave.op
    def simple_op(question: str) -> str:
        return "blue"

    res, call = simple_op.call("What color is the sky?")
    return res, call


def assert_expected_outcome(
    target_call: Call, scorer_res: ApplyScorerResult | tsi.ScoreCallRes
):
    scorer_output = None
    feedback_id = None
    if isinstance(scorer_res, tsi.ScoreCallRes):
        scorer_output = scorer_res.score_call.output
        feedback_id = scorer_res.feedback_id
    else:
        scorer_output = scorer_res["score_call"].output
        feedback_id = scorer_res["feedback_id"]

    assert scorer_output == expected_score
    feedbacks = list(target_call.feedback)
    assert len(feedbacks) == 1
    assert feedbacks[0].payload["output"] == expected_score
    assert feedbacks[0].id == feedback_id


def do_remote_score(
    client: WeaveClient, target_call: Call, scorer_ref: weave.ObjectRef
):
    return client.server.score_call(
        tsi.ScoreCallReq.model_validate(
            {
                "project_id": client._project_id(),
                "call_ref": target_call.ref.uri(),
                "scorer_ref": scorer_ref.uri(),
            }
        )
    )


def make_remote_scorer(client: WeaveClient):
    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "CorrectnessJudge",
                    "val": scorer_args,
                    "builtin_object_class": "LLMJudgeScorer",
                }
            }
        )
    )
    client._flush()
    obj_ref = weave.ObjectRef(
        entity=client._project_id().split("/")[0],
        project=client._project_id().split("/")[1],
        name="CorrectnessJudge",
        _digest=obj_create_res.digest,
    )
    return obj_ref


def test_scorer_local_create_local_use(client: WeaveClient):
    scorer = LLMJudgeScorer(**scorer_args)
    res, call = make_simple_call()
    apply_scorer_res = call._apply_scorer(scorer)
    assert_expected_outcome(call, apply_scorer_res)


def test_scorer_local_create_remote_use(client: WeaveClient):
    scorer = LLMJudgeScorer(**scorer_args)
    res, call = make_simple_call()
    publish_ref = weave.publish(scorer)
    remote_score_res = do_remote_score(client, call, publish_ref)
    assert_expected_outcome(call, remote_score_res)


def test_scorer_remote_create_local_use(client: WeaveClient):
    obj_ref = make_remote_scorer(client)
    fetched = weave.ref(obj_ref.uri()).get()
    assert isinstance(fetched, LLMJudgeScorer)
    res, call = make_simple_call()
    apply_scorer_res = call._apply_scorer(fetched)
    assert_expected_outcome(call, apply_scorer_res)


def test_scorer_remote_create_remote_use(client: WeaveClient):
    obj_ref = make_remote_scorer(client)
    res, call = make_simple_call()
    remote_score_res = do_remote_score(client, call, obj_ref)
    assert_expected_outcome(call, remote_score_res)
