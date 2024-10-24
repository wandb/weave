import os
from typing import Any

import pytest
from pydantic import BaseModel

import weave
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server.interface.base_models.action_base_models import (
    ConfiguredAction,
    _BuiltinAction,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.trace_server.trace_server_interface import (
    ExecuteBatchActionReq,
    FeedbackCreateReq,
    ObjCreateReq,
    ObjQueryReq,
)


def test_action_execute_workflow(client: WeaveClient):
    is_sqlite = isinstance(client.server._internal_trace_server, SqliteTraceServer)
    if is_sqlite:
        # dont run this test for sqlite
        return

    # part 1: create the action
    class ExampleResponse(BaseModel):
        score: int
        reason: str

    digest = client.server.obj_create(
        ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "test_object",
                    "base_object_class": "ConfiguredAction",
                    "val": ConfiguredAction(
                        name="test_action",
                        action=_BuiltinAction(name="llm_judge"),
                        config={
                            "system_prompt": "you are a judge",
                            "model": "gpt-4o-mini",
                            "response_format_schema": ExampleResponse.model_json_schema(),
                        },
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
        name="test_object",
        _digest=digest,
    ).uri()

    # part 2: manually create feedback
    @weave.op
    def example_op(input: str) -> str:
        return input[::-1]

    _, call1 = example_op.call("hello")
    with pytest.raises(Exception):
        client.server.feedback_create(
            FeedbackCreateReq.model_validate(
                {
                    "project_id": client._project_id(),
                    "weave_ref": call1.ref.uri(),
                    "feedback_type": "ActionScore",
                    "payload": {
                        "output": {
                            "score": 1,
                            "reason": "because",
                        }
                    },
                }
            )
        )

    res = client.server.feedback_create(
        FeedbackCreateReq.model_validate(
            {
                "project_id": client._project_id(),
                "weave_ref": call1.ref.uri(),
                "feedback_type": "ActionScore",
                "payload": {
                    "configured_action_ref": action_ref_uri,
                    "output": {
                        "score": 1,
                        "reason": "because",
                    },
                },
            }
        )
    )

    feedbacks = list(call1.feedback)
    assert len(feedbacks) == 1
    assert feedbacks[0].payload == {
        "configured_action_ref": action_ref_uri,
        "output": {
            "score": 1,
            "reason": "because",
        },
    }

    # Step 3: execute the action
    if os.environ.get("CI"):
        # skip this test in CI for now
        return

    _, call2 = example_op.call("hello")

    res = client.server.execute_batch_action(
        ExecuteBatchActionReq.model_validate(
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
        "configured_action_ref": action_ref_uri,
        "output": {
            "score": MatchesAnyNumber(),
            "reason": MatchesAnyStr(),
        },
    }


class MatchesAnyStr:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, str)


class MatchesAnyNumber(BaseModel):
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, (int, float))
