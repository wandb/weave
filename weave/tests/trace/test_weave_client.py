import asyncio
import dataclasses
import json
import platform
import re
import sys

import pydantic
import pytest
import requests

import weave
import weave.trace_server.trace_server_interface as tsi
from weave import Evaluation, weave_client
from weave.legacy import op_def
from weave.trace import refs
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op
from weave.trace.refs import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
)
from weave.trace.serializer import get_serializer_for_obj, register_serializer
from weave.trace.tests.testutil import ObjectRefStrMatcher
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    RefsReadBatchReq,
    TableCreateReq,
    TableQueryReq,
    TableSchemaForInsert,
)

pytestmark = pytest.mark.trace


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
        TableQueryReq(project_id="test/test-project", digest=res.digest)
    )
    assert result.rows[0].val["val"] == 1
    assert result.rows[1].val["val"] == 2
    assert result.rows[2].val["val"] == 3


def test_table_update(client):
    data = [
        {"val": 1},
        {"val": 2},
        {"val": 3},
    ]
    table_create_res = client.server.table_create(
        TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client._project_id(),
                rows=data,
            )
        )
    )
    table_query_res = client.server.table_query(
        TableQueryReq(project_id=client._project_id(), digest=table_create_res.digest)
    )
    assert len(table_query_res.rows) == len(data)
    for i, row in enumerate(table_query_res.rows):
        assert row.val["val"] == data[i]["val"]

    table_create_res = client.server.table_update(
        tsi.TableUpdateReq.model_validate(
            dict(
                project_id=client._project_id(),
                base_digest=table_create_res.digest,
                updates=[
                    {"insert": {"index": 1, "row": {"val": 4}}},
                    {"pop": {"index": 0}},
                    {"append": {"row": {"val": 5}}},
                ],
            )
        )
    )
    final_data = [*data]
    final_data.insert(1, {"val": 4})
    final_data.pop(0)
    final_data.append({"val": 5})

    table_query_2_res = client.server.table_query(
        TableQueryReq(project_id=client._project_id(), digest=table_create_res.digest)
    )

    assert len(table_query_2_res.rows) == len(final_data)
    for i, row in enumerate(table_query_2_res.rows):
        assert row.val["val"] == final_data[i]["val"]

    # Verify digests are equal to if we added directly
    check_res = client.server.table_create(
        TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client._project_id(),
                rows=final_data,
            )
        )
    )
    assert check_res.digest == table_create_res.digest


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
        ref.ref.digest,
        (
            OBJECT_ATTR_EDGE_NAME,
            "rows",
            TABLE_ROW_ID_EDGE_NAME,
            RegexStringMatcher(".*"),
            DICT_KEY_EDGE_NAME,
            "v",
        ),
    )

    row1 = ref2[1]
    ref1_aref = row1["a_ref"]
    assert ref1_aref == 2
    assert weave_client.get_ref(ref0_aref) == weave_client.ObjectRef(
        "shawn",
        "test-project",
        "my-dataset",
        ref.ref.digest,
        (
            OBJECT_ATTR_EDGE_NAME,
            "rows",
            TABLE_ROW_ID_EDGE_NAME,
            RegexStringMatcher(".*"),
            DICT_KEY_EDGE_NAME,
            "v",
        ),
    )


def test_obj_with_table(client):
    class ObjWithTable(weave.Object):
        table: weave_client.Table

    o = ObjWithTable(table=weave_client.Table([{"a": 1}, {"a": 2}, {"a": 3}]))
    res = client._save_object(o, "my-obj")
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
    ref = client._save_object(val, "my-pydantic-obj")
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
    call = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call, "hello")
    result = client.call(call.id)
    expected = weave_client.Call(
        op_name="weave:///shawn/test-project/op/x:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 5, "b": 10},
        id=call.id,
        output="hello",
        exception=None,
        summary={},
        _children=[],
        attributes={
            "weave": {
                "client_version": weave.version.VERSION,
                "source": "python-sdk",
                "os_name": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "sys_version": sys.version,
            },
        },
    )
    assert dataclasses.asdict(result._val) == dataclasses.asdict(expected)


