import pytest

import weave
from weave.flow.prompt.prompt import EasyPrompt
from weave.trace_server.trace_server_interface import ObjectVersionFilter, ObjQueryReq


@pytest.fixture(
    params=[
        "dataset",
        "evaluation",
        "string_prompt",
        "messages_prompt",
        "easy_prompt",
    ]
)
def obj(request):
    examples = [
        {"question": "What is 2+2?", "expected": "4"},
        {"question": "What is 3+3?", "expected": "6"},
    ]

    if request.param == "dataset":
        return weave.Dataset(rows=examples)
    elif request.param == "evaluation":
        return weave.Evaluation(dataset=examples)
    elif request.param == "string_prompt":
        return weave.StringPrompt("Hello, world!")
    elif request.param == "messages_prompt":
        return weave.MessagesPrompt([{"role": "user", "content": "Hello, world!"}])
    elif request.param == "easy_prompt":
        return weave.EasyPrompt("Hello world!")


def test_ref_get(client, obj):
    ref = weave.publish(obj)

    obj_cls = type(obj)
    obj2 = obj_cls.from_uri(ref.uri())
    obj3 = ref.get()
    assert isinstance(obj2, obj_cls)
    assert isinstance(obj3, obj_cls)

    for field_name in obj.model_fields:
        obj_field_val = getattr(obj, field_name)
        obj2_field_val = getattr(obj2, field_name)
        obj3_field_val = getattr(obj3, field_name)

        # This is a special case for EasyPrompt's unique init signature where `config`
        # represents the kwargs passed into the class itself.  Since the original object
        # has not been published, there is no ref and the key is omitted from the first
        # `config`.  After publishing, there is a ref so the `config` dict has an
        # additional `ref` key.  For comparison purposes, we pop the key to ensure the
        # rest of the config dict is the same.
        if obj_cls is EasyPrompt and field_name == "config":
            obj2_field_val.pop("ref")
            obj3_field_val.pop("ref")

        assert obj_field_val == obj2_field_val
        assert obj_field_val == obj3_field_val


@pytest.mark.asyncio
async def test_gotten_methods(client):
    @weave.op
    def model(a: int) -> int:
        return a + 1

    ev = weave.Evaluation(dataset=[{"a": 1}])
    await ev.evaluate(model)
    ref = weave.publish(ev)

    ev2 = weave.Evaluation.from_uri(ref.uri())
    await ev2.evaluate(model)

    # Ensure that the Evaluation object we get back is equivalent to the one published.
    # If they are the same, calling evaluate again should not publish new versions of any
    # relevant objects of ops.
    relevant_object_ids = [
        "model",
        "Evaluation.evaluate",
        "Evaluation.predict_and_score",
        "Evaluation.summarize",
        "Dataset",
        "example_evaluation",
    ]
    # TODO: Replace with client version of this query when available
    res = client.server.objs_query(
        ObjQueryReq(
            project_id=client._project_id(),
            filter=ObjectVersionFilter(object_ids=relevant_object_ids),
        )
    )
    for obj in res.objs:
        assert obj.version_index == 0
        assert obj.is_latest == 1
