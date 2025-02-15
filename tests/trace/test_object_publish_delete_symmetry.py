from copy import deepcopy

import pytest
from typing_extensions import Self

import weave
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject
from weave.trace_server.errors import ObjectDeletedError


@register_object
class CustomObject(weave.Object):
    a: int
    b: str

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        return cls(a=obj.a, b=obj.b)


@pytest.fixture
def custom_object() -> weave.Object:
    return CustomObject(a=1, b="hello")


def test_object_publish(client, custom_object):
    custom_object.publish()
    obj2 = custom_object.ref.get()
    assert isinstance(obj2, CustomObject)
    assert obj2.a == 1
    assert obj2.b == "hello"


def test_object_publish_imperative(client, custom_object):
    weave.publish(custom_object)
    obj2 = custom_object.ref.get()
    assert isinstance(obj2, CustomObject)
    assert obj2.a == 1
    assert obj2.b == "hello"


def test_object_delete(client, custom_object):
    custom_object.publish()
    obj2 = custom_object.ref.get()

    obj2.delete()
    with pytest.raises(ObjectDeletedError):
        obj2.ref.get()


def test_object_delete_imperative(client, custom_object):
    custom_object.publish()

    weave.delete(custom_object)
    with pytest.raises(ObjectDeletedError):
        custom_object.ref.get()


def test_object_lifecycle(client, custom_object):
    ref = custom_object.publish()

    custom_object.a = 2
    ref2 = custom_object.publish()

    custom_object.b = "world"
    ref3 = custom_object.publish()

    custom_object.a = 3
    ref4 = custom_object.publish()

    ref2.delete()
    weave.delete(ref4)

    res = ref.get()
    assert res.a == 1
    assert res.b == "hello"

    with pytest.raises(ObjectDeletedError):
        ref2.get()

    res = ref3.get()
    assert res.a == 2
    assert res.b == "world"

    with pytest.raises(ObjectDeletedError):
        ref4.get()


def test_failed_publish_maintains_old_object_ref(client, custom_object, monkeypatch):
    old_ref = custom_object.ref

    with pytest.raises(RuntimeError):
        with monkeypatch.context() as m:

            def fail_publish(*args, **kwargs):
                raise RuntimeError("Publish failed")

            m.setattr("weave._publish", fail_publish)
            custom_object.publish()

    assert custom_object.ref == old_ref


def test_saving_only_for_registered_objects(client):
    class UnregisteredObject(weave.Object):
        a: int
        b: str

    unregistered_object = UnregisteredObject(a=1, b="hello")

    with pytest.raises(NotImplementedError):
        unregistered_object.publish()


def test_saving_symmetry(client, custom_object):
    custom_object2 = deepcopy(custom_object)

    ref = weave.publish(custom_object)
    ref2 = custom_object2.publish()

    assert ref == ref2


def test_delete_symmetry(client, custom_object):
    # publishing the same object will result in dedupe,
    # so change a value to test deleting
    custom_object2 = deepcopy(custom_object)
    custom_object2.a = 2

    ref = weave.publish(custom_object)
    ref2 = weave.publish(custom_object2)

    obj = ref.get()
    weave.delete(obj)

    obj2 = ref2.get()
    obj2.delete()

    with pytest.raises(ObjectDeletedError):
        ref.get()

    with pytest.raises(ObjectDeletedError):
        ref2.get()