def test_calls_query(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call1 = client.create_call("x", {"a": 6, "b": 11})
    call2 = client.create_call("y", {"a": 5, "b": 10})
    result = list(client.calls(weave_client.CallsFilter(op_names=[call1.op_name])))
    assert len(result) == 2
    assert result[0] == weave_client.Call(
        op_name="weave:///shawn/test-project/op/x:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 5, "b": 10},
        id=call0.id,
        attributes={
            "weave": {
                "client_version": weave.version.VERSION,
                "source": "python-sdk",
                "os_name": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "sys_version": sys.version,
            },
        },
    )
    assert result[1] == weave_client.Call(
        op_name="weave:///shawn/test-project/op/x:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=call0.id,
        inputs={"a": 6, "b": 11},
        id=call1.id,
        attributes={
            "weave": {
                "client_version": weave.version.VERSION,
                "source": "python-sdk",
                "os_name": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "sys_version": sys.version,
            },
        },
    )
    client.finish_call(call2, None)
    client.finish_call(call1, None)
    client.finish_call(call0, None)


def test_calls_delete(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call0_child1 = client.create_call("x", {"a": 5, "b": 11}, call0)
    _call0_child2 = client.create_call("x", {"a": 5, "b": 12}, call0_child1)
    call1 = client.create_call("y", {"a": 6, "b": 11})

    assert len(list(client.calls())) == 4

    result = list(client.calls(weave_client.CallsFilter(op_names=[call0.op_name])))
    assert len(result) == 3

    # should deleted call0_child1, _call0_child2, call1, but not call0
    client.delete_call(call0_child1)

    result = list(client.calls(weave_client.CallsFilter(op_names=[call0.op_name])))
    assert len(result) == 1

    result = list(client.calls(weave_client.CallsFilter(op_names=[call1.op_name])))
    assert len(result) == 0

    # no-op if already deleted
    client.delete_call(call0_child1)
    call1.delete()
    call1.delete()

    result = list(client.calls())
    # only call0 should be left
    assert len(result) == 1


def test_calls_delete_cascade(client):
    # run an evaluation, then delete the evaluation and its children
    @weave.op()
    async def model_predict(input) -> str:
        return eval(input)

    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op()
    async def score(target, model_output):
        return target == model_output

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )
    asyncio.run(evaluation.evaluate(model_predict))

    evaluate_calls = list(weave.as_op(evaluation.evaluate).calls())
    assert len(evaluate_calls) == 1
    eval_call = evaluate_calls[0]
    eval_call_children = list(eval_call.children())
    assert len(eval_call_children) == 3

    # delete the evaluation, should cascade to all the calls and sub-calls
    client.delete_call(eval_call)

    # check that all the calls are gone
    result = list(client.calls())
    assert len(result) == 0


def test_call_display_name(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})

    # Rename using the client method
    client._set_call_display_name(call0, "updated_name")
    # same op_name
    result = list(client.calls())
    assert len(result) == 1

    # Rename using the call object's method
    call0 = result[0]
    call0.set_display_name("new_name")
    result = list(client.calls())
    assert len(result) == 1
    assert result[0].display_name == "new_name"

    # delete the display name
    call0 = result[0]
    client._remove_call_display_name(call0)
    call0 = client.call(call0.id)
    assert call0.display_name is None

    # add it back
    call0.set_display_name("new new name")
    call0 = client.call(call0.id)
    assert call0.display_name == "new new name"

    # delete display_name by setting to None
    call0.remove_display_name()
    call0 = client.call(call0.id)
    assert call0.display_name is None

    # add it back
    call0.set_display_name("new new name")
    call0 = client.call(call0.id)
    assert call0.display_name == "new new name"

    # delete by passing None to set
    call0.set_display_name(None)
    call0 = client.call(call0.id)
    assert call0.display_name is None


