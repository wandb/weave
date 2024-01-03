import pytest
import weave
import typing

from .. import ref_base


@pytest.mark.skip("failing in ci")
def test_digestrefs():
    with weave.local_client():
        ds = weave.WeaveList(
            [
                {
                    "id": "0",
                    "val": 100,
                },
                {
                    "id": "0",
                    "val": 101,
                },
            ]
        )

        ds0_ref = weave.publish(ds, "digestrefs")

        ds0 = weave.ref(str(ds0_ref)).get()

        @weave.op()
        def add5_to_row(row: typing.Any) -> int:
            return row["val"] + 5

        ds0_row0 = ds0[0]

        ds0_row0_ref = ref_base.get_ref(ds0_row0)
        assert ds0_row0_ref != None

        x = add5_to_row(ds0_row0)

        calls = ds0_row0_ref.input_to()
        assert len(calls) == 1

        ds = ds + [{"id": 2, "val": -10}]
        ds1_ref = weave.publish(ds, "digestrefs")

        ds1 = weave.ref(str(ds1_ref)).get()
        ds1_row0 = ds1[0]
        ds1_row0_ref = ref_base.get_ref(ds1_row0)

        assert ds1_row0_ref is not None

        assert ds0_row0_ref.digest == ds1_row0_ref.digest

        assert len(ds1_row0_ref.input_to()) == 0
        assert len(ds1_row0_ref.value_input_to()) == 1


def test_output_of():
    with weave.local_client():

        @weave.op()
        def add_5(v: int) -> int:
            return v + 5

        result = add_5(10)

        run = weave.output_of(result)
        assert run is not None
        assert "add_5" in run.op_name
        assert run.inputs["v"] == 10

        result2 = add_5(result)
        run = weave.output_of(result2)
        assert run is not None
        assert "add_5" in run.op_name

        # v_input is a ref here and we have to deref it
        # TODO: this is not consistent. Shouldn't it already be
        # dereffed recursively when we get it from weave.output_of() ?
        v_input = run.inputs["v"].get()
        assert v_input == 15

        run = weave.output_of(v_input)
        assert run is not None
        assert "add_5" in run.op_name
        assert run.inputs["v"] == 10


@pytest.mark.skip("failing in ci")
def test_vectorrefs(cache_mode_minimal):
    with weave.local_client():
        items = weave.WeaveList([1, 2])
        items_ref = weave.publish(items, "vectorrefs")

        @weave.op()
        def add_5(v: int) -> int:
            return v + 5

        result = items.apply(lambda item: add_5(item))

        result_row0 = result[0]
        run = weave.output_of(result_row0)
        assert run is not None
        assert "add_5" in run.op_name
        assert run.inputs["v"] == 1

        result_row1 = result[1]
        run = weave.output_of(result_row1)
        assert run is not None
        assert "add_5" in run.op_name
        assert run.inputs["v"] == 2


def test_weaveflow_op_wandb(user_by_api_key_in_env):
    with weave.wandb_client("weaveflow_example"):

        @weave.op()
        def custom_adder(a: int, b: int) -> int:
            return a + b

        res = custom_adder(1, 2)
        assert res == 3


def test_weaveflow_op_wandb_return_list(user_by_api_key_in_env):
    with weave.wandb_client("weaveflow_example"):

        @weave.op()
        def custom_adder(a: int, b: int) -> list[int]:
            return [a + b]

        res = custom_adder(1, 2)
        assert res == [3]


def test_weaveflow_object_wandb_with_opmethod(user_by_api_key_in_env):
    with weave.wandb_client("weaveflow_example"):

        @weave.type()
        class ATestObj:
            a: int

            @weave.op()
            def a_test_add(self, b: int) -> int:
                return self.a + b

        x = ATestObj(a=1)
        res = x.a_test_add(2)
        assert res == 3
