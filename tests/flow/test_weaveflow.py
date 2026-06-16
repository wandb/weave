from dataclasses import dataclass

import numpy as np
import pytest
from pydantic import Field

import weave


def test_weaveflow_basic_ops(weave_active):
    """Plain ops, list-returning ops, and nested op composition."""

    @weave.op
    def custom_adder(a: int, b: int) -> int:
        return a + b

    @weave.op
    def custom_adder_list(a: int, b: int) -> list[int]:
        return [a + b]

    @weave.op
    def double_adder(a: int, b: int) -> int:
        return custom_adder(a, a) + custom_adder(b, b)

    assert custom_adder(1, 2) == 3
    assert custom_adder_list(1, 2) == [3]
    assert double_adder(1, 2) == 6


def test_weaveflow_op_methods(weave_active):
    """Op methods on weave.Object: call result and qualified op name."""

    class ATestObj(weave.Object):
        a: int

        @weave.op
        def a_test_add(self, b: int) -> int:
            return self.a + b

    x = ATestObj(a=1)
    assert x.a_test_add(2) == 3

    model = MyModel(a=1)
    assert model.predict.name == "MyModel.predict"
    assert MyModel.predict.name == "MyModel.predict"


@pytest.mark.asyncio
async def test_async_ops(weave_active):
    @weave.op
    async def async_op_add1(v: int) -> int:
        return v + 1

    @weave.op
    async def async_op_add5(v: int) -> int:
        for _i in range(5):
            v = await async_op_add1(v)
        return v

    result = await async_op_add5(10)
    assert result == 15

    assert len(list(async_op_add5.calls())) == 1
    assert len(list(async_op_add1.calls())) == 5


def test_weaveflow_publish_numpy(weave_active):
    v = {"a": np.array([[1, 2, 3], [4, 5, 6]])}
    ref = weave.publish(v, "dict-with-numpy")


@pytest.mark.parametrize("declaration", ["undeclared", "declared", "closure"])
def test_weaveflow_unknown_type_op_param(declaration):
    """Ops accept an unknown-typed param whether undeclared, declared, or closed over."""

    @dataclass
    class SomeUnknownObject:
        x: int

    if declaration == "undeclared":

        @weave.op
        def op_with_unknown_param(v) -> int:
            return v.x + 2

        assert op_with_unknown_param(SomeUnknownObject(x=10)) == 12
    elif declaration == "declared":

        @weave.op
        def op_with_unknown_param(v: SomeUnknownObject) -> int:
            return v.x + 2

        assert op_with_unknown_param(SomeUnknownObject(x=10)) == 12
    elif declaration == "closure":
        v = SomeUnknownObject(x=10)

        @weave.op
        def op_with_unknown_param() -> int:
            return v.x + 2

        assert op_with_unknown_param() == 12
    else:
        raise ValueError(f"unhandled declaration: {declaration}")


def test_dataset_save_and_ref_flows(client):
    """Saved dataset: subobj-ref passing into an op and ref round-trip into Evaluation."""
    dataset = client.save(
        weave.Dataset(rows=[{"x": 1, "y": 3}, {"x": 2, "y": 16}]), "my-dataset"
    )

    @weave.op
    def get_item(row):
        return {"in": row["x"], "out": row["x"]}

    res = get_item(dataset.rows[0])
    assert res == {"in": 1, "out": 1}

    ref = dataset.ref
    assert ref is not None
    dataset2 = weave.ref(ref.uri).get()
    weave.Evaluation(dataset=dataset2)


def test_agent_has_tools(client):
    @weave.op
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


def test_weave_op_mutates_and_returns_same_object(weave_active):
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


class MyModel(weave.Model):
    a: int

    @weave.op
    def predict(self, x: int) -> int:
        return x + 1
