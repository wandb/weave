import asyncio
import dataclasses
import json
import platform
import sys
import time

import pydantic
import pytest
import requests

import weave
import weave.trace_server.trace_server_interface as tsi
from tests.trace.testutil import ObjectRefStrMatcher
from tests.trace.util import (
    AnyIntMatcher,
    DatetimeMatcher,
    RegexStringMatcher,
    client_is_sqlite,
)
from weave import Evaluation
from weave.trace import refs, weave_client
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import is_op
from weave.trace.refs import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
    DeletedRef,
)
from weave.trace.serialization.serializer import (
    get_serializer_for_obj,
    register_serializer,
)
from weave.trace_server.clickhouse_trace_server_batched import NotFoundError
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH
from weave.trace_server.sqlite_trace_server import (
    NotFoundError as sqliteNotFoundError,
)
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    RefsReadBatchReq,
    TableCreateReq,
    TableQueryReq,
    TableSchemaForInsert,
)


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
            {
                "project_id": client._project_id(),
                "base_digest": table_create_res.digest,
                "updates": [
                    {"insert": {"index": 1, "row": {"val": 4}}},
                    {"pop": {"index": 0}},
                    {"append": {"row": {"val": 5}}},
                ],
            }
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
    assert [r.val for r in server.table_query(new_table_ref)] == [1, 2, 3, 4]


@pytest.mark.skip()
def test_table_remove(server):
    table_ref0 = server.new_table([1])
    table_ref1, item_id2 = server.table_append(table_ref0, 2)
    table_ref2, item_id3 = server.table_append(table_ref1, 3)
    table_ref3 = server.table_remove(table_ref2, item_id2)
    assert [r.val for r in server.table_query(table_ref3)] == [1, 3]


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
    assert [r.val for r in table_val] == [1, 2, 3]


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
    result = client.get_call(call.id)
    expected = weave_client.Call(
        _op_name="weave:///shawn/test-project/op/x:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 5, "b": 10},
        id=call.id,
        output="hello",
        exception=None,
        summary={
            "weave": {
                "status": "success",
                "trace_name": "x",
                "latency_ms": AnyIntMatcher(),
            }
        },
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
        started_at=DatetimeMatcher(),
        ended_at=DatetimeMatcher(),
        deleted_at=None,
    )
    assert dataclasses.asdict(result._val) == dataclasses.asdict(expected)