def test_dataset_calls(client):
    ref = client.save(
        weave.Dataset(rows=[{"doc": "xx", "label": "c"}, {"doc": "yy", "label": "d"}]),
        "my-dataset",
    )
    for row in ref.rows:
        call = client.create_call("x", {"a": row["doc"]})
        client.finish_call(call, None)

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
def test_saveload_op(client):
    @weave.op()
    def add2(x, y):
        return x + y

    @weave.op()
    def add3(x, y, z):
        return x + y + z

    obj = {"a": add2, "b": add3}
    ref = client._save_object(obj, "my-ops")
    obj2 = client.get(ref)
    assert isinstance(obj2["a"], op_def.OpDef)
    assert obj2["a"].name == "op-add2"
    assert isinstance(obj2["b"], op_def.OpDef)
    assert obj2["b"].name == "op-add3"


def test_object_mismatch_project_ref(client):
    client.project = "test-project"

    class MyModel(weave.Model):
        prompt: str

        @weave.op()
        def predict(self, input):
            return self.prompt.format(input=input)

    obj = MyModel(prompt="input is: {input}")

    client.project = "test-project2"
    obj.predict("x")

    calls = list(client.calls())
    assert len(calls) == 1
    assert calls[0].project_id == "shawn/test-project2"
    assert "weave:///shawn/test-project2/op" in str(calls[0].op_name)


def test_object_mismatch_project_ref_nested(client):
    client.project = "test-project"

    @weave.op()
    def hello_world():
        return "Hello world"

    hello_world()

    calls = list(client.calls())
    assert len(calls) == 1
    assert calls[0].project_id == "shawn/test-project"
    assert "weave:///shawn/test-project/op" in str(calls[0].op_name)

    ### Now change project in client, simulating new init
    client.project = "test-project2"
    nested = {"a": hello_world}

    client.save(nested, "my-object")

    nested["a"]()

    calls = list(client.calls())
    assert len(calls) == 1
    assert calls[0].project_id == "shawn/test-project2"
    assert "weave:///shawn/test-project2/op" in str(calls[0].op_name)

    # also assert the op and objects are correct in db
    res = client.server.objs_query(tsi.ObjQueryReq(project_id=client._project_id()))
    assert len(res.objs) == 2

    op = [x for x in res.objs if x.kind == "op"][0]
    assert op.object_id == "hello_world"
    assert op.project_id == "shawn/test-project2"
    assert op.kind == "op"

    obj = [x for x in res.objs if x.kind == "object"][0]
    assert obj.object_id == "my-object"
    assert obj.project_id == "shawn/test-project2"


def test_saveload_customtype(client, strict_op_saving):
    class MyCustomObj:
        a: int
        b: str

        def __init__(self, a, b):
            self.a = a
            self.b = b

    def custom_obj_save(obj, artifact, name) -> None:
        with artifact.new_file(f"{name}.json") as f:
            json.dump({"a": obj.a, "b": obj.b}, f)

    def custom_obj_load(artifact, name):
        with artifact.open(f"{name}.json") as f:
            json_obj = json.load(f)
            return MyCustomObj(json_obj["a"], json_obj["b"])

    register_serializer(MyCustomObj, custom_obj_save, custom_obj_load)

    obj = MyCustomObj(5, "x")
    ref = client._save_object(obj, "my-obj")

    # Hack the serializer so that it's loader no longer exists, to ensure
    # it can't be called.
    serializer = get_serializer_for_obj(obj)
    serializer.load = None

    obj2 = client.get(ref)
    assert obj2.__class__.__name__ == "MyCustomObj"
    assert obj2.a == 5
    assert obj2.b == "x"


def test_save_unknown_type(client):
    class SomeUnknownThing:
        def __init__(self, a):
            self.a = a

    obj = SomeUnknownThing(3)
    ref = client._save_object(obj, "my-np-array")
    obj2 = client.get(ref)
    # Expect None for now
    assert obj2 == repr(obj)


def test_save_model(client):
    class MyModel(weave.Model):
        prompt: str

        @weave.op()
        def predict(self, input):
            return self.prompt.format(input=input)

    model = MyModel(prompt="input is: {input}")
    ref = client._save_object(model, "my-model")
    model2 = client.get(ref)
    assert model2.predict("x") == "input is: x"


@pytest.mark.flaky(reruns=5, reruns_delay=2)
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
    ref = client._save_object(model, "my-model")
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
    assert saved.rows.ref.extra == (OBJECT_ATTR_EDGE_NAME, "rows")


