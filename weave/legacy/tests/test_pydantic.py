from typing import Any, Optional

import pydantic

import weave
from weave.legacy.weave import weave_types as types


def test_pydantic_type_inference():
    class TestPydanticClass(pydantic.BaseModel):
        a: int
        b: str
        c: float

    obj = TestPydanticClass(a=1, b="2", c=3.0)
    t = types.TypeRegistry.type_of(obj)
    assert isinstance(t, types.ObjectType)
    assert t.property_types() == {
        "a": types.Int(),
        "b": types.String(),
        "c": types.Float(),
    }


def test_save_load_pydantic():
    class TestPydanticClass(pydantic.BaseModel):
        a: int

    obj = TestPydanticClass(a=1)
    n = weave.save(obj)
    recovered = weave.use(n)
    assert recovered.a == 1


def test_pydantic_saveload(client):
    class Object(pydantic.BaseModel):
        name: Optional[str] = "hello"
        description: Optional[str] = None

    class A(Object):
        model_name: str

    class B(A):
        pass

    a = B(name="my-a", model_name="my-model")

    a_type = weave.type_of(a)
    assert a_type.root_type_class().__name__ == "A"

    weave.publish(a, name="my-a")

    a2 = weave.ref("my-a").get()
    assert a2.name == "my-a"
    assert a2.description is None
    assert a2.model_name == "my-model"


def test_pydantic_nested_type():
    class Child(pydantic.BaseModel):
        a: str

    class Parent(pydantic.BaseModel):
        child: Child
        b: int

    p = Parent(child=Child(a="hello"), b=1)
    t = weave.type_of(p)

    assert str(t) == "Parent(child=Child(a=String()), b=Int())"
    assert t.to_dict() == {
        "type": "Parent",
        "_base_type": {"type": "Object"},
        "_relocatable": True,
        "_is_object": True,
        "child": {
            "type": "Child",
            "_base_type": {"type": "Object"},
            "_relocatable": True,
            "_is_object": True,
            "a": "string",
        },
        "b": "int",
    }


def test_pydantic_v1(client):
    from pydantic import v1

    class MyV1Object(v1.BaseModel):
        val: int

    class MyWeaveObject(weave.Object):
        inner: Any
        # inner: MyV1Object # v1 properties not yet supported

    @weave.op
    def get_inner(obj: MyWeaveObject) -> int:
        return obj.inner.val

    res = get_inner(MyWeaveObject(inner=MyV1Object(val=1)))
    assert res == 1