def test_calls_query(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call1 = client.create_call("x", {"a": 6, "b": 11})
    call2 = client.create_call("y", {"a": 5, "b": 10})
    result = list(client.get_calls(filter=tsi.CallsFilter(op_names=[call1.op_name])))
    assert len(result) == 2
    assert result[0] == weave_client.Call(
        _op_name="weave:///shawn/test-project/op/x:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw",
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
        summary={
            "weave": {
                "status": "running",
                "trace_name": "x",
            }
        },
        started_at=DatetimeMatcher(),
        ended_at=None,
    )
    assert result[1] == weave_client.Call(
        _op_name="weave:///shawn/test-project/op/x:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw",
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
        summary={
            "weave": {
                "status": "running",
                "trace_name": "x",
            }
        },
        started_at=DatetimeMatcher(),
        ended_at=None,
    )
    client.finish_call(call2, None)
    client.finish_call(call1, None)
    client.finish_call(call0, None)


def test_get_calls_complete(client):
    obj = weave.Dataset(rows=[{"a": 1}, {"a": 2}, {"a": 3}])
    ref = client.save(obj, "my-dataset")

    call0 = client.create_call(
        "x", {"a": 5, "b": 10, "dataset": ref, "s": "str"}, display_name="call0"
    )
    call1 = client.create_call(
        "x", {"a": 6, "b": 11, "dataset": ref, "s": "str"}, display_name="call1"
    )
    call2 = client.create_call(
        "y", {"a": 5, "b": 10, "dataset": ref, "s": "str"}, display_name="call2"
    )

    query = tsi.Query(
        **{
            "$expr": {
                "$contains": {
                    "input": {"$getField": "inputs.s"},
                    "substr": {"$literal": "str"},
                }
            }
        }
    )

    # use all the parameters to get_calls
    client_result = list(
        client.get_calls(
            filter=tsi.CallsFilter(op_names=[call1.op_name]),
            limit=1,
            offset=0,
            query=query,
            sort_by=[tsi.SortBy(field="started_at", direction="desc")],
            include_feedback=True,
            columns=["inputs.dataset.rows"],
        )
    )
    assert len(client_result) == 1
    assert client_result[0].inputs["b"] == 11
    assert client_result[0].inputs["dataset"].rows == [{"a": 1}, {"a": 2}, {"a": 3}]

    # what should be an identical query using the trace_server interface
    server_result = list(
        client.server.calls_query(
            tsi.CallsQueryReq(
                project_id="shawn/test-project",
                filter=tsi.CallsFilter(op_names=[call1.op_name]),
                limit=1,
                offset=0,
                query=query,
                sort_by=[tsi.SortBy(field="started_at", direction="desc")],
                include_feedback=True,
                columns=["inputs.dataset"],
                expand_columns=["inputs.dataset"],
            )
        ).calls
    )
    for call1, call2 in zip(client_result, server_result):
        assert call1.id == call2.id
        assert call1.op_name == call2.op_name
        assert call1.project_id == call2.project_id
        assert call1.trace_id == call2.trace_id
        assert call1.parent_id == call2.parent_id
        assert call1.started_at == call2.started_at
        assert call1.display_name == call2.display_name
        assert call1.summary == call2.summary
        assert call1.inputs["a"] == call2.inputs["a"]
        assert call1.inputs["b"] == call2.inputs["b"]
        assert call1.inputs["s"] == call2.inputs["s"]

    # add a simple query
    client_result = list(
        client.get_calls(
            sort_by=[tsi.SortBy(field="started_at", direction="desc")],
            query=query,
            include_costs=True,
            include_feedback=True,
        )
    )
    server_result = list(
        client.server.calls_query(
            tsi.CallsQueryReq(
                project_id="shawn/test-project",
                sort_by=[tsi.SortBy(field="started_at", direction="desc")],
                query=query,
                include_costs=True,
                include_feedback=True,
                columns=["inputs.dataset", "display_name", "parent_id"],
                expand_columns=["inputs.dataset"],
            )
        ).calls
    )
    for call1, call2 in zip(client_result, server_result):
        assert call1.id == call2.id
        assert call1.op_name == call2.op_name
        assert call1.project_id == call2.project_id
        assert call1.trace_id == call2.trace_id
        assert call1.started_at == call2.started_at
        assert call1.display_name == call2.display_name
        assert call1.parent_id == call2.parent_id
        assert call1.summary == call2.summary
        assert call1.inputs["a"] == call2.inputs["a"]
        assert call1.inputs["b"] == call2.inputs["b"]
        assert call1.inputs["s"] == call2.inputs["s"]


def test_get_calls_len(client):
    for i in range(10):
        client.create_call("x", {"a": i})

    # test len first
    calls = client.get_calls()
    assert len(calls) == 10

    calls = client.get_calls(limit=5)
    assert len(calls) == 5

    calls = client.get_calls(limit=5, offset=5)
    assert len(calls) == 5

    calls = client.get_calls(offset=10)
    assert len(calls) == 0

    calls = client.get_calls(offset=10, limit=10)
    assert len(calls) == 0

    with pytest.raises(ValueError):
        client.get_calls(limit=-1)

    with pytest.raises(ValueError):
        client.get_calls(limit=0)

    with pytest.raises(ValueError):
        client.get_calls(offset=-1)


def test_get_calls_limit_offset(client):
    for i in range(10):
        client.create_call("x", {"a": i})

    calls = client.get_calls(limit=3)
    assert len(calls) == 3
    for i, call in enumerate(calls):
        assert call.inputs["a"] == i

    calls = client.get_calls(limit=5, offset=5)
    assert len(calls) == 5

    for i, call in enumerate(calls):
        assert call.inputs["a"] == i + 5

    calls = client.get_calls(offset=9)
    assert len(calls) == 1
    assert calls[0].inputs["a"] == 9

    # now test indexing
    calls = client.get_calls()
    assert calls[0].inputs["a"] == 0
    assert calls[1].inputs["a"] == 1
    assert calls[2].inputs["a"] == 2
    assert calls[3].inputs["a"] == 3
    assert calls[4].inputs["a"] == 4

    calls = client.get_calls(offset=5)
    assert calls[0].inputs["a"] == 5
    assert calls[1].inputs["a"] == 6
    assert calls[2].inputs["a"] == 7
    assert calls[3].inputs["a"] == 8
    assert calls[4].inputs["a"] == 9

    # slicing
    calls = client.get_calls(offset=5)
    for i, call in enumerate(calls[2:]):
        assert call.inputs["a"] == 7 + i


def test_calls_delete(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call0_child1 = client.create_call("x", {"a": 5, "b": 11}, call0)
    _call0_child2 = client.create_call("x", {"a": 5, "b": 12}, call0_child1)
    call1 = client.create_call("y", {"a": 6, "b": 11})

    assert len(list(client.get_calls())) == 4

    result = list(client.get_calls(filter=tsi.CallsFilter(op_names=[call0.op_name])))
    assert len(result) == 3

    # should deleted call0_child1, _call0_child2, call1, but not call0
    client.delete_call(call0_child1)

    result = list(client.get_calls(filter=tsi.CallsFilter(op_names=[call0.op_name])))
    assert len(result) == 1

    result = list(client.get_calls(filter=tsi.CallsFilter(op_names=[call1.op_name])))
    assert len(result) == 0

    # no-op if already deleted
    client.delete_call(call0_child1)
    call1.delete()
    call1.delete()

    result = list(client.get_calls())
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
    result = list(client.get_calls())
    assert len(result) == 0


def test_call_display_name(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})

    # Rename using the client method
    client._set_call_display_name(call0, "updated_name")
    # same op_name
    result = list(client.get_calls())
    assert len(result) == 1

    # Rename using the call object's method
    call0 = result[0]
    call0.set_display_name("new_name")
    result = list(client.get_calls())
    assert len(result) == 1
    assert result[0].display_name == "new_name"

    # delete the display name
    call0 = result[0]
    client._remove_call_display_name(call0)
    call0 = client.get_call(call0.id)
    assert call0.display_name is None

    # add it back
    call0.set_display_name("new new name")
    call0 = client.get_call(call0.id)
    assert call0.display_name == "new new name"

    # delete display_name by setting to None
    call0.remove_display_name()
    call0 = client.get_call(call0.id)
    assert call0.display_name is None

    # add it back
    call0.set_display_name("new new name")
    call0 = client.get_call(call0.id)
    assert call0.display_name == "new new name"

    # delete by passing None to set
    call0.set_display_name(None)
    call0 = client.get_call(call0.id)
    assert call0.display_name is None


def test_dataset_calls(client):
    ref = client.save(
        weave.Dataset(rows=[{"doc": "xx", "label": "c"}, {"doc": "yy", "label": "d"}]),
        "my-dataset",
    )
    for row in ref.rows:
        call = client.create_call("x", {"a": row["doc"]})
        client.finish_call(call, None)

    calls = list(client.get_calls(filter={"op_name": "x"}))
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
    x = client.get_calls(filter={"ref": weave_client.get_ref(dataset.rows[0]["doc"])})

    assert len(list(x)) == 2


def test_opdef(client):
    @weave.op()
    def add2(x, y):
        return x + y

    res = add2(1, 3)
    assert isinstance(weave_client.get_ref(add2), refs.OpRef)
    assert res == 4
    assert len(list(client.get_calls())) == 1


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

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].project_id == "shawn/test-project2"
    assert "weave:///shawn/test-project2/op" in str(calls[0].op_name)


