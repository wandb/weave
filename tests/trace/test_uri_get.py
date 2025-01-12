import pytest

import weave
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


def test_uri_get(client, obj):
    ref = weave.publish(obj)

    obj_cls = type(obj)
    obj2 = obj_cls.from_uri(ref.uri())

    assert isinstance(obj, obj_cls)
    assert isinstance(obj2, obj_cls)

    for field_name in obj.model_fields:
        assert getattr(obj, field_name) == getattr(obj2, field_name)


@pytest.mark.asyncio
async def test_gotten_methods(client, obj):
    @weave.op
    def model(a: int) -> int:
        return a + 1

    ev = weave.Evaluation(dataset=[{"a": 1}])
    await ev.evaluate(model)
    ref = weave.publish(ev)

    ev2 = weave.Evaluation.from_uri(ref.uri())
    await ev2.evaluate(model)

    # TODO: Replace with client versions when they are available

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
    res = client.server.objs_query(
        ObjQueryReq(project_id=client._project_id()),
        filter=ObjectVersionFilter(object_ids=relevant_object_ids),
    )
    for obj in res:
        assert obj.version_index == 0
        assert obj.is_latest == 1
