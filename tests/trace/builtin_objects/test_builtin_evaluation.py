from __future__ import annotations

import weave
from weave.builtin_objects.scorers.LLMJudgeScorer import LLMJudgeScorer
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def test_evaluation_publishing_alignment(client: WeaveClient):
    eval_args = {
        "dataset": f"weave:///{client.entity}/{client.project}/object/Dataset:CObSXNGcvzDYN4LvAjXPux46YNMF2CJ5SZKTBbbEJy0",
        "scorers": [
            f"weave:///{client.entity}/{client.project}/object/LLMJudgeScorer:KlrVBCHEcKqPzl6zYCXuODBnEa8MTxYx9JOvPpS9gI0"
        ],
        "trials": 1,
    }

    evaluation = weave.Evaluation(
        dataset=weave.Dataset(rows=[{"input": "hi", "output": "hello"}]),
        scorers=[
            LLMJudgeScorer(
                model="gpt-4o",
                system_prompt="You are a judge that scores the correctness of a response.",
                response_format={
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
            )
        ],
    )

    publish_ref = weave.publish(evaluation, name="CustomEval")

    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "Evaluation",
                    "val": eval_args,
                    # "builtin_object_class": "Evaluation",
                }
            }
        )
    )

    # This is going to fail until we support nested refs
    # Not required for MVP
    assert obj_create_res.digest == publish_ref.digest

    gotten_model = weave.ref(publish_ref.uri()).get()
    assert isinstance(gotten_model, weave.Evaluation)

    # eval = evaluation.evaluate(
    #     LiteLLMCompletionModel(
    #         model="gpt-4o",
    #         messages_template=[{"role": "user", "content": "{input}"}],
    #         response_format={
    #             "type": "json_schema",
    #             "json_schema": {"name": "Person", "schema": {"type": "string"}},
    #         },
    #     )
    # )

    # 1. Verify alignment on publishing
    # 2. call model via api
