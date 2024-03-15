from typing import Any, Generator
import re
import pytest
import pydantic
import uuid
import weave
import asyncio
from weave import op_def, Evaluation

from weave import weave_client
from weave.api import client as weave_api_client
from weave.trace_server import (
    clickhouse_trace_server_batched,
)


class RegexStringMatcher(str):
    def __init__(self, pattern):
        self.pattern = pattern

    def __eq__(self, other_string):
        if not isinstance(other_string, str):
            return NotImplemented
        return bool(re.match(self.pattern, other_string))


@pytest.fixture
def client() -> Generator[weave_client.WeaveClient, None, None]:
    clickhouse_trace_server = (
        clickhouse_trace_server_batched.ClickHouseTraceServer.from_env(
            use_async_insert=False
        )
    )
    clickhouse_trace_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
    clickhouse_trace_server.ch_client.command("DROP DATABASE IF EXISTS default")
    clickhouse_trace_server._run_migrations()
    with weave_api_client("shawn/test-project") as client:
        yield client


@pytest.mark.skip()
def test_table_create(server):
    table_ref = server.new_table([1, 2, 3])
    assert list(r.val for r in server.table_query(table_ref)) == [1, 2, 3]
    assert list(r.val for r in server.table_query(table_ref, offset=1)) == [2, 3]
    assert list(r.val for r in server.table_query(table_ref, offset=1, limit=1)) == [2]
    # TODO: This doesn't work
    # assert list(server._table_query(table_ref, filter={"": 2})) == [2]


@pytest.mark.skip()
def test_table_append(server):
    table_ref = server.new_table([1, 2, 3])
    new_table_ref, item_id = server.table_append(table_ref, 4)
    assert list(r.val for r in server.table_query(new_table_ref)) == [1, 2, 3, 4]


@pytest.mark.skip()
def test_table_remove(server):
    table_ref0 = server.new_table([1])
    table_ref1, item_id2 = server.table_append(table_ref0, 2)
    table_ref2, item_id3 = server.table_append(table_ref1, 3)
    table_ref3 = server.table_remove(table_ref2, item_id2)
    assert list(r.val for r in server.table_query(table_ref3)) == [1, 3]


@pytest.mark.skip()
def new_val_single(server):
    obj_id = server.new_val(42)
    assert server.get(obj_id) == 42


@pytest.mark.skip()
def test_new_val_with_list(server):
    ref = server.new_val({"a": [1, 2, 3]})
    server_val = server.get_val(ref)
    table_ref = server_val["a"]
    assert isinstance(table_ref, chobj.TableRef)
    table_val = server.table_query(table_ref)
    assert list(r.val for r in table_val) == [1, 2, 3]


@pytest.mark.skip()
def test_object(server):
    obj_ref = server.new_object({"a": 43}, "my-obj", "latest")
    val_ref = server._resolve_object("my-obj", "latest")
    assert obj_ref.val_id == val_ref.val_id
    assert server._resolve_object("my-obj", "latest2") is None


def test_save_load(client):
    saved_val = client.save({"a": [1, 2, 3]}, "my-obj")
    val = client.get(saved_val.ref)
    val_table = list(val["a"])
    assert val_table[0] == 1
    assert val_table[1] == 2
    assert val_table[2] == 3


@pytest.mark.skip()
def test_dataset_refs(client):
    ref = client.save(weave.Dataset(rows=[1, 2, 3]), "my-dataset")
    new_table_rows = []
    for row in ref.rows:
        new_table_rows.append({"a_ref": row, "b": row + 42})
    ref2 = client.save(new_table_rows, "my-dataset2")
    ref2_list = list(ref2)

    # if we access a_ref values, we actually get values, but we
    # can also get correct references.
    # TODO: shit this is wrong... those should be the underlying
    # refs I think?

    row0 = ref2_list[0]
    ref0_aref = row0["a_ref"]
    assert ref0_aref == 1
    assert weave_client.get_ref(ref0_aref) == weave_client.ObjectRef(
        "my-dataset2",
        ref2.ref.val_id,
        ["id", RegexStringMatcher(".*,.*"), "key", "a_ref"],
    )

    row1 = ref2_list[1]
    ref1_aref = row1["a_ref"]
    assert ref1_aref == 2
    assert weave_client.get_ref(ref1_aref) == weave_client.ObjectRef(
        "my-dataset2",
        ref2.ref.val_id,
        ["id", RegexStringMatcher(".*,.*"), "key", "a_ref"],
    )

    row2 = ref2_list[2]
    ref2_aref = row2["a_ref"]
    assert ref2_aref == 3
    assert weave_client.get_ref(ref2_aref) == weave_client.ObjectRef(
        "my-dataset2",
        ref2.ref.val_id,
        ["id", RegexStringMatcher(".*,.*"), "key", "a_ref"],
    )


def test_pydantic(client):
    class PydanticObj(pydantic.BaseModel):
        a: int
        b: str

    val = PydanticObj(a=5, b="x")
    ref = client.save_object(val, "my-pydantic-obj")
    val2 = client.get(ref)
    assert val == val2


def test_call_create(client):
    call = client.create_call("x", None, {"a": 5, "b": 10})
    client.finish_call(call, "hello")
    result = client.call(call.id)
    assert result == weave_client.Call(
        op_name="x",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 5, "b": 10},
        id=call.id,
        output="hello",
    )


def test_calls_query(client):
    call0 = client.create_call("x", None, {"a": 5, "b": 10})
    call1 = client.create_call("x", None, {"a": 6, "b": 11})
    client.create_call("y", None, {"a": 5, "b": 10})
    result = list(client.calls(weave_client._CallsFilter(op_version_refs=["x"])))
    assert len(result) == 2
    assert result[0] == weave_client.Call(
        op_name="x",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 5, "b": 10},
        id=call0.id,
    )
    assert result[1] == weave_client.Call(
        op_name="x",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 6, "b": 11},
        id=call1.id,
    )


