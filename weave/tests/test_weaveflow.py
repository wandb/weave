import pytest
import weave
from weave import weaveflow
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


def test_vectorrefs_int(cache_mode_minimal):
    with weave.local_client():
        items = weave.WeaveList([1, 2])
        items_ref = weave.publish(items, "vectorrefs")

        @weave.op()
        def add_5(v: int) -> int:
            return v + 5

        result = items.apply(lambda item: add_5(item))
        breakpoint()

        result_row0 = result[0]
        run = weave.output_of(result_row0)
        assert run is not None
        assert "add_5" in run.op_name
        assert run.inputs["v"].get() == 1

        result_row1 = result[1]
        run = weave.output_of(result_row1)
        assert run is not None
        assert "add_5" in run.op_name
        assert run.inputs["v"].get() == 2


def test_vectorrefs_dict_output(cache_mode_minimal):
    with weave.local_client():
        items = weave.WeaveList([1, 2])
        items_ref = weave.publish(items, "vectorrefs")

        @weave.op()
        def add_5(v: int):
            return {"out": v + 5}

        result = items.apply(lambda item: add_5(item))

        result_row0 = result[0]
        run = weave.output_of(result_row0)
        breakpoint()
        pass
        # assert run is not None
        # assert "add_5" in run.op_name
        # assert run.inputs["v"].get() == 1

        # result_row1 = result[1]
        # run = weave.output_of(result_row1)
        # assert run is not None
        # assert "add_5" in run.op_name
        # assert run.inputs["v"].get() == 2


def test_evaluate(cache_mode_minimal):
    from weave import weaveflow

    # An eval example:

    with weave.local_client():
        dataset = weave.publish(
            weaveflow.Dataset(
                [
                    {"id": "0", "x": 0, "y": 0, "out": 0},
                    {"id": "0", "x": 1, "y": 1, "out": 1},
                    {"id": "0", "x": 2, "y": 1, "out": 2},
                ]
            ),
            "datasets",
        )

        @weave.type()
        class AddModel(weaveflow.Model):
            @weave.op()
            def predict(self, ex):
                return ex["x"] + ex["y"]

        @weave.type()
        class MultModel(weaveflow.Model):
            @weave.op()
            def predict(ex):
                return ex["x"]

        @weave.op()
        def extract_output(ex):
            return ex["out"]

        eval = weaveflow.ScoreExactMatch(extract_output)
        add_model = AddModel()
        result = weaveflow.evaluate2(eval, dataset, add_model)


# eval = Eval()
# eval.add_record(
