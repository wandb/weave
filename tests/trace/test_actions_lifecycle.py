import os

import pytest

import weave
from tests.integrations.litellm.client_completions_create_test import (
    secret_fetcher_context,
)
from tests.trace.util import client_is_sqlite
from weave.trace.weave_client import WeaveClient
from weave.trace_server.interface.base_object_classes.actions import (
    ActionDefinition,
)
from weave.trace_server.trace_server_interface import (
    ActionsExecuteBatchReq,
    FeedbackCreateReq,
)


class DummySecretFetcher:
    def fetch(self, secret_name: str) -> dict:
        return {
            "secrets": {secret_name: os.environ.get(secret_name, "DUMMY_SECRET_VALUE")}
        }


def test_action_lifecycle_word_count(client: WeaveClient):
    if client_is_sqlite(client):
        return pytest.skip("skipping for sqlite")

    action_name = "my_contains_words_action"

    published_ref = weave.publish(
        ActionDefinition(
            name=action_name,
            spec={
                "action_type": "contains_words",
                "target_words": ["mindful", "demure"],
            },
        )
    )

    # Construct the URI
    action_ref_uri = published_ref.uri()

    # Part 2: Demonstrate manual feedback (this is not user-facing)
    @weave.op
    def example_op(input: str) -> str:
        return input + "!!!"

    _, call1 = example_op.call("i've been very distracted today")

    res = client.server.feedback_create(
        FeedbackCreateReq.model_validate(
            {
                "project_id": client._project_id(),
                "weave_ref": call1.ref.uri(),
                "feedback_type": "wandb.runnable." + action_name,
                "runnable_ref": action_ref_uri,
                "payload": {
                    "output": False,
                },
            }
        )
    )

    feedbacks = list(call1.feedback)
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback.feedback_type == "wandb.runnable." + action_name
    assert feedback.runnable_ref == action_ref_uri
    assert feedback.payload == {"output": False}

    # Step 3: test that we can in-place execute one action at a time.

    _, call2 = example_op.call("i've been very mindful today")

    res = client.server.actions_execute_batch(
        ActionsExecuteBatchReq.model_validate(
            {
                "project_id": client._project_id(),
                "action_ref": action_ref_uri,
                "call_ids": [call2.id],
            }
        )
    )

    feedbacks = list(call2.feedback)
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback.feedback_type == "wandb.runnable." + action_name
    assert feedback.runnable_ref == action_ref_uri
    assert feedback.payload == {"output": True}


def test_action_lifecycle_llm_judge(client: WeaveClient):
    if client_is_sqlite(client):
        return pytest.skip("skipping for sqlite")

    action_name = "response_is_mindful"

    published_ref = weave.publish(
        ActionDefinition(
            name=action_name,
            spec={
                "action_type": "llm_judge",
                "model": "gpt-4o-mini",
                "prompt": "Is the response mindful?",
                "response_format": {"type": "boolean"},
            },
        )
    )

    # Construct the URI
    action_ref_uri = published_ref.uri()

    @weave.op
    def example_op(input: str) -> str:
        return input + "."

    # Step 2: test that we can in-place execute one action at a time.
    _, call = example_op.call("i've been very meditative and mindful today")

    with secret_fetcher_context(DummySecretFetcher()):
        res = client.server.actions_execute_batch(
            ActionsExecuteBatchReq.model_validate(
                {
                    "project_id": client._project_id(),
                    "action_ref": action_ref_uri,
                    "call_ids": [call.id],
                }
            )
        )

    feedbacks = list(call.feedback)
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback.feedback_type == "wandb.runnable." + action_name
    assert feedback.runnable_ref == action_ref_uri
    assert feedback.payload == {"output": True}