def test_object_mismatch_project_ref_nested(client):
    client.project = "test-project"

    @weave.op()
    def hello_world():
        return "Hello world"

    hello_world()

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].project_id == "shawn/test-project"
    assert "weave:///shawn/test-project/op" in str(calls[0].op_name)

    ### Now change project in client, simulating new init
    client.project = "test-project2"
    nested = {"a": hello_world}

    client.save(nested, "my-object")

    nested["a"]()

    calls = list(client.get_calls())
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


def test_saveload_customtype(client):
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


@pytest.mark.skip(reason="TODO: Skip flake")
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
    async def score(target, output):
        return target == output

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    expected_eval_result = {
        "output": {"mean": 9.5},
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
    assert is_op(eval_obj.scorers[0])
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
    assert is_op(model_obj)
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
    async def score(target, output):
        return target == output

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


@pytest.mark.skip("skipping since it depends on query service deps atm")
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
    row_digests = [
        "2df5YAp2sqlYyxEpTKsIrUlf9Kc5ZxEkbqtqUnYOLhk",
        "DMjRIeuM76SCqXqsqehYyfL3KYV5fL0DBr6g4RJ4izA",
        "f949WksZQdTgf5Ac3cXS5cMuGf0otLvpULOfOsAGiYs",
        "YaFBweA0HU7w51Sdt8X4uhSmjk7N4WqSfuknmBRpWcc",
        "BBzLkGZ6fFraXdoFOSjj7p2d1qSiyMXjRnk7Zas2FEA",
        "i6i1XJ7QecqWkB8MdljoWu35tpjwk8npzFAd67aisB4",
        "IsjSZ4usQrHUcu0cNtKedBlUWrIW1f4cSDck1lGCSMw",
        "MkL0DTiDMCW3agkcIeZ5g5VP0MyFuQcVpa1yqGGVZwk",
        "Vu6S8c4XdXgWNYaAXKqsxuicY6XbYDKLIUkd2M0YPF8",
        "IkIjQFARp0Qny3AUav18zZuzY4INFXsREPkS3iFCrWo",
        "E3T6ngUGSpXY9u2l58sb9smleJ7GO2YlYJY0tq2oV5U",
        "uNmcjBhJyiC6qvJZ0JRlGLpRm68ARrXVYlBgjGRqRdA",
        "0bzwVP0JFd7Y2W9YmpPUv62aAkyY2RCaFVxMnEfjIqY",
        "3bZG40U188x6bVfm9aQX2xvYVqlCftD82O4UsDZtRVU",
        "KW40nfHplo7BDJux0kP8PeYQ95lnOEGaeYfgNtsQ1oE",
        "u10rDrPoYXl58eQStkQP4dPH6KfmE7I88f0FYI7L9fg",
    ]
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
    assert res.row_digests == row_digests
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
    assert res.row_digests == row_digests
    assert len(records) == (
        1  # The first create call,
        + 1  # the second  create
        + NUM_ROWS / 2  # updates - 2 per batch
    )


def test_summary_tokens_cost(client):
    if client_is_sqlite(client):
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
        client.get_calls(
            filter=tsi.CallsFilter(op_names=[call.op_name]),
            include_costs=True,
        )
    )
    callsNoCost = list(
        client.get_calls(
            filter=tsi.CallsFilter(op_names=[call.op_name]),
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
            "prompt_tokens_total_cost": pytest.approx(60),
            "completion_tokens_total_cost": pytest.approx(240),
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
            "prompt_tokens_total_cost": pytest.approx(15),
            "completion_tokens_total_cost": pytest.approx(75),
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
    assert noCostCallSummary["weave"] == {
        "status": "success",
        "trace_name": "models",
        "latency_ms": AnyIntMatcher(),
    }


@pytest.mark.skip_clickhouse_client
def test_summary_tokens_cost_sqlite(client):
    if not client_is_sqlite(client):
        # only run this test for sqlite
        return

    # ensure that include_costs is a no-op for sqlite
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call0_child1 = client.create_call("x", {"a": 5, "b": 11}, call0)
    _call0_child2 = client.create_call("x", {"a": 5, "b": 12}, call0_child1)
    call1 = client.create_call("y", {"a": 6, "b": 11})

    callsWithCost = list(client.get_calls(include_costs=True))
    callsNoCost = list(client.get_calls(include_costs=False))

    assert len(callsWithCost) == len(callsNoCost)
    assert len(callsWithCost) == 4

    noCostCallSummary = callsNoCost[0].summary
    withCostCallSummary = callsWithCost[0].summary

    weave_summary = {
        "weave": {
            "status": "running",
            "trace_name": "x",
        }
    }

    assert noCostCallSummary == weave_summary
    assert withCostCallSummary == weave_summary


def test_ref_in_dict(client):
    ref = client._save_object({"a": 5}, "d1")

    # Put a ref directly in a dict.
    ref2 = client._save_object({"b": ref}, "d2")

    obj = weave.ref(ref2.uri()).get()
    assert obj["b"] == {"a": 5}


def test_calls_stream_table_ref_expansion(client):
    class ObjWithTable(weave.Object):
        table: weave_client.Table

    o = ObjWithTable(table=weave_client.Table([{"a": 1}, {"a": 2}, {"a": 3}]))
    client._save_object(o, "my-obj")

    @weave.op
    def f(a):
        return {"a": a, "table": o.table}

    f(1)

    calls = client.server.calls_query_stream(
        req=tsi.CallsQueryReq(
            project_id=client._project_id(),
            expand_columns=["output.table"],
        )
    )
    calls = list(calls)
    assert len(calls) == 1
    assert calls[0].output["table"] == o.table.table_ref.uri()


def test_object_version_read(client):
    refs = []
    for i in range(10):
        refs.append(weave.publish({"a": i}))

    # read all objects, check the version
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            object_id=refs[0].name,
        )
    ).objs
    assert len(objs) == 10
    assert objs[0].version_index == 0
    assert objs[1].version_index == 1
    assert objs[2].version_index == 2
    assert objs[3].version_index == 3
    assert objs[4].version_index == 4
    assert objs[5].version_index == 5
    assert objs[6].version_index == 6
    assert objs[7].version_index == 7
    assert objs[8].version_index == 8
    assert objs[9].version_index == 9

    # read each object one at a time, check the version
    for i in range(10):
        obj_res = client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id=refs[i].name,
                digest=refs[i].digest,
            )
        )
        assert obj_res.obj.val == {"a": i}
        assert obj_res.obj.version_index == i

    # read each object one at a time, check the version, metadata only
    for i in range(10):
        obj_res = client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id=refs[i].name,
                digest=refs[i].digest,
                metadata_only=True,
            )
        )
        assert obj_res.obj.val == {}
        assert obj_res.obj.version_index == i

    # now grab the latest version of the object
    obj_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=refs[0].name,
            digest="latest",
        )
    )
    assert obj_res.obj.val == {"a": 9}
    assert obj_res.obj.version_index == 9

    # now grab each by their digests
    for i, digest in enumerate([obj.digest for obj in objs]):
        obj_res = client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id=refs[0].name,
                digest=digest,
            )
        )
        assert obj_res.obj.val == {"a": i}
        assert obj_res.obj.version_index == i

    # publish another, check that latest is updated
    client._save_object({"a": 10}, refs[0].name)
    obj_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=refs[0].name,
            digest="latest",
        )
    )
    assert obj_res.obj.val == {"a": 10}
    assert obj_res.obj.version_index == 10

    # check that v5 is still correct
    obj_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id=refs[0].name,
            digest="v5",
        )
    )
    assert obj_res.obj.val == {"a": 5}
    assert obj_res.obj.version_index == 5

    # check badly formatted digests
    digests = ["v1111", "1", ""]
    for digest in digests:
        with pytest.raises((NotFoundError, sqliteNotFoundError)):
            # grab non-existant version
            obj_res = client.server.obj_read(
                tsi.ObjReadReq(
                    project_id=client._project_id(),
                    object_id=refs[0].name,
                    digest=digest,
                )
            )

    # check non-existant object_id
    with pytest.raises((NotFoundError, sqliteNotFoundError)):
        obj_res = client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id="refs[0].name",
                digest="v1",
            )
        )


