import weave
from weave.builtin_objects.models.CompletionModel import LiteLLMCompletionModel
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi

model_args = {
    "model": "gpt-4o",
    "messages_template": [{"role": "user", "content": "{input}"}],
    "response_format": {
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
}

input_text = "My name is Carlos and I am 42 years old."

expected_result = {"age": 42, "name": "Carlos"}


def test_model_publishing_alignment(client: WeaveClient):
    model = LiteLLMCompletionModel(**model_args)
    publish_ref = weave.publish(model)

    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "LiteLLMCompletionModel",
                    "val": model_args,
                    "set_leaf_object_class": "LiteLLMCompletionModel",
                }
            }
        )
    )

    assert obj_create_res.digest == publish_ref.digest

    gotten_model = weave.ref(publish_ref.uri()).get()
    assert isinstance(gotten_model, LiteLLMCompletionModel)


def test_model_local_create_local_use(client: WeaveClient):
    model = LiteLLMCompletionModel(**model_args)
    predict_result = model.predict(input=input_text)
    assert predict_result == expected_result


def test_model_local_create_remote_use(client: WeaveClient):
    model = LiteLLMCompletionModel(**model_args)
    publish_ref = weave.publish(model)
    remote_call_res = client.server.call_method(
        tsi.CallMethodReq.model_validate(
            {
                "project_id": client._project_id(),
                "object_ref": publish_ref.uri(),
                "method_name": "predict",
                "args": {"input": input_text},
            }
        )
    )
    assert remote_call_res.output == expected_result

    remote_call_read = client.server.call_read(
        tsi.CallReadReq.model_validate(
            {
                "project_id": client._project_id(),
                "id": remote_call_res.call_id,
            }
        )
    )
    assert remote_call_read.call.output == expected_result


def test_model_remote_create_local_use(client: WeaveClient):
    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "LiteLLMCompletionModel",
                    "val": model_args,
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
    assert isinstance(fetched, LiteLLMCompletionModel)
    predict_res = fetched.predict(input=input_text)
    assert predict_res == expected_result


def test_model_remote_create_remote_use(client: WeaveClient):
    obj_create_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "LiteLLMCompletionModel",
                    "val": model_args,
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
                "args": {"input": input_text},
            }
        )
    )
    assert obj_call_res.output == expected_result

    remote_call_read = client.server.call_read(
        tsi.CallReadReq.model_validate(
            {
                "project_id": client._project_id(),
                "id": obj_call_res.call_id,
            }
        )
    )
    assert remote_call_read.call.output == expected_result
