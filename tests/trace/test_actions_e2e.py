import pytest

import weave
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server.interface.base_models.action_base_models import (
    ConfiguredAction,
    ConfiguredContainsWordsAction,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.trace_server.trace_server_interface import (
    ActionsExecuteBatchReq,
    FeedbackCreateReq,
    ObjCreateReq,
    ObjQueryReq,
)


def test_action_execute_workflow(client: WeaveClient):
    is_sqlite = isinstance(client.server._internal_trace_server, SqliteTraceServer)  # type: ignore
    if is_sqlite:
        # dont run this test for sqlite
        return

    action_name = "test_action"
    # part 1: create the action
    digest = client.server.obj_create(
        ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": action_name,
                    "base_object_class": "ConfiguredAction",
                    "val": ConfiguredAction(
                        name="test_action",
                        config=ConfiguredContainsWordsAction(
                            target_words=["mindful", "demure"]
                        ),
                    ).model_dump(),
                }
            }
        )
    ).digest

    configured_actions = client.server.objs_query(
        ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["ConfiguredAction"]},
            }
        )
    )

    assert len(configured_actions.objs) == 1
    assert configured_actions.objs[0].digest == digest
    action_ref_uri = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=action_name,
        _digest=digest,
    ).uri()

    # part 2: manually create feedback
    @weave.op
    def example_op(input: str) -> str:
        return input[::-1]

    _, call1 = example_op.call("i've been very mindful today")
    with pytest.raises(Exception):
        client.server.feedback_create(
            FeedbackCreateReq.model_validate(
                {
                    "project_id": client._project_id(),
                    "weave_ref": call1.ref.uri(),
                    "feedback_type": "MachineScore",
                    "payload": True,
                }
            )
        )

    res = client.server.feedback_create(
        FeedbackCreateReq.model_validate(
            {
                "project_id": client._project_id(),
                "weave_ref": call1.ref.uri(),
                "feedback_type": "MachineScore",
                "payload": {
                    "runnable_ref": action_ref_uri,
                    "value": {action_name: {digest: True}},
                },
            }
        )
    )

    feedbacks = list(call1.feedback)
    assert len(feedbacks) == 1
    assert feedbacks[0].payload == {
        "runnable_ref": action_ref_uri,
        "value": {action_name: {digest: True}},
        "call_ref": None,
        "trigger_ref": None,
    }

    # Step 3: test that we can in-place execute one action at a time.

    _, call2 = example_op.call("i've been very meditative today")

    res = client.server.actions_execute_batch(
        ActionsExecuteBatchReq.model_validate(
            {
                "project_id": client._project_id(),
                "call_ids": [call2.id],
                "configured_action_ref": action_ref_uri,
            }
        )
    )

    feedbacks = list(call2.feedback)
    assert len(feedbacks) == 1
    assert feedbacks[0].payload == {
        "runnable_ref": action_ref_uri,
        "value": {action_name: {digest: False}},
        "call_ref": None,
        "trigger_ref": None,
    }