def test_dataset_calls(client):
    ref = client.save(
        weave.Dataset(rows=[{"doc": "xx", "label": "c"}, {"doc": "yy", "label": "d"}]),
        "my-dataset",
    )
    for row in ref.rows:
        client.create_call("x", None, {"a": row["doc"]})

    calls = list(client.calls({"op_name": "x"}))
    assert calls[0].inputs["a"] == "xx"
    assert calls[1].inputs["a"] == "yy"


@pytest.mark.skip()
def test_mutations(client):
    dataset = client.save(
        weave.Dataset(
            rows=[
                {"doc": "xx", "label": "c"},
                {"doc": "yy", "label": "d", "somelist": [{"a": 3, "b": 14}]},
            ]
        ),
        "my-dataset",
    )
    dataset.rows.append({"doc": "zz", "label": "e"})
    dataset.rows[1]["doc"] = "jjj"
    dataset.rows[1]["somelist"][0]["a"] = 12
    dataset.cows = "moo"
    assert dataset.mutations == [
        weave_client.MutationAppend(
            path=["attr", "rows"],
            operation="append",
            args=({"doc": "zz", "label": "e"},),
        ),
        weave_client.MutationSetitem(
            path=["attr", "rows", "id", RegexStringMatcher(".*,.*")],
            operation="setitem",
            args=("doc", "jjj"),
        ),
        weave_client.MutationSetitem(
            path=[
                "attr",
                "rows",
                "id",
                RegexStringMatcher(".*,.*"),
                "key",
                "somelist",
                "index",
                "0",
            ],
            operation="setitem",
            args=("a", 12),
        ),
        weave_client.MutationSetattr(
            path=[], operation="setattr", args=("cows", "moo")
        ),
    ]
    new_ref = dataset.save()
    new_ds = client.get(new_ref)
    assert new_ds.cows == "moo"
    new_ds_rows = list(new_ds.rows)
    assert new_ds_rows[0] == {"doc": "xx", "label": "c"}
    assert new_ds_rows[1] == {
        "doc": "jjj",
        "label": "d",
        "somelist": [{"a": 12, "b": 14}],
    }
    assert new_ds_rows[2] == {"doc": "zz", "label": "e"}


@pytest.mark.skip()
def test_stable_dataset_row_refs(client):
    dataset = client.save(
        weave.Dataset(
            rows=[
                {"doc": "xx", "label": "c"},
                {"doc": "yy", "label": "d", "somelist": [{"a": 3, "b": 14}]},
            ]
        ),
        "my-dataset",
    )
    call = client.create_call("x", {"a": dataset.rows[0]["doc"]})
    client.finish_call(call, "call1")
    dataset.rows.append({"doc": "zz", "label": "e"})
    dataset2_ref = dataset.save()
    dataset2 = client.get(dataset2_ref)
    call = client.create_call("x", {"a": dataset2.rows[0]["doc"]})
    client.finish_call(call, "call2")
    x = client.calls({"ref": weave_client.get_ref(dataset.rows[0]["doc"])})

    assert len(list(x)) == 2


def test_opdef(client):
    @weave.op()
    def add2(x, y):
        return x + y

    res = add2(1, 3)
    assert res == 4
    assert len(list(client.calls())) == 1


def test_saveload_customtype(client):
    @weave.op()
    def add2(x, y):
        return x + y

    @weave.op()
    def add3(x, y, z):
        return x + y + z

    obj = {"a": add2, "b": add3}
    ref = client.save_object(obj, "my-ops")
    obj2 = client.get(ref)
    assert isinstance(obj2["a"], op_def.OpDef)
    assert obj2["a"].name == "op-add2"
    assert isinstance(obj2["b"], op_def.OpDef)
    assert obj2["b"].name == "op-add3"


def test_save_unknown_type(client):
    class SomeUnknownThing:
        def __init__(self, a):
            self.a = a

    obj = SomeUnknownThing(3)
    ref = client.save_object(obj, "my-np-array")
    obj2 = client.get(ref)
    # Expect None for now
    assert obj2 == None


def test_save_model(client):
    class MyModel(weave.Model):
        prompt: str

        @weave.op()
        def predict(self, input):
            return self.prompt.format(input=input)

    model = MyModel(prompt="input is: {input}")
    ref = client.save_object(model, "my-model")
    model2 = client.get(ref)
    # TODO: wrong, have to manually pass self
    assert model2.predict(model2, "x") == "input is: x"


def test_evaluate(client):
    @weave.op()
    async def model_predict(input) -> str:
        return eval(input)

    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op()
    async def score(target, prediction):
        return target == prediction

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    expected_eval_result = {
        "prediction": {"mean": 9.5},
        "score": {"true_count": 1, "true_fraction": 0.5},
    }
    assert result == expected_eval_result


def test_obj_dedupe(client):
    client.save_object({"a": 1}, "my-obj")
    client.save_object({"a": 1}, "my-obj")
    client.save_object({"a": 2}, "my-obj")
    res = client.objects()
    assert len(res) == 2
    assert res[0].version_index == 1
    assert res[1].version_index == 2


# def test_publish_big_list(server):
#     import time

#     t = time.time()
#     big_list = list({"x": i, "y": i} for i in range(1000000))
#     print("create", time.time() - t)
#     t = time.time()
#     ref = server.new({"a": big_list})
#     print("insert", time.time() - t)
#     t = time.time()
#     res = server.get(ref)
#     print("get", time.time() - t)
#     assert res == {"a": big_list}