@pytest.mark.skip("failing in ci, due to some kind of /tmp file slowness?")
def test_evaluate(client):
    @weave.op()
    async def model_predict(input) -> str:
        return eval(input)

    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op()
    async def score(target, model_output):
        return target == model_output

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    expected_eval_result = {
        "model_output": {"mean": 9.5},
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
    assert eval_obj_val.description is None
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
    assert example0_obj.ref.extra == (
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
    )
    example0_obj_input = example0_obj["input"]
    assert example0_obj_input == "1 + 2"
    assert example0_obj_input.ref.name == "Dataset"
    assert example0_obj_input.ref.extra == (
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
        DICT_KEY_EDGE_NAME,
        "input",
    )
    example0_obj_target = example0_obj["target"]
    assert example0_obj_target == 3
    assert example0_obj_target.ref.name == "Dataset"
    assert example0_obj_target.ref.extra == (
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
        DICT_KEY_EDGE_NAME,
        "target",
    )

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
    assert example1_obj.ref.extra == (
        OBJECT_ATTR_EDGE_NAME,
        "rows",
        TABLE_ROW_ID_EDGE_NAME,
        RegexStringMatcher(".*"),
    )
    # Should be a different row ref
    assert example1_obj.ref.extra[3] != example0_obj.ref.extra[3]


def test_nested_ref_is_inner(client):
    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op()
    async def score(target, model_output):
        return target == model_output

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )

    saved = client.save(evaluation, "my-eval")
    assert saved.dataset.ref.name == "Dataset"
    assert saved.dataset.rows.ref.name == "Dataset"


def test_obj_dedupe(client):
    client._save_object({"a": 1}, "my-obj")
    client._save_object({"a": 1}, "my-obj")
    client._save_object({"a": 2}, "my-obj")
    res = client._objects()
    assert len(res) == 2
    assert res[0].version_index == 0
    assert res[1].version_index == 1


def test_op_query(client):
    @weave.op()
    def myop(x):
        return x

    client._save_object({"a": 1}, "my-obj")
    client._save_object(myop, "my-op")
    res = client._objects()
    assert len(res) == 1


def test_refs_read_batch_noextra(client):
    ref = client._save_object([1, 2, 3], "my-list")
    ref2 = client._save_object({"a": [3, 4, 5]}, "my-obj")
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


def test_refs_read_batch_multi_project(client):
    client.project = "test111"
    ref = client._save_object([1, 2, 3], "my-list")

    client.project = "test222"
    ref2 = client._save_object({"a": [3, 4, 5]}, "my-obj")

    client.project = "test333"
    ref3 = client._save_object({"ab": [3, 4, 5]}, "my-obj-2")

    refs = [ref.uri(), ref2.uri(), ref3.uri()]
    res = client.server.refs_read_batch(RefsReadBatchReq(refs=refs))
    assert len(res.vals) == 3
    assert res.vals[0] == [1, 2, 3]
    assert res.vals[1] == {"a": [3, 4, 5]}
    assert res.vals[2] == {"ab": [3, 4, 5]}


def test_large_files(client):
    class CoolCustomThing:
        a: str

        def __init__(self, a):
            self.a = a

    def save_instance(obj, artifact, name):
        with artifact.new_file(name) as f:
            f.write(obj.a * 10000005)

    def load_instance(artifact, name, extra=None):
        with artifact.open(name) as f:
            return CoolCustomThing(f.read())

    register_serializer(CoolCustomThing, save_instance, load_instance)

    ref = client._save_object(CoolCustomThing("x"), "my-obj")
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

    client._save_nested_objects(b)

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

    y3 = y[3]
    assert y3 is None


def test_summary_tokens(client):
    @weave.op()
    def model_a(text):
        result = "a: " + text
        return {
            "result": result,
            "model": "model_a",
            "usage": {
                "prompt_tokens": len(text),
                "completion_tokens": len(result),
            },
        }

    @weave.op()
    def model_b(text):
        result = "bbbb: " + text
        return {
            "result": result,
            "model": "model_b",
            "usage": {
                "prompt_tokens": len(text),
                "completion_tokens": len(result),
            },
        }

    @weave.op()
    def models(text):
        return (
            model_a(text)["result"]
            + " "
            + model_a(text)["result"]
            + " "
            + model_b(text)["result"]
        )

    res = models("hello")
    assert res == "a: hello a: hello bbbb: hello"

    call = list(models.calls())[0]

    assert call.summary["usage"] == {
        "model_a": {"requests": 2, "prompt_tokens": 10, "completion_tokens": 16},
        "model_b": {"requests": 1, "prompt_tokens": 5, "completion_tokens": 11},
    }


