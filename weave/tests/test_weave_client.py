import re
import pytest
import pydantic
from pydantic import BaseModel
import weave
import asyncio
from weave import op_def, Evaluation

from weave import weave_client
from weave.trace.op import Op
from weave.trace.refs import (
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    DICT_KEY_EDGE_NAME,
)

from weave.trace import refs
from weave.trace.isinstance import weave_isinstance
from weave.trace_server.trace_server_interface import (
    TableCreateReq,
    TableSchemaForInsert,
    TableQueryReq,
    RefsReadBatchReq,
    FileCreateReq,
    FileContentReadReq,
)


class RegexStringMatcher(str):
    def __init__(self, pattern):
        self.pattern = pattern

    def __eq__(self, other_string):
        if not isinstance(other_string, str):
            return NotImplemented
        return bool(re.match(self.pattern, other_string))


def test_table_create(client):
    res = client.server.table_create(
        TableCreateReq(
            table=TableSchemaForInsert(
                project_id="test/test-project",
                rows=[
                    {TABLE_ROW_ID_EDGE_NAME: 1, "val": 1},
                    {TABLE_ROW_ID_EDGE_NAME: 2, "val": 2},
                    {TABLE_ROW_ID_EDGE_NAME: 3, "val": 3},
                ],
            )
        )
    )
    result = client.server.table_query(
        TableQueryReq(project_id="test/test-project", table_digest=res.digest)
    )
    assert result.rows[0].val["val"] == 1
    assert result.rows[1].val["val"] == 2
    assert result.rows[2].val["val"] == 3


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


def test_dataset_refs(client):
    ref = client.save(weave.Dataset(rows=[{"v": 1}, {"v": 2}]), "my-dataset")
    new_table_rows = []
    for row in ref.rows:
        new_table_rows.append({"a_ref": row["v"], "b": row["v"] + 42})
    ref2 = client.save(new_table_rows, "my-dataset2")

    row0 = ref2[0]
    ref0_aref = row0["a_ref"]
    assert ref0_aref == 1
    assert weave_client.get_ref(ref0_aref) == weave_client.ObjectRef(
        "shawn",
        "test-project",
        "my-dataset",
        ref.ref.version,
        [
            OBJECT_ATTR_EDGE_NAME,
            "rows",
            TABLE_ROW_ID_EDGE_NAME,
            RegexStringMatcher(".*"),
            DICT_KEY_EDGE_NAME,
            "v",
        ],
    )

    row1 = ref2[1]
    ref1_aref = row1["a_ref"]
    assert ref1_aref == 2
    assert weave_client.get_ref(ref0_aref) == weave_client.ObjectRef(
        "shawn",
        "test-project",
        "my-dataset",
        ref.ref.version,
        [
            OBJECT_ATTR_EDGE_NAME,
            "rows",
            TABLE_ROW_ID_EDGE_NAME,
            RegexStringMatcher(".*"),
            DICT_KEY_EDGE_NAME,
            "v",
        ],
    )


def test_obj_with_table(client):
    class ObjWithTable(weave.Object):
        table: weave_client.Table

    o = ObjWithTable(table=weave_client.Table([{"a": 1}, {"a": 2}, {"a": 3}]))
    res = client.save_object(o, "my-obj")
    o2 = client.get(res)
    row_vals = list(o2.table)
    assert row_vals[0]["a"] == 1
    assert row_vals[1]["a"] == 2
    assert row_vals[2]["a"] == 3


def test_pydantic(client):
    class A(pydantic.BaseModel):
        a: int

    class B(A):
        b: str

    val = B(a=5, b="x")
    ref = client.save_object(val, "my-pydantic-obj")
    val2 = client.get(ref)
    assert val == val2

    assert weave_isinstance(val, B)
    assert weave_isinstance(val, A)
    assert weave_isinstance(val, pydantic.BaseModel)
    assert not weave_isinstance(val, int)

    assert weave_isinstance(val2, B)
    assert weave_isinstance(val2, A)
    assert weave_isinstance(val2, pydantic.BaseModel)
    assert not weave_isinstance(val2, int)


