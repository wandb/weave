import weave
from weave.builtin_objects.models.CompletionModel import LiteLLMCompletionModel
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def test_publishing_alignment(client: WeaveClient):
    model = LiteLLMCompletionModel(
        model="gpt-4o", messages_template=[{"role": "user", "content": "{input}"}]
    )
    publish_ref = weave.publish(model)

    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "LiteLLMCompletionModel",
                    "val": {
                        "model": "gpt-4o",
                        "messages_template": [{"role": "user", "content": "{input}"}],
                    },
                    "set_leaf_object_class": "LiteLLMCompletionModel",
                }
            }
        )
    )

    assert obj_create_res.digest == publish_ref.digest


def test_local_create_local_use(client: WeaveClient):
    model = LiteLLMCompletionModel(
        model="gpt-4o",
        messages_template=[{"role": "user", "content": "{input}"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "Person",
                "schema": {
                    "type": "object",
                    "properties": {
                        "age": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                },
            },
        },
    )
    predict_result = model.predict(input="My name is Carlos and I am 42 years old.")
    assert predict_result == {"age": 42, "name": "Carlos"}


def test_local_create_remote_use(client: WeaveClient):
    model = LiteLLMCompletionModel(
        model="gpt-4o", messages_template=[{"role": "user", "content": "{input}"}]
    )
    publish_ref = weave.publish(model)
    remote_call_res = client.server.call_method(
        tsi.CallMethodReq.model_validate(
            {
                "project_id": client._project_id(),
                "object_ref": publish_ref.uri(),
                "method_name": "predict",
                "args": {"input": "Hello, World!"},
            }
        )
    )
    assert remote_call_res.call.output == "Hello, World!"

    remote_call_query = client.server.calls_query(
        tsi.CallReadReq.model_validate(
            {
                "project_id": client._project_id(),
                "id": remote_call_res.call.id,
            }
        )
    )
    assert remote_call_query.call.output == "Hello, World!"


def test_remote_create_local_use(client: WeaveClient):
    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "LiteLLMCompletionModel",
                    "val": {
                        "model": "gpt-4o",
                        "messages_template": [{"role": "user", "content": "{input}"}],
                    },
                    "set_leaf_object_class": "LiteLLMCompletionModel",
                }
            }
        )
    )
    obj_ref = ObjectRef(
        entity=client._project_id().split("/")[0],
        project=client._project_id().split("/")[1],
        name="LiteLLMCompletionModel",
        _digest=obj_create_res.digest,
    )
    fetched = obj_ref.get()
    predict_res = fetched.predict(input="Hello, World!")
    assert predict_res == "Hello, World!"


def test_remote_create_remote_use(client: WeaveClient):
    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "LiteLLMCompletionModel",
                    "val": {
                        "model": "gpt-4o",
                        "messages_template": [{"role": "user", "content": "{input}"}],
                    },
                    "set_leaf_object_class": "LiteLLMCompletionModel",
                }
            }
        )
    )
    obj_ref = ObjectRef(
        entity=client._project_id().split("/")[0],
        project=client._project_id().split("/")[1],
        name="LiteLLMCompletionModel",
        _digest=obj_create_res.digest,
    )
    obj_call_res = client.server.call_method(
        tsi.CallMethodReq.model_validate(
            {
                "project_id": client._project_id(),
                "object_ref": obj_ref.uri(),
                "method_name": "predict",
                "args": {"input": "Hello, World!"},
            }
        )
    )
    assert obj_call_res.call.output == "Hello, World!"
