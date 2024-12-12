# Tests:
# 1. Publishing alignment & class alignment
# 2. Local Create, Local Direct Score
# 3. Local Create, Remote Direct Score
# 4. Remote Create, Local Direct Score
# 5. Remote Create, Remote Direct Score
import weave
from weave.builtin_objects.scorers.LLMJudgeScorer import LLMJudgeScorer
from weave.trace.weave_client import WeaveClient
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
                    "reasoning": {"type": "string"},
                },
            },
        },
    },
}


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
                    "set_leaf_object_class": "LLMJudgeScorer",
                }
            }
        )
    )

    assert obj_create_res.digest == publish_ref.digest

    gotten_model = weave.ref(publish_ref.uri()).get()
    assert isinstance(gotten_model, LLMJudgeScorer)