def test_call_create(client):
    call = client.create_call("x", None, {"a": 5, "b": 10})
    client.finish_call(call, "hello")
    result = client.call(call.id)
    print("RESULT", result)
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
            path=[OBJECT_ATTR_EDGE_NAME, "rows"],
            operation="append",
            args=({"doc": "zz", "label": "e"},),
        ),
        weave_client.MutationSetitem(
            path=[
                OBJECT_ATTR_EDGE_NAME,
                "rows",
                TABLE_ROW_ID_EDGE_NAME,
                RegexStringMatcher(".*,.*"),
            ],
            operation="setitem",
            args=("doc", "jjj"),
        ),
        weave_client.MutationSetitem(
            path=[
                OBJECT_ATTR_EDGE_NAME,
                "rows",
                TABLE_ROW_ID_EDGE_NAME,
                RegexStringMatcher(".*,.*"),
                DICT_KEY_EDGE_NAME,
                "somelist",
                LIST_INDEX_EDGE_NAME,
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
    assert isinstance(weave_client.get_ref(add2), refs.OpRef)
    assert res == 4
    assert len(list(client.calls())) == 1


@pytest.mark.skip("failing in ci, due to some kind of /tmp file slowness?")
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
    assert model2.predict("x") == "input is: x"


def test_saved_nested_modellike(client):
    class A(weave.Object):
        x: int

        @weave.op()
        async def call(self, input):
            return self.x + input

    class B(weave.Object):
        a: A
        y: int

        @weave.op()
        async def call(self, input):
            return await self.a.call(input - self.y)

    model = B(a=A(x=3), y=2)
    ref = client.save_object(model, "my-model")
    model2 = client.get(ref)

    class C(weave.Object):
        b: B
        z: int

        @weave.op()
        async def call(self, input):
            return await self.b.call(input - 2 * self.z)

    @weave.op()
    async def call_model(c, input):
        return await c.call(input)

    c = C(b=model2, z=1)
    assert asyncio.run(call_model(c, 5)) == 4


def test_dataset_rows_ref(client):
    dataset = weave.Dataset(rows=[{"a": 1}, {"a": 2}, {"a": 3}])
    saved = client.save(dataset, "my-dataset")
    assert isinstance(saved.rows.ref, weave_client.ObjectRef)
    assert saved.rows.ref.name == "my-dataset"
    assert saved.rows.ref.extra == [OBJECT_ATTR_EDGE_NAME, "rows"]


# @pytest.mark.skip("failing in ci, due to some kind of /tmp file slowness?")
def test_evaluate(client):
    @weave.op()
    async def model_predict(input) -> str:
        return eval(input)

    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op()
    async def score(target, prediction):
        return target == prediction

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    expected_eval_result = {
        "prediction": {"mean": 9.5},
        "score": {"true_count": 1, "true_fraction": 0.5},
    }
    assert result == expected_eval_result

    evaluate_calls = list(weave.as_op(evaluation.evaluate).calls())
    assert len(evaluate_calls) == 1
    eval_call = evaluate_calls[0]
    eval_call_children = list(eval_call.children())
    assert len(eval_call_children) == 3

    # TODO: walk the whole graph and make sure all the refs and relationships
    # are there.
    child0 = eval_call_children[0]
    assert child0.op_name == weave_client.get_ref(Evaluation.predict_and_score).uri()

    eval_obj = child0.inputs["self"]
    eval_obj_val = eval_obj._val  # non-trace version so we don't automatically deref
    assert eval_obj_val._class_name == "Evaluation"
    assert eval_obj_val.name == "my-eval"
    assert eval_obj_val.description == None
    assert isinstance(eval_obj_val.dataset, weave_client.ObjectRef)
    assert eval_obj.dataset._class_name == "Dataset"
    assert len(eval_obj_val.scorers) == 1
    assert isinstance(eval_obj_val.scorers[0], weave_client.ObjectRef)
    assert isinstance(eval_obj.scorers[0], Op)
    # WARNING: test ordering issue. Because we attach the ref to ops directly,
    # the ref may be incorrect if we've blown away the database between tests.
    # Running a different evaluation test before this check will cause a failure
    # here.
    assert isinstance(eval_obj_val.predict_and_score, weave_client.ObjectRef)
    # Disabled because of test ordering issue, if test_evaluate.py runs first, this fails
    # assert isinstance(eval_obj.predict_and_score, op_def.OpDef)
    assert isinstance(eval_obj_val.summarize, weave_client.ObjectRef)
    # Disabled because of test ordering issue, if test_evaluate.py runs first, this fails
    # assert isinstance(eval_obj.summarize, op_def.OpDef)

    model_obj = child0.inputs["model"]
    assert isinstance(model_obj, Op)
    assert (
        weave_client.get_ref(model_obj).uri()
        == weave_client.get_ref(model_predict).uri()
    )

    example0_obj = child0.inputs["example"]
    assert example0_obj.ref.name == "Dataset"
    assert example0_obj.ref.extra == [
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
    ]
    example0_obj_input = example0_obj["input"]
    assert example0_obj_input == "1 + 2"
    assert example0_obj_input.ref.name == "Dataset"
    assert example0_obj_input.ref.extra == [
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
        DICT_KEY_EDGE_NAME,
        "input",
    ]
    example0_obj_target = example0_obj["target"]
    assert example0_obj_target == 3
    assert example0_obj_target.ref.name == "Dataset"
    assert example0_obj_target.ref.extra == [
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
        DICT_KEY_EDGE_NAME,
        "target",
    ]

    # second child is another predict_and_score call
    child1 = eval_call_children[1]
    assert child1.op_name == weave_client.get_ref(Evaluation.predict_and_score).uri()
    assert child0.inputs["self"]._val == child1.inputs["self"]._val

    # TODO: these are not directly equal, we end up loading the same thing
    # multiple times
    # (these are ops)
    assert child0.inputs["model"].name == child1.inputs["model"].name
    example1_obj = child1.inputs["example"]
    assert example1_obj.ref.name == "Dataset"
    assert example1_obj.ref.extra == [
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
    ]
    # Should be a different row ref
    assert example1_obj.ref.extra[3] != example0_obj.ref.extra[3]


def test_nested_ref_is_inner(client):
    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op()
    async def score(target, prediction):
        return target == prediction

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )

    saved = client.save(evaluation, "my-eval")
    assert saved.dataset.ref.name == "Dataset"
    assert saved.dataset.rows.ref.name == "Dataset"


def test_obj_dedupe(client):
    client.save_object({"a": 1}, "my-obj")
    client.save_object({"a": 1}, "my-obj")
    client.save_object({"a": 2}, "my-obj")
    res = client.objects()
    assert len(res) == 2
    assert res[0].version_index == 0
    assert res[1].version_index == 1


def test_op_query(client):
    @weave.op()
    def myop(x):
        return x

    client.save_object({"a": 1}, "my-obj")
    client.save_object(myop, "my-op")
    res = client.objects()
    assert len(res) == 1


def test_refs_read_batch_noextra(client):
    ref = client.save_object([1, 2, 3], "my-list")
    ref2 = client.save_object({"a": [3, 4, 5]}, "my-obj")
    res = client.server.refs_read_batch(RefsReadBatchReq(refs=[ref.uri(), ref2.uri()]))
    assert len(res.vals) == 2
    assert res.vals[0] == [1, 2, 3]
    assert res.vals[1] == {"a": [3, 4, 5]}


def test_refs_read_batch_with_extra(client):
    saved = client.save([{"a": 5}, {"a": 6}], "my-list")
    ref1 = saved[0]["a"].ref
    ref2 = saved[1].ref
    res = client.server.refs_read_batch(RefsReadBatchReq(refs=[ref1.uri(), ref2.uri()]))
    assert len(res.vals) == 2
    assert res.vals[0] == 5
    assert res.vals[1] == {"a": 6}


def test_refs_read_batch_dataset_rows(client):
    saved = client.save(weave.Dataset(rows=[{"a": 5}, {"a": 6}]), "my-dataset")
    ref1 = saved.rows[0]["a"].ref
    ref2 = saved.rows[1]["a"].ref
    res = client.server.refs_read_batch(RefsReadBatchReq(refs=[ref1.uri(), ref2.uri()]))
    assert len(res.vals) == 2
    assert res.vals[0] == 5
    assert res.vals[1] == 6


def test_large_files(client):
    class CoolCustomThing:
        a: str

        def __init__(self, a):
            self.a = a

    class CoolCustomThingType(weave.types.Type):
        instance_classes = CoolCustomThing

        def save_instance(self, obj, artifact, name):
            with artifact.new_file(name) as f:
                f.write(obj.a * 10000005)

        def load_instance(self, artifact, name, extra=None):
            with artifact.open(name) as f:
                return CoolCustomThing(f.read())

    ref = client.save_object(CoolCustomThing("x"), "my-obj")
    res = client.get(ref)
    assert len(res.a) == 10000005


def test_server_file(client):
    f_bytes = b"0" * 10000005
    res = client.server.file_create(
        FileCreateReq(project_id="shawn/test-project", name="my-file", content=f_bytes)
    )

    read_res = client.server.file_content_read(
        FileContentReadReq(project_id="shawn/test-project", digest=res.digest)
    )
    assert f_bytes == read_res.content


def test_isinstance_checks(client):
    class PydanticObjA(weave.Object):
        x: dict

    class PydanticObjB(weave.Object):
        a: PydanticObjA

    b = PydanticObjB(a=PydanticObjA(x={"y": [1, "j", True, None]}))

    client.save_nested_objects(b)

    assert isinstance(b, PydanticObjB)
    a = b.a
    assert b.ref is not None
    assert isinstance(a, PydanticObjA)
    assert a.ref is not None
    assert not a.ref.is_descended_from(b.ref)  # objects always saved as roots
    x = a.x
    assert isinstance(x, dict)
    assert x.ref is not None
    assert x.ref.is_descended_from(a.ref)
    y = x["y"]
    assert isinstance(y, list)
    assert y.ref is not None
    assert y.ref.is_descended_from(x.ref)
    y0 = y[0]
    assert isinstance(y0, int)
    assert y0.ref is not None
    assert y0.ref.is_descended_from(y.ref)
    y1 = y[1]
    assert isinstance(y1, str)
    assert y1.ref is not None
    assert y1.ref.is_descended_from(y.ref)

    # BoxedBool can't inherit from bool
    y2 = y[2]
    assert not isinstance(y2, bool)
    assert y2.ref is not None
    assert y2.ref.is_descended_from(y.ref)

    y3 = y[3]
    assert not isinstance(y2, type(None))
    assert y3.ref is not None
    assert y3.ref.is_descended_from(y.ref)
