from concurrent.futures import Future
from dataclasses import replace
from typing import TypeVar

import pytest

import weave
from weave.flow.obj import Object
from weave.flow.prompt.prompt import EasyPrompt
from weave.trace.objectify import register_object
from weave.trace.refs import RefWithExtra
from weave.trace_server.trace_server_interface import ObjectVersionFilter, ObjQueryReq

T = TypeVar("T")


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


def resolve_ref_futures(ref: RefWithExtra) -> RefWithExtra:
    """This is a bit of a hack to resolve futures in an initally unsaved object's extra fields.

    Currently, the extras are still a Future and not yet replaced with the actual value.
    This function resolves the futures and replaces them with the actual values.
    """
    extras = ref._extra
    new_extras = []
    for name, val in zip(extras[::2], extras[1::2]):
        if isinstance(val, Future):
            val = val.result()
        new_extras.append(name)
        new_extras.append(val)
    ref = replace(ref, _extra=tuple(new_extras))
    return ref


def test_drill_down_dataset_refs_same_after_publishing(client):
    ds = weave.Dataset(
        name="test",
        rows=[{"a": {"b": 1}}, {"a": {"b": 2}}, {"a": {"b": 3}}],
    )
    ref = weave.publish(ds)
    ds2 = ref.get()
    ref2 = weave.publish(ds2)
    ds3 = ref2.get()

    assert resolve_ref_futures(ds.rows.ref) == ds2.rows.ref
    for row, row2 in zip(ds.rows, ds2.rows):
        assert resolve_ref_futures(row.ref) == row2.ref
        assert resolve_ref_futures(row["a"].ref) == row2["a"].ref
        assert resolve_ref_futures(row["a"]["b"].ref) == row2["a"]["b"].ref

    assert ds2.ref == ds3.ref
    for row2, row3 in zip(ds2.rows, ds3.rows):
        assert row2.ref == row3.ref
        assert row2["a"].ref == row3["a"].ref
        assert row2["a"]["b"].ref == row3["a"]["b"].ref

    assert ds3.rows == [{"a": {"b": 1}}, {"a": {"b": 2}}, {"a": {"b": 3}}]
    for i, row in enumerate(ds3.rows, 1):
        assert row == {"a": {"b": i}}
        assert row["a"] == {"b": i}
        assert row["a"]["b"] == i


def test_registration():
    # This is a second class named Dataset.  The first has already been registered
    # in weave.flow.obj.  This should raise an error.

    with pytest.raises(ValueError, match="Class Dataset already registered as"):

        @register_object
        class Dataset(Object):
            anything: str
            doesnt_matter: int