@pytest.mark.skip("descendent error tracking disabled until we fix UI")
def test_summary_descendents(client):
    @weave.op()
    def model_a(text):
        return "a: " + text

    @weave.op()
    def model_b(text):
        return "bbbb: " + text

    @weave.op()
    def model_error(text):
        raise ValueError("error: " + text)

    @weave.op()
    def model_error_catch(text):
        try:
            model_error(text)
        except ValueError as e:
            return str(e)

    @weave.op()
    def models(text):
        return (
            model_a(text)
            + " "
            + model_a(text)
            + " "
            + model_b(text)
            + " "
            + model_error_catch(text)
        )

    res = models("hello")
    assert res == "a: hello a: hello bbbb: hello error: hello"

    call = list(models.calls())[0]

    assert list(call.summary["descendants"].items()) == [
        (ObjectRefStrMatcher(name="model_a"), {"successes": 2, "errors": 0}),
        (ObjectRefStrMatcher(name="model_b"), {"successes": 1, "errors": 0}),
        (ObjectRefStrMatcher(name="model_error"), {"successes": 0, "errors": 1}),
        (ObjectRefStrMatcher(name="model_error_catch"), {"successes": 1, "errors": 0}),
    ]


def test_weave_server(client):
    class MyModel(weave.Model):
        prompt: str

        @weave.op()
        def predict(self, input: str) -> str:
            return self.prompt.format(input=input)

    model = MyModel(prompt="input is: {input}")
    ref = client._save_object(model, "my-model")

    url = weave.serve(ref, thread=True)
    response = requests.post(url + "/predict", json={"input": "x"})
    assert response.json() == {"result": "input is: x"}


def row_gen(num_rows: int, approx_row_bytes: int = 1024):
    for i in range(num_rows):
        yield {"a": i, "b": "x" * approx_row_bytes}


def test_table_partitioning(network_proxy_client):
    """
    This test is specifically testing the correctness
    of the table partitioning logic in the remote client.
    In particular, the ability to partition large dataset
    creation into multiple updates
    """
    client, remote_client, records = network_proxy_client
    NUM_ROWS = 16
    rows = list(row_gen(NUM_ROWS, 1024))
    exp_digest = "15696550bde28f9231173a085ce107c823e7eab6744a97adaa7da55bc9c93347"

    remote_client.remote_request_bytes_limit = (
        100 * 1024
    )  # very large buffer to ensure a single request
    res = remote_client.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=rows,
            )
        )
    )
    assert res.digest == exp_digest
    assert len(records) == 1

    remote_client.remote_request_bytes_limit = (
        4 * 1024
    )  # Small enough to get multiple updates
    res = remote_client.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=rows,
            )
        )
    )
    assert res.digest == exp_digest
    assert len(records) == (
        1  # The first create call,
        + 1  # the second  create
        + NUM_ROWS / 2  # updates - 2 per batch
    )


