import logging

import numpy as np
from pydantic import Field

import weave
from weave.flow.obj import deprecated_field


def test_weaveflow_op_wandb(client):
    @weave.op()
    def custom_adder(a: int, b: int) -> int:
        return a + b

    res = custom_adder(1, 2)
    assert res == 3


def test_weaveflow_op_wandb_return_list(client):
    @weave.op()
    def custom_adder(a: int, b: int) -> list[int]:
        return [a + b]

    res = custom_adder(1, 2)
    assert res == [3]


def test_weaveflow_object_wandb_with_opmethod(client):
    class ATestObj(weave.Object):
        a: int

        @weave.op()
        def a_test_add(self, b: int) -> int:
            return self.a + b

    x = ATestObj(a=1)
    res = x.a_test_add(2)
    assert res == 3


def test_weaveflow_nested_op(client):
    @weave.op()
    def adder(a: int, b: int) -> int:
        return a + b

    @weave.op()
    def double_adder(a: int, b: int) -> int:
        return adder(a, a) + adder(b, b)

    res = double_adder(1, 2)
    assert res == 6


def test_async_ops(client):
    @weave.op()
    async def async_op_add1(v: int) -> int:
        return v + 1

    @weave.op()
    async def async_op_add5(v: int) -> int:
        for i in range(5):
            v = await async_op_add1(v)
        return v

    called = async_op_add5(10)
    import asyncio

    result = asyncio.run(called)
    assert result == 15

    assert len(list(async_op_add5.calls())) == 1
    assert len(list(async_op_add1.calls())) == 5


def test_weaveflow_publish_numpy(client):
    v = {"a": np.array([[1, 2, 3], [4, 5, 6]])}
    ref = weave.publish(v, "dict-with-numpy")


def test_weaveflow_unknown_type_op_param_undeclared():
    class SomeUnknownObject:
        x: int

        def __init__(self, x: int):
            self.x = x

    @weave.op()
    def op_with_unknown_param(v) -> int:
        return v.x + 2

    assert op_with_unknown_param(SomeUnknownObject(x=10)) == 12


def test_weaveflow_unknown_type_op_param_declared():
    class SomeUnknownObject:
        x: int

        def __init__(self, x: int):
            self.x = x

    @weave.op()
    def op_with_unknown_param(v: SomeUnknownObject) -> int:
        return v.x + 2

    assert op_with_unknown_param(SomeUnknownObject(x=10)) == 12


def test_weaveflow_unknown_type_op_param_closure():
    class SomeUnknownObject:
        x: int

        def __init__(self, x: int):
            self.x = x

    v = SomeUnknownObject(x=10)

    @weave.op()
    def op_with_unknown_param() -> int:
        return v.x + 2

    assert op_with_unknown_param() == 12


def test_subobj_ref_passing(client):
    dataset = client.save(
        weave.Dataset(rows=[{"x": 1, "y": 3}, {"x": 2, "y": 16}]), "my-dataset"
    )

    @weave.op()
    def get_item(row):
        return {"in": row["x"], "out": row["x"]}

    res = get_item(dataset.rows[0])
    assert res == {"in": 1, "out": 1}


class MyModel(weave.Model):
    a: int

    @weave.op()
    def predict(self, x: int) -> int:
        return x + 1


def test_op_method_name(client):
    model = MyModel(a=1)

    assert model.predict.name == "MyModel.predict"
    assert MyModel.predict.name == "MyModel.predict"


def test_agent_has_tools(client):
    @weave.op()
    def get_weather(city: str) -> str:
        return f"weather in {city} is sunny"

    agent = weave.Agent(
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        system_message="hello",
        tools=[get_weather],
    )
    saved = client.save(agent, "agent")

    assert len(saved.tools) == 1


def test_construct_eval_with_dataset_get(client):
    dataset = client.save(
        weave.Dataset(rows=[{"x": 1, "y": 3}, {"x": 2, "y": 16}]), "my-dataset"
    )
    ref = weave.obj_ref(dataset)
    assert ref is not None
    dataset2 = weave.ref(ref.uri()).get()
    weave.Evaluation(dataset=dataset2)


def test_weave_op_mutates_and_returns_same_object(client):
    class Thing(weave.Object):
        tools: list = Field(default_factory=list)

        @weave.op
        def append_tool(self, f):
            assert self.tools is self.tools
            self.tools.append(f)
            assert self.tools is self.tools

    thing = Thing()
    assert len(thing.tools) == 0
    assert thing.tools is thing.tools

    thing.append_tool(lambda: 1)
    assert len(thing.tools) == 1
    assert thing.tools is thing.tools

    thing.append_tool(lambda: 2)
    assert len(thing.tools) == 2
    assert thing.tools is thing.tools


def test_deprecated_field_warning(caplog):
    caplog.set_level(logging.WARNING)

    class TestObj(weave.Object):
        new_field: int = Field(..., alias="old_field")

        @deprecated_field("new_field")
        def old_field(self): ...

    # Using new field is the same, but you can access the old field name
    obj = TestObj(new_field=1)
    assert obj.new_field == obj.old_field == 1

    obj.new_field = 2
    assert obj.new_field == obj.old_field == 2

    # You can also instantiate with the old field name, but using it will show warnings
    obj = TestObj(old_field=1)
    with caplog.at_level(logging.WARNING):
        v = obj.old_field

    assert v == 1 == obj.new_field
    assert "Use `new_field` instead of `old_field`" in caplog.text

    caplog.clear()

    with caplog.at_level(logging.WARNING):
        obj.old_field = 2

    assert obj.new_field == obj.old_field == 2
    assert "Use `new_field` instead of `old_field`" in caplog.text

    caplog.clear()
