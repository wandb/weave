import os

from litellm import OpenAI

import weave
from weave.flow import action_objects
from weave.trace.feedback_types.score import SCORE_TYPE_NAME
from weave.trace.weave_client import WeaveClient, get_ref
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface import actions


def test_action_create(client: WeaveClient):
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    @weave.op
    def extract_name(user_input: str) -> str:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Extract the name from the user input. If there is no name, return an empty string.",
                },
                {"role": "user", "content": user_input},
            ],
            temperature=0.0,
            max_tokens=64,
            top_p=1,
        )
        return response.choices[0].message.content

    res, call = extract_name.call("My name is Tim.")

    action = action_objects.ActionWithConfig(
        name="is_name_extracted",
        action=actions.BuiltinAction(
            name="openai_completion",
        ),
        config={
            "system_prompt": "Given the following prompt and response, determine if the name was extracted correctly.",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "is_name_extracted",
                    "schema": {
                        "type": "object",
                        "properties": {"is_extracted": {"type": "boolean"}},
                        "required": ["is_extracted"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        },
    )
    mapping = action_objects.ActionOpMapping(
        action=action,
        op_name=get_ref(extract_name).name,
        op_digest=get_ref(extract_name).digest,
        input_mapping={
            "inputs.user_input": "prompt",
            "output": "response",
        },
    )
    weave.publish(mapping)

    res = client.server.execute_batch_action(
        req=tsi.ExecuteBatchActionReq(call_ids=[call.id], mapping=mapping)
    )

    gotten_call = client.server.calls_query(
        req=tsi.CallsQueryReq(
            project_id=client._project_id(), call_ids=[call.id], include_feedback=True
        )
    )
    assert len(gotten_call.calls) == 2
    target_call = gotten_call.calls[0]

    assert target_call.op_name == get_ref(extract_name).uri()
    feedbacks = target_call.summary["weave"]["feedback"]
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert (
        feedback["feedback_type"] == SCORE_TYPE_NAME
    )  # Should this be something else? Need to decide before checking this into master.
    assert feedback["payload"]["name"] == "is_name_extracted"
    assert feedback["payload"]["action_ref"] == get_ref(action).uri()
    assert feedback["payload"]["call_ref"] == "WHAT SHOULD THIS BE?"
    assert feedback["payload"]["results"] == {"is_extracted": True}


# def test_builtin_actions(client: WeaveClient):
#     actions = client.server.actions_list()
#     assert len(actions) > 0


# def test_action_flow(client: WeaveClient):
#     # 1. Bootstrap builtin actions
#     # 2. Query Available Actions
#     # Run an op
#     # 3. Create a 1-off batch action using mapping
#     # 4. Create an online trigger
#     # Run more ops
#     # 5. Query back the feedback results.
#     pass


"""
Framing:

1. We support a number of functions that serve as scorers from a standard lib like https://docs.ragas.io/en/stable/concepts/metrics
2. Each scorer can have a config to configure the rules of the scorer (think of this like a closure)
3. When executing a scorer, we will need to define a mapping for an op (inputs and outputs) to the specific fields


(Scorers - Hard coded, but versioned non-the-less)
Mapping (Mapping from Op to Scorer fields)
Run (single / Batch) - not saved, needs config
Online - query/filter, sample rate, scorer, config, mapping, op



Spec:

"""

# Shouldn't actually put thiese in the user space
# input_schema=actions.JSONSchema(
#     schema={
#         "type": "object",
#         "properties": {"prompt": {"type": "string"}},
#         "required": ["prompt"],
#         "additionalProperties": False,
#     }
# ),
# config_schema=actions.JSONSchema(
#     schema={
#         "type": "object",
#         "properties": {
#             "system_prompt": {"type": "string"},
#             "response_format": {"type": "object"},
#         },
#         "required": ["system_prompt"],
#         "additionalProperties": False,
#     }
# ),