def test_summary_tokens_cost(client):
    is_sqlite = isinstance(client.server._internal_trace_server, SqliteTraceServer)
    if is_sqlite:
        # SQLite does not support costs
        return

    @weave.op()
    def gpt4(text):
        result = "a: " + text
        return {
            "result": result,
            "model": "gpt-4",
            "usage": {
                "prompt_tokens": 1000000,
                "completion_tokens": 2000000,
            },
        }

    @weave.op()
    def gpt4o(text):
        result = "bbbb: " + text
        return {
            "result": result,
            "model": "gpt-4o",
            "usage": {
                "prompt_tokens": 3000000,
                "completion_tokens": 5000000,
            },
        }

    @weave.op()
    def models(text):
        return (
            gpt4(text)["result"]
            + " "
            + gpt4(text)["result"]
            + " "
            + gpt4o(text)["result"]
        )

    res = models("hello")
    assert res == "a: hello a: hello bbbb: hello"

    call = list(models.calls())[0]

    assert call.summary["usage"] == {
        "gpt-4": {
            "requests": 2,
            "prompt_tokens": 2000000,
            "completion_tokens": 4000000,
        },
        "gpt-4o": {
            "requests": 1,
            "prompt_tokens": 3000000,
            "completion_tokens": 5000000,
        },
    }

    callsWithCost = list(
        client.calls(
            weave_client.CallsFilter(op_names=[call.op_name]),
            include_costs=True,
        )
    )
    callsNoCost = list(
        client.calls(
            weave_client.CallsFilter(op_names=[call.op_name]),
            include_costs=False,
        )
    )

    assert len(callsWithCost) == len(callsNoCost)
    assert len(callsWithCost) == 1

    noCostCallSummary = callsNoCost[0].summary
    withCostCallSummary = callsWithCost[0].summary

    assert withCostCallSummary.get("weave", "bah") != "bah"
    assert len(withCostCallSummary["weave"]["costs"]) == 2

    gpt4cost = withCostCallSummary["weave"]["costs"]["gpt-4"]
    gpt4ocost = withCostCallSummary["weave"]["costs"]["gpt-4o"]

    # delete the effective_date and created_at fields, as they will be different each start up
    del gpt4cost["effective_date"]
    del gpt4ocost["effective_date"]
    del gpt4cost["created_at"]
    del gpt4ocost["created_at"]

    assert gpt4cost == (
        {
            "prompt_tokens": 2000000,
            "completion_tokens": 4000000,
            "requests": 2,
            "total_tokens": 0,
            "prompt_tokens_cost": pytest.approx(60),
            "completion_tokens_cost": pytest.approx(240),
            "prompt_token_cost": 3e-05,
            "completion_token_cost": 6e-05,
            "prompt_token_cost_unit": "USD",
            "completion_token_cost_unit": "USD",
            "provider_id": "openai",
            "pricing_level": "default",
            "pricing_level_id": "default",
            "created_by": "system",
        }
    )

    assert gpt4ocost == (
        {
            "prompt_tokens": 3000000,
            "completion_tokens": 5000000,
            "requests": 1,
            "total_tokens": 0,
            "prompt_tokens_cost": pytest.approx(15),
            "completion_tokens_cost": pytest.approx(75),
            "prompt_token_cost": 5e-06,
            "completion_token_cost": 1.5e-05,
            "prompt_token_cost_unit": "USD",
            "completion_token_cost_unit": "USD",
            "provider_id": "openai",
            "pricing_level": "default",
            "pricing_level_id": "default",
            "created_by": "system",
        }
    )

    # for no cost call, there should be no cost information
    # currently that means no weave object in the summary
    assert noCostCallSummary.get("weave", "bah") == "bah"


@pytest.mark.skip_clickhouse_client
def test_summary_tokens_cost_sqlite(client):
    is_sqlite = isinstance(client.server._internal_trace_server, SqliteTraceServer)
    if not is_sqlite:
        # only run this test for sqlite
        return

    # ensure that include_costs is a no-op for sqlite
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call0_child1 = client.create_call("x", {"a": 5, "b": 11}, call0)
    _call0_child2 = client.create_call("x", {"a": 5, "b": 12}, call0_child1)
    call1 = client.create_call("y", {"a": 6, "b": 11})

    callsWithCost = list(client.calls(include_costs=True))
    callsNoCost = list(client.calls(include_costs=False))

    assert len(callsWithCost) == len(callsNoCost)
    assert len(callsWithCost) == 4

    noCostCallSummary = callsNoCost[0].summary
    withCostCallSummary = callsWithCost[0].summary

    assert noCostCallSummary is None
    assert withCostCallSummary is None


def test_ref_in_dict(client):
    ref = client._save_object({"a": 5}, "d1")

    # Put a ref directly in a dict.
    ref2 = client._save_object({"b": ref}, "d2")

    obj = weave.ref(ref2.uri()).get()
    assert obj["b"] == {"a": 5}
