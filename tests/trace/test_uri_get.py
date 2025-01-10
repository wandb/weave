import pytest

import weave


@pytest.fixture(
    params=[
        "dataset",
        "model",
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
    elif request.param == "model":

        class SimpleModel(weave.Model):
            @weave.op()
            def predict(self, question: str) -> dict:
                return {"answer": "4"}

        return SimpleModel()
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

    for field in obj.model_fields:
        assert getattr(obj, field.name) == getattr(obj2, field.name)