@pytest.mark.asyncio
async def test_op_calltime_display_name(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a

    result = my_op(1, __weave={"display_name": "custom_display_name"})
    calls = list(my_op.calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.display_name == "custom_display_name"

    evaluation = weave.Evaluation(dataset=[{"a": 1}], scorers=[])
    res = await evaluation.evaluate(
        my_op, __weave={"display_name": "custom_display_name"}
    )
    calls = list(evaluation.evaluate.calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.display_name == "custom_display_name"


def test_long_display_names_are_elided(client):
    @weave.op(call_display_name="a" * 2048)
    def func():
        pass

    # The display name is correct client side
    _, call = func.call()
    assert len(call.display_name) <= MAX_DISPLAY_NAME_LENGTH

    # The display name is correct server side
    calls = list(func.calls())
    call = calls[0]
    assert len(call.display_name) <= MAX_DISPLAY_NAME_LENGTH

    # Calling set_display_name is correct
    call.set_display_name("b" * 2048)
    assert len(call.display_name) <= MAX_DISPLAY_NAME_LENGTH

    calls = list(func.calls())
    call = calls[0]
    assert len(call.display_name) <= MAX_DISPLAY_NAME_LENGTH


def test_object_deletion(client):
    # Simple case, delete a single version of an object
    obj = {"a": 5}
    weave_obj = weave.publish(obj, "my-obj")
    assert client.get(weave_obj) == obj

    client.delete_object_version(weave_obj)
    with pytest.raises(weave.trace_server.errors.ObjectDeletedError):
        client.get(weave_obj)

    # create 3 versions of the object
    obj["a"] = 6
    weave_ref2 = weave.publish(obj, "my-obj")
    obj["a"] = 7
    weave_ref3 = weave.publish(obj, "my-obj")
    obj["a"] = 8
    weave_ref4 = weave.publish(obj, "my-obj")

    # delete weave_obj3 with class method
    weave_ref3.delete()

    # make sure we can't get the deleted object
    with pytest.raises(weave.trace_server.errors.ObjectDeletedError):
        client.get(weave_ref3)

    # make sure we can still get the existing object versions
    assert client.get(weave_ref4)
    assert client.get(weave_ref2)

    # count the number of versions of the object
    versions = client.server.objs_query(
        req=tsi.ObjQueryReq(
            project_id=client._project_id(),
            names=["my-obj"],
            sort_by=[tsi.SortBy(field="created_at", direction="desc")],
        )
    )
    assert len(versions.objs) == 2

    # iterate over the versions, confirm the indexes are correct
    assert versions.objs[0].version_index == 3
    assert versions.objs[1].version_index == 1

    weave_ref4.delete()
    weave_ref2.delete()

    versions = client.server.objs_query(
        req=tsi.ObjQueryReq(
            project_id=client._project_id(),
            names=["my-obj"],
        )
    )
    assert len(versions.objs) == 0


def test_recursive_object_deletion(client):
    # Create a bunch of objects that refer to each other
    obj1 = {"a": 5}
    obj1_ref = weave.publish(obj1, "obj1")

    obj2 = {"b": obj1_ref}
    obj2_ref = weave.publish(obj2, "obj2")

    obj3 = {"c": obj2_ref}
    obj3_ref = weave.publish(obj3, "obj3")

    # Delete obj1
    obj1_ref.delete()

    # Make sure we can't get obj1
    with pytest.raises(weave.trace_server.errors.ObjectDeletedError):
        obj1_ref.get()

    # Make sure we can get obj2, but the ref to object 1 should return None
    obj_2 = obj2_ref.get()

    assert isinstance(obj_2["b"], DeletedRef)
    assert obj_2["b"].deleted_at == DatetimeMatcher()
    assert obj_2["b"].ref == obj1_ref
    assert isinstance(obj_2["b"].error, weave.trace_server.errors.ObjectDeletedError)

    # Object2 should store the ref to object2, as instantiated
    assert obj3_ref.get() == {"c": obj2}


def test_delete_op_version(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a

    my_op(1)

    op_ref = weave.publish(my_op, "my-op")
    op_ref.delete()

    with pytest.raises(weave.trace_server.errors.ObjectDeletedError):
        op_ref.get()

    # lets get the calls
    calls = list(my_op.calls())
    assert len(calls) == 1

    # call the deleted op, this should still work (?)
    my_op(1)

    calls = list(my_op.calls())
    assert len(calls) == 2

    # but the ref is still deleted
    with pytest.raises(weave.trace_server.errors.ObjectDeletedError):
        op_ref.get()


def test_global_attributes(client_creator):
    @weave.op()
    def my_op(a: int) -> int:
        return a

    with client_creator(global_attributes={"env": "test", "version": "1.0"}) as client:
        my_op(1)

        calls = list(client.get_calls())
        assert len(calls) == 1
        call = calls[0]

        # Check global attributes are present
        assert call.attributes["env"] == "test"
        assert call.attributes["version"] == "1.0"


def test_global_attributes_with_call_attributes(client_creator):
    @weave.op()
    def my_op(a: int) -> int:
        return a

    with client_creator(
        global_attributes={"global_attr": "global", "env": "test"}
    ) as client:
        with weave.attributes({"local_attr": "local", "env": "override"}):
            my_op(1)

        calls = list(client.get_calls())
        assert len(calls) == 1
        call = calls[0]

        # Both global and local attributes are present
        assert call.attributes["global_attr"] == "global"
        assert call.attributes["local_attr"] == "local"

        # Local attributes override global ones
        assert call.attributes["env"] == "override"


def test_flush_progress_bar(client):
    client.set_autoflush(False)

    @weave.op
    def op_1():
        time.sleep(1)

    op_1()

    # flush with progress bar
    client.finish(use_progress_bar=True)

    # make sure there are no pending jobs
    assert client._get_pending_jobs()["total_jobs"] == 0
    assert client._has_pending_jobs() == False


def test_flush_callback(client):
    client.set_autoflush(False)

    @weave.op
    def op_1():
        time.sleep(1)

    op_1()

    def fake_logger(status):
        assert "job_counts" in status

    # flush with callback
    client.finish(callback=fake_logger)

    # make sure there are no pending jobs
    assert client._get_pending_jobs()["total_jobs"] == 0
    assert client._has_pending_jobs() == False
