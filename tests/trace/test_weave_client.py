import asyncio
import dataclasses
import datetime
import json
import platform
import re
import sys
import time
import uuid

import httpx
import pydantic
import pytest
from pydantic import ValidationError

import weave
import weave.trace.call
import weave.trace_server.trace_server_interface as tsi
from tests.conftest import TestOnlyFlushingWeaveClient
from tests.trace.testutil import ObjectRefStrMatcher
from tests.trace.util import (
    AnyIntMatcher,
    DatetimeMatcher,
    RegexStringMatcher,
    client_is_sqlite,
)
from weave import Evaluation
from weave.integrations.integration_utilities import op_name_from_call
from weave.prompt.prompt import MessagesPrompt
from weave.trace import refs, settings, table_upload_chunking, weave_client
from weave.trace.context import call_context
from weave.trace.context.call_context import tracing_disabled
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import is_op
from weave.trace.refs import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
    DeletedRef,
    TableRef,
)
from weave.trace.serialization.serializer import (
    get_serializer_for_obj,
    register_serializer,
)
from weave.trace.wandb_run_context import WandbRunContext
from weave.trace_server.clickhouse_trace_server_batched import NotFoundError
from weave.trace_server.common_interface import SortBy
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH
from weave.trace_server.ids import generate_id
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
    LLMStructuredCompletionModelDefaultParams,
)
from weave.trace_server.sqlite_trace_server import (
    NotFoundError as sqliteNotFoundError,
)
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    FilesStatsReq,
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


@pytest.mark.skip
def test_table_append(server):
    table_ref = server.new_table([1, 2, 3])
    new_table_ref, item_id = server.table_append(table_ref, 4)
    assert [r.val for r in server.table_query(new_table_ref)] == [1, 2, 3, 4]


@pytest.mark.skip
def test_table_remove(server):
    table_ref0 = server.new_table([1])
    table_ref1, item_id2 = server.table_append(table_ref0, 2)
    table_ref2, item_id3 = server.table_append(table_ref1, 3)
    table_ref3 = server.table_remove(table_ref2, item_id2)
    assert [r.val for r in server.table_query(table_ref3)] == [1, 3]


@pytest.mark.skip
def new_val_single(server):
    obj_id = server.new_val(42)
    assert server.get(obj_id) == 42


@pytest.mark.skip
def test_new_val_with_list(server):
    ref = server.new_val({"a": [1, 2, 3]})
    server_val = server.get_val(ref)
    table_ref = server_val["a"]
    assert isinstance(table_ref, TableRef)
    table_val = server.table_query(table_ref)
    assert [r.val for r in table_val] == [1, 2, 3]


@pytest.mark.skip
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


def test_filter_sort_by_query_validation(client):
    # Test invalid types
    with pytest.raises(TypeError):
        client.get_calls(filter="not a filter")
    with pytest.raises(TypeError):
        client.get_calls(filter=1)
    with pytest.raises(TypeError):
        client.get_calls(filter=["not a filter"])

    # Test invalid field names - these should fail with pydantic validation error
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        client.get_calls(filter={"op_name": ["should be op_names"]})
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        client.get_calls(filter={"call_id": ["should be call_ids"]})
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        client.get_calls(filter={"invalid_field": "invalid_value"})

    # Test that valid fields work
    client.get_calls(filter={"op_names": ["some_op"]})
    client.get_calls(filter={"call_ids": ["some_call_id"]})
    client.get_calls(filter={"trace_ids": ["some_trace_id"]})

    # now order_by
    with pytest.raises(ValidationError):
        client.get_calls(sort_by="not a sort_by")
    with pytest.raises(ValidationError):
        client.get_calls(sort_by=1)
    with pytest.raises(TypeError):
        client.get_calls(sort_by=["not a sort_by"])

    # test valid
    client.get_calls(sort_by=[SortBy(field="started_at", direction="desc")])

    # now query like filter
    with pytest.raises(TypeError):
        client.get_calls(query="not a query")
    with pytest.raises(TypeError):
        client.get_calls(query=1)
    with pytest.raises(TypeError):
        client.get_calls(query=["not a query"])

    with pytest.raises(
        ValidationError,
        match=r"\d+ validation errors for WeaveClient.get_calls",
    ):
        client.get_calls(query={"$expr": {"$invalid_field": "invalid_value"}})

    # test valid
    client.get_calls(
        query={"$expr": {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}}
    )


def test_call_create(client):
    call = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call, "hello")
    result = client.get_call(call.id)
    expected = weave.trace.call.Call(
        _op_name="weave:///shawn/test-project/op/x:6jAV4T6F42RKlabeB2RO0BXkbFFPrKyU2yyQedpotB8",
        project_id="shawn/test-project",
        trace_id=RegexStringMatcher(".*"),
        parent_id=None,
        inputs={"a": 5, "b": 10},
        id=call.id,
        output="hello",
        exception=None,
        summary={
            "status_counts": {
                "success": 1,
                "error": 0,
            },
            "weave": {
                "status": "success",
                "trace_name": "x",
                "latency_ms": AnyIntMatcher(),
            },
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
    assert result[0] == weave.trace.call.Call(
        _op_name="weave:///shawn/test-project/op/x:6jAV4T6F42RKlabeB2RO0BXkbFFPrKyU2yyQedpotB8",
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
            },
        },
        started_at=DatetimeMatcher(),
        ended_at=None,
    )
    assert result[1] == weave.trace.call.Call(
        _op_name="weave:///shawn/test-project/op/x:6jAV4T6F42RKlabeB2RO0BXkbFFPrKyU2yyQedpotB8",
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
            },
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
            sort_by=[SortBy(field="started_at", direction="desc")],
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
                sort_by=[SortBy(field="started_at", direction="desc")],
                include_feedback=True,
                columns=["inputs.dataset"],
                expand_columns=["inputs.dataset"],
            )
        ).calls
    )
    for call1, call2 in zip(client_result, server_result, strict=False):
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
            sort_by=[SortBy(field="started_at", direction="desc")],
            query=query,
            include_costs=True,
            include_feedback=True,
        )
    )
    server_result = list(
        client.server.calls_query(
            tsi.CallsQueryReq(
                project_id="shawn/test-project",
                sort_by=[SortBy(field="started_at", direction="desc")],
                query=query,
                include_costs=True,
                include_feedback=True,
                columns=["inputs.dataset", "display_name", "parent_id"],
                expand_columns=["inputs.dataset"],
            )
        ).calls
    )
    for call1, call2 in zip(client_result, server_result, strict=False):
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

    sort_by = [SortBy(field="inputs.a", direction="asc")]

    calls = client.get_calls(limit=3, sort_by=sort_by)
    assert len(calls) == 3
    for i, call in enumerate(calls):
        assert call.inputs["a"] == i

    calls = client.get_calls(limit=5, offset=5, sort_by=sort_by)
    assert len(calls) == 5

    for i, call in enumerate(calls):
        assert call.inputs["a"] == i + 5

    calls = client.get_calls(offset=9, sort_by=sort_by)
    assert len(calls) == 1
    assert calls[0].inputs["a"] == 9

    # now test indexing
    calls = client.get_calls(sort_by=sort_by)
    assert calls[0].inputs["a"] == 0
    assert calls[1].inputs["a"] == 1
    assert calls[2].inputs["a"] == 2
    assert calls[3].inputs["a"] == 3
    assert calls[4].inputs["a"] == 4

    calls = client.get_calls(offset=5, sort_by=sort_by)
    assert calls[0].inputs["a"] == 5
    assert calls[1].inputs["a"] == 6
    assert calls[2].inputs["a"] == 7
    assert calls[3].inputs["a"] == 8
    assert calls[4].inputs["a"] == 9

    # slicing
    calls = client.get_calls(offset=5, sort_by=sort_by)
    for i, call in enumerate(calls[2:]):
        assert call.inputs["a"] == 7 + i


def test_get_calls_page_size_with_offset(client):
    for i in range(20):
        client.create_call("x", {"a": i})

    batch_size = 5
    batch_num = 0
    all_call_ids = []
    all_values = []

    while True:
        call_batch = client.get_calls(
            limit=batch_size,
            offset=batch_num * batch_size,
            page_size=2,
        )

        # Convert to list to force fetch
        call_batch_list = list(call_batch)
        if not call_batch_list:
            break

        # Store call IDs
        batch_call_ids = [call.id for call in call_batch_list]
        all_call_ids.extend(batch_call_ids)

        values = [call.inputs["a"] for call in call_batch_list]
        all_values.extend(values)
        batch_num += 1

    assert len(all_call_ids) == 20
    # Use sorted() because calls created in a tight loop may share the same
    # started_at timestamp (especially on Windows with ~15ms clock resolution),
    # and the default sort tiebreaker (id DESC) uses random UUIDv7 suffixes
    # which don't preserve insertion order.
    assert sorted(all_values) == list(range(20))


def test_calls_delete(client):
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call0_child1 = client.create_call("x", {"a": 5, "b": 11}, call0)
    _call0_child2 = client.create_call("x", {"a": 5, "b": 12}, call0_child1)
    call1 = client.create_call("y", {"a": 6, "b": 11})

    assert len(list(client.get_calls())) == 4

    result = list(client.get_calls(filter={"op_names": [call0.op_name]}))
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
    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op
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


def test_delete_calls(client):
    @weave.op
    def my_op(a: int) -> int:
        return a + 1

    call0 = my_op(1)
    call1 = my_op(2)
    call2 = my_op(3)

    calls = client.get_calls()
    assert len(calls) == 3

    call_0_id = calls[0].id
    call_1_id = calls[1].id
    call_2_id = calls[2].id

    client.delete_calls([call_0_id, call_1_id])
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].id == call_2_id

    # test idempotent
    client.delete_calls([call_0_id, call_1_id])
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].id == call_2_id

    client.delete_calls([])
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].id == call_2_id

    with pytest.raises(ValueError):
        client.delete_calls([1111111111111111])

    client.delete_calls([call_2_id])
    calls = client.get_calls()
    assert len(calls) == 0


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
    op_name = ""
    for row in ref.rows:
        call = client.create_call("x", {"a": row["doc"]})
        op_name = call.op_name
        client.finish_call(call, None)

    calls = list(client.get_calls(filter={"op_names": [op_name]}))
    assert calls[0].inputs["a"] == "xx"
    assert calls[1].inputs["a"] == "yy"


@pytest.mark.skip
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


@pytest.mark.skip
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
    @weave.op
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

        @weave.op
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

    @weave.op
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

    op = next(x for x in res.objs if x.kind == "op")
    assert op.object_id == "hello_world"
    assert op.project_id == "shawn/test-project2"
    assert op.kind == "op"

    obj = next(x for x in res.objs if x.kind == "object")
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

        @weave.op
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

        @weave.op
        async def call(self, input):
            return self.x + input

    class B(weave.Object):
        a: A
        y: int

        @weave.op
        async def call(self, input):
            return await self.a.call(input - self.y)

    model = B(a=A(x=3), y=2)
    ref = client._save_object(model, "my-model")
    model2 = client.get(ref)

    class C(weave.Object):
        b: B
        z: int

        @weave.op
        async def call(self, input):
            return await self.b.call(input - 2 * self.z)

    @weave.op
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
    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]

    @weave.op
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

    @weave.op
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
    @weave.op
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


def test_refs_read_batch_call_ref(client):
    call_ref = refs.CallRef(entity="shawn", project="test-project", id="my-call")
    with pytest.raises(ValueError, match="Call refs not supported"):
        client.server.refs_read_batch(RefsReadBatchReq(refs=[call_ref.uri()]))


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
    @weave.op
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

    @weave.op
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

    @weave.op
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

    call = next(iter(models.calls()))

    assert call.summary["usage"] == {
        "model_a": {"requests": 2, "prompt_tokens": 10, "completion_tokens": 16},
        "model_b": {"requests": 1, "prompt_tokens": 5, "completion_tokens": 11},
    }


@pytest.mark.skip("descendent error tracking disabled until we fix UI")
def test_summary_descendents(client):
    @weave.op
    def model_a(text):
        return "a: " + text

    @weave.op
    def model_b(text):
        return "bbbb: " + text

    @weave.op
    def model_error(text):
        raise ValueError("error: " + text)

    @weave.op
    def model_error_catch(text):
        try:
            model_error(text)
        except ValueError as e:
            return str(e)

    @weave.op
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

    call = next(iter(models.calls()))

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

        @weave.op
        def predict(self, input: str) -> str:
            return self.prompt.format(input=input)

    model = MyModel(prompt="input is: {input}")
    ref = client._save_object(model, "my-model")

    url = weave.serve(ref, thread=True)
    with httpx.Client() as http_client:
        response = http_client.post(url + "/predict", json={"input": "x"})
    assert response.json() == {"result": "input is: x"}


def row_gen(num_rows: int, approx_row_bytes: int = 1024):
    for i in range(num_rows):
        yield {"a": i, "b": "x" * approx_row_bytes}


@pytest.mark.parametrize("use_parallel_table_upload", [False, True])
def test_table_partitioning(network_proxy_client, use_parallel_table_upload):
    """This test is specifically testing the correctness
    of the table partitioning logic in the remote client.
    In particular, the ability to partition large dataset
    creation into multiple updates.
    """
    client, remote_client, records = network_proxy_client

    # Set the parallel table upload setting for this test
    test_settings = settings.UserSettings(
        use_parallel_table_upload=use_parallel_table_upload
    )
    settings.parse_and_apply_settings(test_settings)

    num_rows = 16
    rows = list(row_gen(num_rows, 1024))
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

    # Set the client to use the remote server so calls get recorded
    client = TestOnlyFlushingWeaveClient(
        entity=client.entity,
        project=client.project,
        server=remote_client,
        ensure_project_exists=False,
    )

    # Create a Table object and save it to trigger chunking logic
    table_obj = weave_client.Table(rows)
    saved_table = client.save(table_obj, "table")

    assert saved_table.table_ref._digest == exp_digest

    if use_parallel_table_upload:
        # Verify that chunking happened by checking for table_create_from_digests call
        table_create_records = [r for r in records if r[0] == "table_create"]
        table_create_from_digests_records = [
            r for r in records if r[0] == "table_create_from_digests"
        ]
        obj_records = [r for r in records if r[0] in ["obj_create", "obj_read"]]

        # Expected: 2 table_create calls (first + second) + 1 table_create_from_digests (chunking merge)
        assert len(table_create_records) == 2, (
            f"Expected 2 table_create calls, got {len(table_create_records)}"
        )
        # 1 for testing if the endpoint exists, 1 for the actual request
        assert len(table_create_from_digests_records) == 2, (
            f"Expected 2 table_create_from_digests calls, got {len(table_create_from_digests_records)}"
        )
        assert len(obj_records) == 2, (
            f"Expected 2 obj_create/obj_read calls, got {len(obj_records)}"
        )
        assert len(records) == 6, f"Expected 6 total records, got {len(records)}"


def test_summary_tokens_cost(client):
    if client_is_sqlite(client):
        # SQLite does not support costs
        return

    @weave.op
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

    @weave.op
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

    @weave.op
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

    call = next(iter(models.calls()))

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

    calls_with_cost = list(
        client.get_calls(
            filter=tsi.CallsFilter(op_names=[call.op_name]),
            include_costs=True,
        )
    )
    calls_no_cost = list(
        client.get_calls(
            filter=tsi.CallsFilter(op_names=[call.op_name]),
            include_costs=False,
        )
    )

    assert len(calls_with_cost) == len(calls_no_cost)
    assert len(calls_with_cost) == 1

    no_cost_call_summary = calls_no_cost[0].summary
    with_cost_call_summary = calls_with_cost[0].summary

    assert with_cost_call_summary.get("weave", "bah") != "bah"
    assert len(with_cost_call_summary["weave"]["costs"]) == 2

    gpt4cost = with_cost_call_summary["weave"]["costs"]["gpt-4"]
    gpt4ocost = with_cost_call_summary["weave"]["costs"]["gpt-4o"]

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
            "cached_prompt_tokens": 0,
            "prompt_tokens_total_cost": pytest.approx(60),
            "cached_prompt_tokens_total_cost": pytest.approx(0),
            "completion_tokens_total_cost": pytest.approx(240),
            "prompt_token_cost": 3e-05,
            "cached_prompt_token_cost": 3e-05,
            "completion_token_cost": 6e-05,
            "prompt_token_cost_unit": "USD",
            "cached_prompt_token_cost_unit": "USD",
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
            "cached_prompt_tokens": 0,
            "prompt_tokens_total_cost": pytest.approx(15),
            "cached_prompt_tokens_total_cost": pytest.approx(0),
            "completion_tokens_total_cost": pytest.approx(75),
            "prompt_token_cost": 5e-06,
            "cached_prompt_token_cost": 5e-06,
            "completion_token_cost": 1.5e-05,
            "prompt_token_cost_unit": "USD",
            "cached_prompt_token_cost_unit": "USD",
            "completion_token_cost_unit": "USD",
            "provider_id": "openai",
            "pricing_level": "default",
            "pricing_level_id": "default",
            "created_by": "system",
        }
    )

    # for no cost call, there should be no cost information
    # currently that means no weave object in the summary
    assert no_cost_call_summary["weave"] == {
        "status": "success",
        "trace_name": "models",
        "latency_ms": AnyIntMatcher(),
    }


def test_summary_tokens_cost_uses_cached_tokens(client):
    if client_is_sqlite(client):
        # SQLite does not support costs
        return

    project_id = client._project_id()
    prompt_token_cost = 5e-06
    cached_prompt_token_cost = 2.5e-06
    cost_res = client.server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs={
                "gpt-4o": tsi.CostCreateInput(
                    prompt_token_cost=prompt_token_cost,
                    completion_token_cost=1.5e-05,
                    cached_prompt_token_cost=cached_prompt_token_cost,
                    effective_date=datetime.datetime.now(datetime.timezone.utc)
                    - datetime.timedelta(days=1),
                )
            },
            wb_user_id="VXNlcjo0NTI1NDQ=",
        )
    )
    cost_id = cost_res.ids[0][0]

    @weave.op
    def cached_prompt_op() -> dict[str, Any]:
        return {
            "result": "ok",
            "model": "gpt-4o",
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 0,
                "total_tokens": 1000,
                "prompt_tokens_details": {"cached_tokens": 900},
            },
        }

    try:
        cached_prompt_op()
        op_call = next(iter(cached_prompt_op.calls()))
        calls = list(
            client.get_calls(
                filter=tsi.CallsFilter(op_names=[op_call.op_name]),
                include_costs=True,
            )
        )
        assert len(calls) == 1
        call_summary = calls[0].summary
        assert call_summary is not None
        assert call_summary.get("weave", {}).get("costs") is not None

        gpt4o_cost = call_summary["weave"]["costs"]["gpt-4o"]
        expected_prompt_cost = (1000 - 900) * prompt_token_cost + (
            900 * cached_prompt_token_cost
        )
        full_prompt_cost = 1000 * prompt_token_cost

        assert gpt4o_cost["prompt_tokens"] == 1000
        assert gpt4o_cost["cached_prompt_tokens"] == 900
        assert gpt4o_cost["cached_prompt_token_cost"] == pytest.approx(
            cached_prompt_token_cost
        )
        assert gpt4o_cost["cached_prompt_tokens_total_cost"] == pytest.approx(
            900 * cached_prompt_token_cost
        )
        assert gpt4o_cost["prompt_tokens_total_cost"] == pytest.approx(
            expected_prompt_cost
        )
        assert gpt4o_cost["prompt_tokens_total_cost"] < full_prompt_cost
    finally:
        client.purge_costs(cost_id)


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

    calls_with_cost = list(client.get_calls(include_costs=True))
    calls_no_cost = list(client.get_calls(include_costs=False))

    assert len(calls_with_cost) == len(calls_no_cost)
    assert len(calls_with_cost) == 4

    no_cost_call_summary = calls_no_cost[0].summary
    with_cost_call_summary = calls_with_cost[0].summary

    weave_summary = {
        "weave": {
            "status": "running",
            "trace_name": "x",
        }
    }

    assert no_cost_call_summary == weave_summary
    assert with_cost_call_summary == weave_summary


def _setup_calls_for_storage_size_test(client):
    """Helper function to set up calls for storage size tests.

    Returns:
        List of created Call objects.
    """
    call0 = client.create_call("x", {"a": 5, "b": 10})
    call0_child1 = client.create_call("x", {"a": 5, "b": 11}, call0)
    call1 = client.create_call("y", {"a": 6, "b": 11})
    return [call0, call0_child1, call1]


def test_get_calls_storage_size_with_filter(client):
    """Test that storage size parameters can be combined with other get_calls parameters."""
    all_calls = _setup_calls_for_storage_size_test(client)
    assert len(all_calls) > 2

    call0 = all_calls[0]

    # Test that parameters can be combined with other parameters
    calls_filtered = list(
        client.get_calls(
            filter=tsi.CallsFilter(op_names=[call0.op_name]),
            include_storage_size=True,
            include_total_storage_size=True,
        )
    )
    assert len(calls_filtered) == 2


def test_get_calls_storage_size_with_limit(client):
    """Test that storage size parameters can be combined with other get_calls parameters."""
    all_calls = _setup_calls_for_storage_size_test(client)
    assert len(all_calls) > 2

    # Test that parameters can be combined with other parameters
    calls_limited = list(
        client.get_calls(
            include_storage_size=True,
            include_total_storage_size=True,
            limit=2,
        )
    )
    assert len(calls_limited) == 2


@pytest.fixture
def clickhouse_client(client):
    if client_is_sqlite(client):
        return None
    return client.server._next_trace_server.ch_client


def test_get_calls_storage_size_values(client, clickhouse_client):
    """Test that storage size values are correctly included when parameters are set."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    _setup_calls_for_storage_size_test(client)

    # This is a best effort to achieve consistency in the calls_merged_stats table.
    # calls_merged_stats is an AggregatingMergeTree table populated by a materialized view.
    # ClickHouse merges data asynchronously, so queries may see unmerged data.
    # OPTIMIZE TABLE ... FINAL forces an immediate merge to ensure consistency for tests.
    if clickhouse_client:
        clickhouse_client.command("OPTIMIZE TABLE calls_merged_stats FINAL")

    # Get calls via get_calls with storage size parameters
    client_calls = list(
        client.get_calls(include_storage_size=True, include_total_storage_size=True)
    )

    # Get calls directly from server with same parameters
    server_calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client._project_id(),
                include_storage_size=True,
                include_total_storage_size=True,
            )
        )
    )

    # Verify same number of calls
    assert len(client_calls) == len(server_calls)
    assert len(server_calls) > 0

    # Verify that get_calls returns the same calls (by ID) as direct server calls
    client_call_ids = {call.id for call in client_calls if call.id}
    server_call_ids = {call.id for call in server_calls if call.id}
    assert client_call_ids == server_call_ids

    # Create a mapping of call IDs to client calls for easy lookup
    client_calls_by_id = {call.id: call for call in client_calls if call.id}

    # Verify storage size fields and compare values between server and client calls
    for server_call in server_calls:
        # Verify storage size fields are present on server calls
        assert hasattr(server_call, "storage_size_bytes")
        assert hasattr(server_call, "total_storage_size_bytes")

        # Verify that storage size values match between server and client calls
        if server_call.id and server_call.id in client_calls_by_id:
            client_call = client_calls_by_id[server_call.id]
            assert server_call.storage_size_bytes == client_call.storage_size_bytes
            assert (
                server_call.total_storage_size_bytes
                == client_call.total_storage_size_bytes
            )
            assert server_call.storage_size_bytes is not None

            # total_storage_size_bytes is only set for root calls (parent_id is None)
            # For child calls, it is intentionally None
            expect_total_storage_size_bytes = server_call.parent_id is None
            assert expect_total_storage_size_bytes == (
                server_call.total_storage_size_bytes is not None
            )


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
            filter=tsi.ObjectVersionFilter(object_ids=[refs[0].name]),
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
    @weave.op
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
            filter=tsi.ObjectVersionFilter(object_ids=["my-obj"]),
            sort_by=[SortBy(field="created_at", direction="desc")],
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
            filter=tsi.ObjectVersionFilter(object_ids=["my-obj"]),
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
    @weave.op
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
    @weave.op
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
    @weave.op
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
        time.sleep(0.01)

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
        time.sleep(0.01)

    op_1()

    def fake_logger(status):
        assert "job_counts" in status

    # flush with callback
    client.finish(callback=fake_logger)

    # make sure there are no pending jobs
    assert client._get_pending_jobs()["total_jobs"] == 0
    assert client._has_pending_jobs() == False


def test_repeated_flushing(client):
    client.set_autoflush(False)

    @weave.op
    def op_1():
        time.sleep(0.01)

    op_1()
    client.flush()
    op_1()
    op_1()
    client.flush()

    calls = list(op_1.calls())
    assert len(calls) == 3

    op_1()
    client.flush()
    client.flush()
    client.flush()

    calls = list(op_1.calls())
    assert len(calls) == 4
    # make sure there are no pending jobs
    assert client._get_pending_jobs()["total_jobs"] == 0
    assert client._has_pending_jobs() == False


def test_calls_query_filter_by_strings(client):
    """Test string filter optimization with nested queries."""
    test_id = str(uuid.uuid4())

    @weave.op
    def test_op(test_id: str, name: str, tags: list[str], value: int, active: bool):
        return {
            "test_id": test_id,
            "name": name,
            "tags": tags,
            "value": value,
            "active": active,
        }

    @weave.op
    def dummy_op():
        return {"woooo": "test"}

    test_op(test_id, "alpha_test", ["frontend", "ui"], 100, "True")
    test_op(test_id, "beta_test", ["backend", "api"], 200, "False")
    test_op(test_id, "gamma_test", ["frontend", "mobile"], 300, "True")
    test_op(test_id, "delta_test", ["backend", "database"], 400, "False")
    test_op(test_id, "epsilon_test", ["frontend", "api"], 500, "True")

    for _i in range(5):
        dummy_op()

    # Flush to ensure all calls are persisted
    client.flush()

    # Basic filter - should return all 5 calls
    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}}
    )
    calls = list(client.get_calls(query=query))
    assert len(calls) == 5

    # Filter with string contains - should return 5 calls (name contains "test")
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$contains": {
                            "input": {"$getField": "inputs.name"},
                            "substr": {"$literal": "test"},
                        }
                    },
                ]
            }
        }
    )
    calls = list(client.get_calls(query=query))
    assert len(calls) == 5  # All names contain "test"
    for call in calls:
        assert "test" in call.inputs["name"]
        assert "test" in call.output["name"]
        assert call.inputs["test_id"] == test_id
        assert call.output["test_id"] == test_id
        assert call.inputs["value"] > 0

    # Filter with string contains - should return 1 call (name contains "alpha")
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$contains": {
                            "input": {"$getField": "inputs.name"},
                            "substr": {"$literal": "alpha"},
                        }
                    },
                ]
            }
        }
    )
    calls = list(client.get_calls(query=query))
    assert len(calls) == 1
    assert calls[0].inputs["name"] == "alpha_test"
    assert calls[0].output["name"] == "alpha_test"
    assert calls[0].inputs["test_id"] == test_id
    assert calls[0].output["test_id"] == test_id
    assert calls[0].inputs["value"] == 100

    # Filter with string in - should return 2 calls (tags contains "api")
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$in": [
                            {"$getField": "inputs.name"},
                            [
                                {"$literal": "delta_test"},
                                {"$literal": "gamma_test"},
                            ],
                        ]
                    },
                ]
            }
        }
    )
    calls = list(client.get_calls(query=query))
    assert len(calls) == 2
    for call in calls:
        assert "test" in call.inputs["name"]
        assert "test" in call.output["name"]
        assert call.inputs["test_id"] == test_id
        assert call.output["test_id"] == test_id
        assert call.inputs["value"] > 0

    # Filter with boolean - should return 3 calls (active is true)
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$eq": [{"$getField": "inputs.active"}, {"$literal": "True"}]},
                ]
            }
        }
    )
    calls = list(client.get_calls(query=query))
    assert len(calls) == 3
    for call in calls:
        assert "test" in call.inputs["name"]
        assert "test" in call.output["name"]
        assert call.inputs["test_id"] == test_id
        assert call.output["test_id"] == test_id
        assert call.inputs["value"] > 0

    # Filter with OR - should return 4 calls (name contains "alpha" or "beta" or value > 300)
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$or": [
                            {
                                "$contains": {
                                    "input": {"$getField": "inputs.name"},
                                    "substr": {"$literal": "alpha"},
                                }
                            },
                            {
                                "$contains": {
                                    "input": {"$getField": "inputs.name"},
                                    "substr": {"$literal": "beta"},
                                }
                            },
                            {
                                "$gt": [
                                    {"$getField": "inputs.value"},
                                    {"$literal": "300"},
                                ]
                            },
                        ]
                    },
                ]
            }
        }
    )
    # name has alpha or beta or value > 300
    calls = list(client.get_calls(query=query))
    assert len(calls) == 4
    for call in calls:
        assert "test" in call.inputs["name"]
        assert "test" in call.output["name"]
        assert call.inputs["test_id"] == test_id
        assert call.output["test_id"] == test_id
        assert call.inputs["value"] > 0

    # Complex nested filter - should return exactly 1 call (name contains "epsilon" and active is true)
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$contains": {
                            "input": {"$getField": "inputs.name"},
                            "substr": {"$literal": "epsilon"},
                        }
                    },
                    {"$eq": [{"$getField": "inputs.active"}, {"$literal": "True"}]},
                ]
            }
        }
    )
    calls = list(client.get_calls(query=query))
    assert len(calls) == 1
    assert calls[0].inputs["name"] == "epsilon_test"
    assert calls[0].output["name"] == "epsilon_test"
    assert calls[0].inputs["test_id"] == test_id
    assert calls[0].output["test_id"] == test_id
    assert calls[0].inputs["value"] == 500

    # Extremely complex nested filter with multiple levels of nesting
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    # Condition 1: Must match the test_id
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    # Condition 2: Name must contain "alpha" and be active, OR contain "delta" and be inactive
                    {
                        "$or": [
                            {
                                "$and": [
                                    {
                                        "$contains": {
                                            "input": {"$getField": "inputs.name"},
                                            "substr": {"$literal": "alpha"},
                                        }
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.active"},
                                            {"$literal": "True"},
                                        ]
                                    },
                                ]
                            },
                            {
                                "$and": [
                                    {
                                        "$contains": {
                                            "input": {"$getField": "inputs.name"},
                                            "substr": {"$literal": "delta"},
                                        }
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.active"},
                                            {
                                                "$literal": "False"
                                            },  # should filter out beta
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                    # Condition 3: Value must be >= 400, OR active must be true
                    {
                        "$or": [
                            {
                                "$gte": [
                                    {"$getField": "inputs.value"},
                                    {"$literal": "400"},
                                ]
                            },
                            {
                                "$eq": [
                                    {"$getField": "inputs.active"},
                                    {"$literal": "True"},
                                ]
                            },
                        ]
                    },
                ]
            }
        }
    )

    # Test breakdown:
    # 1. We create a complex query with multiple conditions:
    #    - Condition 1: name must be "alpha_test" AND value must be >= 100
    #    - Condition 2: name must be "beta_test" AND value must be < 200
    #    - Condition 3: name must be "delta_test" AND (value >= 400 OR active must be true)
    # 2. The query uses $and to combine these three conditions, meaning all must be satisfied
    # 3. We expect exactly 2 calls to match:
    #    - One with name "alpha_test" (matching condition 1)
    #    - One with name "delta_test" (matching condition 3)
    # 4. The test verifies both the count and the specific names of the matching calls

    calls = list(client.get_calls(query=query))
    assert len(calls) == 2
    assert calls[0].inputs["name"] == "alpha_test"
    assert calls[0].output["name"] == "alpha_test"
    assert calls[1].inputs["name"] == "delta_test"
    assert calls[1].output["name"] == "delta_test"
    for call in calls:
        assert call.inputs["test_id"] == test_id
        assert call.output["test_id"] == test_id
        assert call.inputs["value"] > 0


def test_calls_default_sort_secondary_id_asc(client):
    """Test that the default sort uses id ASC as a secondary tiebreaker.

    When no explicit sort_by is provided, calls should be sorted by
    started_at ASC, then id ASC. This test creates three calls with
    identical started_at timestamps but different explicit IDs, then
    verifies that within the same started_at group the ids are returned
    in ascending order.
    """
    # Use explicit IDs that have a clear lexicographic ordering:
    # id_small < id_mid < id_large
    id_small = "00000000-0000-7000-8000-00000000000a"
    id_mid = "00000000-0000-7000-8000-00000000000b"
    id_large = "00000000-0000-7000-8000-00000000000c"

    # All calls share the exact same started_at to force the tiebreaker
    fixed_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
    project_id = client._project_id()
    trace_id = generate_id()

    # Insert calls via server API with controlled ids and started_at.
    # Insert in ascending id order to ensure the sort isn't just insertion order.
    for call_id in [id_small, id_mid, id_large]:
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=trace_id,
                    op_name="test_secondary_sort",
                    started_at=fixed_time,
                    attributes={},
                    inputs={"call_id": call_id},
                )
            )
        )
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=fixed_time + datetime.timedelta(seconds=1),
                    output={"result": "ok"},
                    summary={},
                )
            )
        )

    # Query with default sort (no sort_by) -- should be started_at ASC, id ASC
    result = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
            filter=tsi.CallsFilter(op_names=["test_secondary_sort"]),
        )
    )
    returned_ids = [c.id for c in result.calls]
    assert len(returned_ids) == 3

    # All have the same started_at, so order is determined by id ASC:
    # id_small < id_mid < id_large
    assert returned_ids == [id_small, id_mid, id_large], (
        f"Expected id ASC tiebreaker order [{id_small}, {id_mid}, {id_large}], "
        f"but got {returned_ids}"
    )

    # Also verify with explicit sort_by -- when sorting by started_at,
    # secondary id sort should match the started_at direction for perf
    result_explicit = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
            filter=tsi.CallsFilter(op_names=["test_secondary_sort"]),
            sort_by=[SortBy(field="started_at", direction="asc")],
        )
    )
    returned_ids_explicit = [c.id for c in result_explicit.calls]
    assert returned_ids_explicit == [id_small, id_mid, id_large], (
        f"Expected id ASC tiebreaker with explicit sort [{id_small}, {id_mid}, {id_large}], "
        f"but got {returned_ids_explicit}"
    )


def test_calls_query_sort_by_status(client):
    """Test that sort_by summary.weave.status works with get_calls."""
    # Use a unique test ID to identify these calls
    test_id = str(uuid.uuid4())

    # Create calls with different statuses
    success_call = client.create_call("x", {"a": 1, "b": 1, "test_id": test_id})
    client.finish_call(
        success_call, "success result"
    )  # This will have status "success"

    # Create a call with an error status
    error_call = client.create_call("x", {"a": 2, "b": 2, "test_id": test_id})
    e = ValueError("Test error")
    client.finish_call(error_call, None, exception=e)  # This will have status "error"

    # Create a call with running status (no finish_call)
    running_call = client.create_call(
        "x", {"a": 3, "b": 3, "test_id": test_id}
    )  # This will have status "running"

    # Flush to make sure all calls are committed
    client.flush()

    # Create a query to find just our test calls
    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}}
    )

    # Ascending sort - running, error, success
    calls_asc = list(
        client.get_calls(
            query=query,
            sort_by=[SortBy(field="summary.weave.status", direction="asc")],
        )
    )

    # Verify order - should be error, running, success in ascending order
    assert len(calls_asc) == 3
    # "error" comes first alphabetically
    assert calls_asc[0].id == error_call.id
    # "running" comes second
    assert calls_asc[1].id == running_call.id
    # "success" comes last
    assert calls_asc[2].id == success_call.id

    # Descending sort - success, error, running
    calls_desc = list(
        client.get_calls(
            query=query,
            sort_by=[SortBy(field="summary.weave.status", direction="desc")],
        )
    )

    # Verify order - should be success, running, error in descending order
    assert len(calls_desc) == 3
    # "success" comes first
    assert calls_desc[0].id == success_call.id
    # "running" comes second
    assert calls_desc[1].id == running_call.id
    # "error" comes last
    assert calls_desc[2].id == error_call.id


def test_calls_query_sort_by_latency(client):
    """Test that sort_by summary.weave.latency_ms works with get_calls."""
    # Use a unique test ID to identify these calls
    test_id = str(uuid.uuid4())

    # Create calls with different latencies
    # Fast call - minimal latency
    fast_call = client.create_call("x", {"a": 1, "b": 1, "test_id": test_id})
    client.finish_call(fast_call, "fast result")
    client.flush()

    # Medium latency
    medium_call = client.create_call("x", {"a": 2, "b": 2, "test_id": test_id})
    # Sleep to ensure different latency
    time.sleep(0.05)
    client.finish_call(medium_call, "medium result")
    client.flush()

    # Slow call - higher latency
    slow_call = client.create_call("x", {"a": 3, "b": 3, "test_id": test_id})
    # Sleep to ensure different latency
    time.sleep(0.1)
    client.finish_call(slow_call, "slow result")
    client.flush()

    # Create a query to find just our test calls
    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}}
    )

    # Ascending sort (fast to slow)
    calls_asc = list(
        client.get_calls(
            query=query,
            sort_by=[SortBy(field="summary.weave.latency_ms", direction="asc")],
        )
    )

    # Verify order - should be fast, medium, slow in ascending order
    assert len(calls_asc) == 3
    assert calls_asc[0].id == fast_call.id
    assert calls_asc[1].id == medium_call.id
    assert calls_asc[2].id == slow_call.id

    # Descending sort (slow to fast)
    calls_desc = list(
        client.get_calls(
            query=query,
            sort_by=[SortBy(field="summary.weave.latency_ms", direction="desc")],
        )
    )

    # Verify order - should be slow, medium, fast in descending order
    assert len(calls_desc) == 3
    assert calls_desc[0].id == slow_call.id
    assert calls_desc[1].id == medium_call.id
    assert calls_desc[2].id == fast_call.id


def test_calls_filter_by_status(client):
    """Test filtering calls by status using get_calls."""
    # Use a unique test ID to identify these calls
    test_id = str(uuid.uuid4())

    # Create calls with different statuses
    success_call = client.create_call("x", {"a": 1, "b": 1, "test_id": test_id})
    client.finish_call(success_call, "success result")  # Status: success

    error_call = client.create_call("x", {"a": 2, "b": 2, "test_id": test_id})
    e = ValueError("Test error")
    client.finish_call(error_call, None, exception=e)  # Status: error

    running_call = client.create_call(
        "x", {"a": 3, "b": 3, "test_id": test_id}
    )  # Status: running

    # Flush to make sure all calls are committed
    client.flush()

    # Get all calls to examine their structure
    base_query = {
        "$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}
    }
    all_calls = list(client.get_calls(query=tsi.Query(**base_query)))
    assert len(all_calls) == 3

    # Print summary structure to debug
    for call in all_calls:
        if call.id == success_call.id:
            print(f"Success call summary: {call.summary}")
        elif call.id == error_call.id:
            print(f"Error call summary: {call.summary}")
        elif call.id == running_call.id:
            print(f"Running call summary: {call.summary}")

    # Using the 'filter' parameter instead of complex query for status
    # This is a more reliable way to filter by status
    success_calls = list(
        client.get_calls(filter=tsi.CallsFilter(call_ids=[success_call.id]))
    )
    assert len(success_calls) == 1
    assert success_calls[0].id == success_call.id
    assert success_calls[0].summary.get("weave", {}).get("status") == "success"

    error_calls = list(
        client.get_calls(filter=tsi.CallsFilter(call_ids=[error_call.id]))
    )
    assert len(error_calls) == 1
    assert error_calls[0].id == error_call.id
    assert error_calls[0].summary.get("weave", {}).get("status") == "error"

    running_calls = list(
        client.get_calls(filter=tsi.CallsFilter(call_ids=[running_call.id]))
    )
    assert len(running_calls) == 1
    assert running_calls[0].id == running_call.id
    assert running_calls[0].summary.get("weave", {}).get("status") == "running"


def test_calls_filter_by_latency(client):
    """Test filtering calls by latency using get_calls."""
    # Use a unique test ID to identify these calls
    test_id = str(uuid.uuid4())

    # Create calls with different latencies.
    # Use substantial sleep differences to ensure reliable latency ordering
    # across all backends (SQLite, ClickHouse).
    fast_call = client.create_call("x-fast", {"a": 1, "b": 1, "test_id": test_id})
    time.sleep(0.05)
    client.finish_call(fast_call, "fast result")

    medium_call = client.create_call("x-medium", {"a": 2, "b": 2, "test_id": test_id})
    time.sleep(0.3)
    client.finish_call(medium_call, "medium result")

    slow_call = client.create_call("x-slow", {"a": 3, "b": 3, "test_id": test_id})
    time.sleep(0.6)
    client.finish_call(slow_call, "slow result")

    # Flush to make sure all calls are committed
    client.flush()

    # Get all test calls to determine actual latencies
    base_query = {
        "$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}
    }
    all_calls = list(client.get_calls(query=tsi.Query(**base_query)))
    assert len(all_calls) == 3

    # Verify asc order: latencies should be monotonically non-decreasing
    sorted_calls_asc = list(
        client.get_calls(
            query=tsi.Query(**base_query),
            sort_by=[SortBy(field="summary.weave.latency_ms", direction="asc")],
        )
    )
    latencies_asc = [
        c.summary.get("weave", {}).get("latency_ms") for c in sorted_calls_asc
    ]
    # All latencies should be present (non-None)
    assert all(lat is not None for lat in latencies_asc), (
        f"Expected all calls to have latency_ms, but got {latencies_asc}"
    )
    for i in range(len(latencies_asc) - 1):
        assert latencies_asc[i] <= latencies_asc[i + 1], (
            f"Expected latency ASC order, but got {latencies_asc}"
        )

    # Verify desc order: latencies should be monotonically non-increasing
    sorted_calls_desc = list(
        client.get_calls(
            query=tsi.Query(**base_query),
            sort_by=[SortBy(field="summary.weave.latency_ms", direction="desc")],
        )
    )
    latencies_desc = [
        c.summary.get("weave", {}).get("latency_ms") for c in sorted_calls_desc
    ]
    assert all(lat is not None for lat in latencies_desc), (
        f"Expected all calls to have latency_ms, but got {latencies_desc}"
    )
    for i in range(len(latencies_desc) - 1):
        assert latencies_desc[i] >= latencies_desc[i + 1], (
            f"Expected latency DESC order, but got {latencies_desc}"
        )

    # Filter by latency, Float
    latency_calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$gte": [
                        {"$getField": "summary.weave.latency_ms"},
                        {"$literal": 0.001},
                    ]
                }
            }
        )
    )
    assert len(latency_calls) == 3

    # Filter by latency, Int
    latency_calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "summary.weave.latency_ms"},
                        {"$literal": 10},
                    ]
                }
            }
        )
    )
    assert len(latency_calls) == 0


def test_calls_query_sort_by_trace_name(client):
    """Test that sort_by and filter by summary.weave.trace_name works with get_calls."""
    # Use a unique test ID to identify these calls
    test_id = str(uuid.uuid4())

    # Create calls with different trace_names - one uses display_name, one uses op_name reference, one is plain

    # Call 1: with display_name - this should be prioritized for trace_name
    display_name_call = client.create_call("simple_op", {"test_id": test_id})
    display_name_call.set_display_name(
        "B_display_name"
    )  # Using B_ prefix for testing alphabetical order
    client.finish_call(display_name_call, "result")

    # Call 2: with weave reference op_name - should extract name from reference
    ref_op_name = "weave:///user/project/object/A_ref_name:digest"
    ref_call = client.create_call(ref_op_name, {"test_id": test_id})
    client.finish_call(ref_call, "result")

    # Call 3: with plain op_name - should use op_name directly
    plain_call = client.create_call("C_plain_op", {"test_id": test_id})
    client.finish_call(plain_call, "result")

    # Flush to make sure all calls are committed
    client.flush()

    # Create a query to find just our test calls
    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}}
    )

    # Get all calls for our test
    all_calls = list(client.get_calls(query=query))

    # Check that we have all three test calls
    assert len(all_calls) == 3

    # Instead of relying on sorting which has ClickHouse compatibility issues,
    # we'll verify that the trace_name is correctly calculated for each call type

    # Create a map of call IDs to calls
    calls_by_id = {call.id: call for call in all_calls}

    # Verify display_name call - should have trace_name matching the display name
    display_name_call_obj = calls_by_id.get(display_name_call.id)
    assert display_name_call_obj is not None
    # Note: the trace_name field might not be directly accessible, but we want to verify
    # the display_name in the retrieved call matches what we set
    assert display_name_call_obj.display_name == "B_display_name"

    # Verify ref_name call - should have op_name matching the reference format
    ref_call_obj = calls_by_id.get(ref_call.id)
    assert ref_call_obj is not None
    # The reference may be normalized by the system, so just check it contains expected parts
    assert "weave://" in ref_call_obj.op_name
    assert "A_ref_name" in ref_call_obj.op_name

    # Verify plain_call - should have op_name as a Weave reference containing the original name
    plain_call_obj = calls_by_id.get(plain_call.id)
    assert plain_call_obj is not None
    assert "weave://" in plain_call_obj.op_name
    assert "C_plain_op" in plain_call_obj.op_name

    # Verify filtering capabilities for trace_name
    # Test filter by individual call IDs to ensure we can fetch specific calls
    display_name_call_result = list(
        client.get_calls(filter=tsi.CallsFilter(call_ids=[display_name_call.id]))
    )
    assert len(display_name_call_result) == 1
    assert display_name_call_result[0].id == display_name_call.id

    ref_call_result = list(
        client.get_calls(filter=tsi.CallsFilter(call_ids=[ref_call.id]))
    )
    assert len(ref_call_result) == 1
    assert ref_call_result[0].id == ref_call.id

    plain_call_result = list(
        client.get_calls(filter=tsi.CallsFilter(call_ids=[plain_call.id]))
    )
    assert len(plain_call_result) == 1
    assert plain_call_result[0].id == plain_call.id


def test_calls_query_sort_by_display_name_prioritized(client):
    """Test that sorting by trace_name prioritizes display_name over op_name when op_names are identical."""
    import uuid

    # Use a unique test ID to identify these calls
    test_id = str(uuid.uuid4())
    op_name = "same_op_name"  # Use the same op_name for all calls

    # First call with display_name "C" (should be last in sort)
    c_call = client.create_call(op_name, {"test_id": test_id})
    c_call.set_display_name("C-display")
    client.finish_call(c_call, "result")

    # Second call with display_name "A" (should be first in sort)
    a_call = client.create_call(op_name, {"test_id": test_id})
    a_call.set_display_name("A-display")
    client.finish_call(a_call, "result")

    # Third call with display_name "B" (should be middle in sort)
    b_call = client.create_call(op_name, {"test_id": test_id})
    b_call.set_display_name("B-display")
    client.finish_call(b_call, "result")

    # Flush to make sure all calls are committed
    client.flush()

    # Query calls and sort by trace_name (ascending)
    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}}
    )
    calls = client.get_calls(
        query=query,
        sort_by=[SortBy(field="summary.weave.trace_name", direction="asc")],
    )
    call_list = list(calls)

    # Verify we have all 3 test calls
    assert len(call_list) == 3

    # Verify they're sorted by display_name (A, B, C) not by op_name
    assert call_list[0].display_name == "A-display"
    assert call_list[1].display_name == "B-display"
    assert call_list[2].display_name == "C-display"

    # Verify they all have the same op_name
    assert call_list[0].op_name == call_list[1].op_name == call_list[2].op_name

    # Sort by trace_name (descending)
    calls = client.get_calls(
        query=query,
        sort_by=[SortBy(field="summary.weave.trace_name", direction="desc")],
    )
    call_list = list(calls)

    # Verify they're sorted by display_name (C, B, A) not by op_name
    assert call_list[0].display_name == "C-display"
    assert call_list[1].display_name == "B-display"
    assert call_list[2].display_name == "A-display"

    # Verify they all have the same op_name
    assert call_list[0].op_name == call_list[1].op_name == call_list[2].op_name


def test_tracing_enabled_context(client):
    """Test that gc.create_call() and gc.finish_call() respect the _tracing_enabled context variable."""
    from weave.trace.call import Call

    @weave.op
    def test_op():
        return "test"

    # Test create_call with tracing enabled
    call = client.create_call(test_op, {})
    assert isinstance(call, Call)
    assert call.op_name.endswith("/test_op:mxdfzr0HPxStQEzDDx7NgSoQXzfxkf86sc6bmUTZaIk")
    assert len(list(client.get_calls())) == 1  # Verify only one call was created

    # Test create_call with tracing disabled
    with tracing_disabled():
        call = client.create_call(test_op, {})
        assert isinstance(
            call, weave.trace.call.NoOpCall
        )  # Should be a NoOpCall instance
        assert (
            len(list(client.get_calls())) == 1
        )  # Verify no additional calls were created

    # Test finish_call with tracing disabled
    with tracing_disabled():
        client.finish_call(call)  # Should not raise any error


def test_calls_query_hardcoded_filter_length_validation(client):
    @weave.op
    def test():
        return {"foo": "bar"}

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Parameter: 'call_ids' request length is greater than max length (1000). Actual length: 1001"
        ),
    ):
        calls = client.get_calls(filter={"call_ids": ["11111"] * 1001})[0]

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Parameter: 'op_names' request length is greater than max length (1000). Actual length: 1001"
        ),
    ):
        calls = client.get_calls(filter={"op_names": ["11111"] * 1001})[0]

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Parameter: 'input_refs' request length is greater than max length (1000). Actual length: 1001"
        ),
    ):
        calls = client.get_calls(filter={"input_refs": ["11111"] * 1001})[0]

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Parameter: 'output_refs' request length is greater than max length (1000). Actual length: 1001"
        ),
    ):
        calls = client.get_calls(filter={"output_refs": ["11111"] * 1001})[0]

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Parameter: 'parent_ids' request length is greater than max length (1000). Actual length: 1001"
        ),
    ):
        calls = client.get_calls(filter={"parent_ids": ["11111"] * 1001})[0]

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Parameter: 'trace_ids' request length is greater than max length (1000). Actual length: 1001"
        ),
    ):
        calls = client.get_calls(filter={"trace_ids": ["11111"] * 1001})[0]


def test_calls_query_datetime_optimization_with_gt_operation(client):
    """Test that datetime optimization works correctly with GT operations on started_at and ended_at fields."""
    if client_is_sqlite(client):
        # TODO(gst): FIX this asap. timestamps aren't actually evaluated
        # correctly in sqlite
        return

    # Use a unique test ID to identify these calls
    test_id = generate_id()

    # Create calls with different timestamps
    # Call 1: Start at t=0, end at t=1
    call1 = client.create_call("x", {"test_id": test_id})
    time.sleep(0.01)  # Ensure different timestamps
    client.finish_call(call1, "result1")

    # Call 2: Start at t=1, end at t=2
    time.sleep(0.01)  # Ensure different timestamps
    call2 = client.create_call("x", {"test_id": test_id})
    time.sleep(0.01)
    client.finish_call(call2, "result2")

    # Call 3: Start at t=2, end at t=3
    time.sleep(0.01)  # Ensure different timestamps
    call3 = client.create_call("x", {"test_id": test_id})
    time.sleep(0.01)
    client.finish_call(call3, "result3")

    # Call 4: Start at t=3, end at t=4
    time.sleep(0.01)  # Ensure different timestamps
    call4 = client.create_call("x", {"test_id": test_id})
    time.sleep(0.01)
    client.finish_call(call4, "result4")

    # Flush to make sure all calls are committed
    client.flush()

    # Get all calls to determine their actual timestamps
    base_query = {
        "$expr": {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]}
    }
    all_calls = list(client.get_calls(query=tsi.Query(**base_query)))
    assert len(all_calls) == 4

    # Sort calls by started_at to get their order
    sorted_calls = sorted(all_calls, key=lambda call: call.started_at)
    call1_ts = sorted_calls[0].started_at.timestamp()
    call2_ts = sorted_calls[1].started_at.timestamp()
    call3_ts = sorted_calls[2].started_at.timestamp()
    call4_ts = sorted_calls[3].started_at.timestamp()

    # Test GT operation on started_at
    # Query for calls started after call2's timestamp
    gt_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$gt": [{"$getField": "started_at"}, {"$literal": call2_ts}]},
                ]
            }
        }
    )
    gt_calls = list(client.get_calls(query=gt_query))
    assert len(gt_calls) == 2  # Should get call3 and call4
    gt_call_ids = {call.id for call in gt_calls}
    assert gt_call_ids == {call3.id, call4.id}

    # Test GT operation on ended_at
    # Query for calls that ended after call2's end timestamp
    gt_ended_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$gt": [
                            {"$getField": "ended_at"},
                            {"$literal": call2.ended_at.timestamp()},
                        ]
                    },
                ]
            }
        }
    )
    gt_ended_calls = list(client.get_calls(query=gt_ended_query))
    assert len(gt_ended_calls) == 2  # Should get call3 and call4
    gt_ended_call_ids = {call.id for call in gt_ended_calls}
    assert gt_ended_call_ids == {call3.id, call4.id}

    # Test GT operation with a timestamp between call2 and call3
    mid_timestamp = (call2_ts + call3_ts) / 2
    mid_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$gt": [{"$getField": "started_at"}, {"$literal": mid_timestamp}]},
                ]
            }
        }
    )
    mid_calls = list(client.get_calls(query=mid_query))
    assert len(mid_calls) == 2  # Should get call3 and call4
    mid_call_ids = {call.id for call in mid_calls}
    assert mid_call_ids == {call3.id, call4.id}

    # Test LT operation on started_at
    lt_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$lt": [{"$getField": "started_at"}, {"$literal": call3_ts}]},
                ]
            }
        }
    )
    lt_calls = list(client.get_calls(query=lt_query))
    assert len(lt_calls) == 2  # Should get call1 and call2
    lt_call_ids = {call.id for call in lt_calls}
    assert lt_call_ids == {call1.id, call2.id}

    # Test GT operation with a timestamp after all calls
    future_timestamp = call4_ts + 1000  # 1000 seconds after the last call
    future_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$gt": [
                            {"$getField": "started_at"},
                            {"$literal": future_timestamp},
                        ]
                    },
                ]
            }
        }
    )
    future_calls = list(client.get_calls(query=future_query))
    assert len(future_calls) == 0  # Should get no calls

    # Test date range query with additional conditions
    date_range_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$gt": [{"$getField": "started_at"}, {"$literal": call2_ts}]},
                    {
                        "$lte": [
                            {"$getField": "started_at"},
                            {"$literal": call4_ts},
                        ]
                    },
                ]
            }
        }
    )
    date_range_calls = list(client.get_calls(query=date_range_query))
    assert len(date_range_calls) == 2  # Should get call3 and call4
    date_range_call_ids = {call.id for call in date_range_calls}
    assert date_range_call_ids == {call3.id, call4.id}

    # Test date range query with ended_at field
    ended_at_range_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$gt": [{"$getField": "ended_at"}, {"$literal": call2_ts}]},
                    {
                        "$lte": [
                            {"$getField": "ended_at"},
                            {"$literal": call4_ts},
                        ]
                    },
                ]
            }
        }
    )
    ended_at_range_calls = list(client.get_calls(query=ended_at_range_query))
    assert len(ended_at_range_calls) == 2  # Should get call2 and call3
    ended_at_range_call_ids = {call.id for call in ended_at_range_calls}
    assert ended_at_range_call_ids == {call2.id, call3.id}

    # Deeply nested datetime query
    nested_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    # greated than or equal to call 1
                    {"$gte": [{"$getField": "started_at"}, {"$literal": call1_ts}]},
                    # not greater than call 4
                    {
                        "$not": [
                            {
                                "$gt": [
                                    {"$getField": "started_at"},
                                    {"$literal": call4_ts},
                                ]
                            }
                        ]
                    },
                    {
                        "$or": [
                            # or greater than call 2 and not greater than call 4
                            {
                                "$and": [
                                    {
                                        "$gt": [
                                            {"$getField": "started_at"},
                                            {"$literal": call2_ts},
                                        ]
                                    },
                                    {
                                        "$not": [
                                            {
                                                "$eq": [
                                                    {"$getField": "started_at"},
                                                    {"$literal": call4_ts},
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            },
                            # or greater than call 2 and not greater than call 3
                            {
                                "$and": [
                                    {
                                        "$gte": [
                                            {"$getField": "started_at"},
                                            {"$literal": call2_ts},
                                        ]
                                    },
                                    {
                                        "$not": [
                                            {
                                                "$gt": [
                                                    {"$getField": "started_at"},
                                                    {"$literal": call3_ts},
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        }
    )
    calls = list(client.get_calls(query=nested_query))
    assert len(calls) == 2
    call_ids = [call.id for call in calls]
    assert call_ids[0] == call2.id
    assert call_ids[1] == call3.id


def _make_call(client, _id):
    trace_id = "trace" + "0" * (32 - len("trace"))
    parent_id = "wo" + "0" * (16 - len("wo"))
    call_res = client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=client._project_id(),
                id=_id,
                op_name="explicit_log_with_custom_ids",
                display_name=f"call_{_id}",
                trace_id=trace_id,
                started_at=datetime.datetime.now(),
                parent_id=None,
                inputs={"test_id": _id},
                attributes={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=client._project_id(),
                id=call_res.id,
                ended_at=datetime.datetime.now(),
                outputs={"hello": "world"},
                summary={"number": "1"},
            )
        )
    )


def test_calls_query_with_non_uuidv7_ids(client):
    """Test that calls query works with non-uuidv7 ids."""
    if client_is_sqlite(client):
        # TODO(gst): FIX this asap. timestamps aren't actually evaluated
        # correctly in sqlite
        return

    # Create a call with an 8 byte hex id
    non_uuidv7_id1 = "1111111111111111"
    non_uuidv7_id2 = "2222222222222222"
    non_uuidv7_id3 = "3333333333333333"
    non_uuidv7_id4 = "4444444444444444"

    # Create calls with timestamps
    call1 = _make_call(client, non_uuidv7_id1)
    time.sleep(0.01)

    call2 = _make_call(client, non_uuidv7_id2)
    time.sleep(0.01)

    call3 = _make_call(client, non_uuidv7_id3)
    time.sleep(0.01)

    call4 = _make_call(client, non_uuidv7_id4)
    time.sleep(0.01)

    client.flush()

    all_calls = list(client.get_calls())
    # Sort calls by started_at to get their order
    sorted_calls = sorted(all_calls, key=lambda call: call.started_at)
    call1_ts = sorted_calls[0].started_at.timestamp()
    call2_ts = sorted_calls[1].started_at.timestamp()
    call3_ts = sorted_calls[2].started_at.timestamp()
    call4_ts = sorted_calls[3].started_at.timestamp()

    # Test basic filtering with $eq
    query = {
        "$expr": {
            "$eq": [
                {"$getField": "started_at"},
                {"$literal": call1_ts},
            ]
        }
    }
    calls = list(client.get_calls(query=query))
    assert len(calls) == 1
    assert calls[0].id == non_uuidv7_id1

    # Test filtering with $gt (greater than)
    query = {
        "$expr": {
            "$gt": [
                {"$getField": "started_at"},
                {"$literal": call1_ts},
            ]
        }
    }
    calls = list(client.get_calls(query=query))
    assert len(calls) == 3
    call_ids = {call.id for call in calls}
    assert call_ids == {non_uuidv7_id2, non_uuidv7_id3, non_uuidv7_id4}

    # Test filtering with $gte (greater than or equal)
    query = {
        "$expr": {
            "$gte": [
                {"$getField": "started_at"},
                {"$literal": call2_ts},
            ]
        }
    }
    calls = list(client.get_calls(query=query))
    assert len(calls) == 3
    call_ids = {call.id for call in calls}
    assert call_ids == {non_uuidv7_id2, non_uuidv7_id3, non_uuidv7_id4}

    # Test nested filtering with mixed operators
    nested_query = {
        "$expr": {
            "$and": [
                {
                    "$or": [
                        {
                            "$eq": [
                                {"$getField": "started_at"},
                                {"$literal": call3_ts},
                            ]
                        },
                        {
                            "$gt": [
                                {"$getField": "started_at"},
                                {"$literal": call3_ts},
                            ]
                        },
                    ]
                }
            ]
        }
    }
    calls = list(client.get_calls(query=nested_query))
    assert len(calls) == 2
    assert calls[0].id == non_uuidv7_id3
    assert calls[1].id == non_uuidv7_id4

    # Add UUIDv7 calls and test mixed filtering
    uuidv7_calls = []
    for i in range(4):
        time.sleep(0.01)
        call = client.create_call("x", {"test_id": f"uuidv7_{i}", "special": "true"})
        client.finish_call(call, "result")
        uuidv7_calls.append(call)

    client.flush()

    # Test filtering with  mixed ID types
    mixed_query = {
        "$expr": {
            "$and": [
                {
                    "$gt": [
                        {"$getField": "started_at"},
                        {"$literal": call2_ts},
                    ]
                },
            ]
        }
    }
    calls = list(client.get_calls(query=mixed_query))
    assert len(calls) == 6
    # call3, call4, uuidv7_calls[1], uuidv7_calls[2], uuidv7_calls[3], uuidv7_calls[4]
    call_ids = [call.id for call in calls]
    assert call_ids[0] == non_uuidv7_id3
    assert call_ids[1] == non_uuidv7_id4
    assert call_ids[2] == uuidv7_calls[0].id
    assert call_ids[3] == uuidv7_calls[1].id
    assert call_ids[4] == uuidv7_calls[2].id
    assert call_ids[5] == uuidv7_calls[3].id

    # test filtering nested, with bad or, and mixed ids
    now = datetime.datetime.now().timestamp()
    mixed_query = {
        "$expr": {
            "$or": [
                {
                    "$or": [
                        {
                            "$gt": [
                                {"$getField": "started_at"},
                                {"$literal": call2_ts},
                            ]
                        },
                        # all hex id calls satisfy this
                        {
                            "$eq": [
                                {"$getField": "summary.number"},
                                {"$literal": "1"},
                            ]
                        },
                    ]
                },
                # all uuidv7 calls satisfy this
                {
                    "$and": [
                        {
                            "$not": [
                                {
                                    "$gt": [
                                        {"$getField": "started_at"},
                                        {"$literal": now},
                                    ]
                                }
                            ]
                        },
                        {
                            "$eq": [
                                {"$getField": "inputs.special"},
                                {"$literal": "true"},
                            ]
                        },
                    ]
                },
            ]
        }
    }
    calls = list(client.get_calls(query=mixed_query))
    assert len(calls) == 8
    call_ids = [call.id for call in calls]
    assert call_ids[0] == non_uuidv7_id1
    assert call_ids[1] == non_uuidv7_id2
    assert call_ids[2] == non_uuidv7_id3
    assert call_ids[3] == non_uuidv7_id4
    assert call_ids[4] == uuidv7_calls[0].id
    assert call_ids[5] == uuidv7_calls[1].id
    assert call_ids[6] == uuidv7_calls[2].id
    assert call_ids[7] == uuidv7_calls[3].id


def test_calls_query_filter_by_root_refs(client):
    @weave.op
    def root_op(x: int):
        return {"n": x, "child": child_op(x)}

    @weave.op
    def child_op(x: int):
        return grandchild_op(x)

    @weave.op
    def grandchild_op(x: int):
        return x + 3

    with call_context.set_call_stack([]):
        root_op(1)
        root_op(2)

    # 2 root_op calls, 2 child_op calls, 2 grandchild_op calls
    all_calls = list(client.get_calls())
    assert len(all_calls) == 6

    # basic trace roots only filter
    calls = client.get_calls(filter={"trace_roots_only": True})
    assert len(calls) == 2  # tests the stats query
    assert op_name_from_call(calls[0]) == "root_op"
    assert op_name_from_call(calls[1]) == "root_op"
    root_op_ref = calls[0].op_name

    # basic trace roots only filter = false, this should be everything
    calls = client.get_calls(filter={"trace_roots_only": False})
    assert len(calls) == 6

    # trace roots only + inputs query
    calls = client.get_calls(
        filter={"trace_roots_only": True},
        query={
            "$expr": {
                "$eq": [
                    {"$convert": {"input": {"$getField": "inputs.x"}, "to": "int"}},
                    {"$literal": 1},
                ]
            }
        },
    )
    assert len(calls) == 1
    assert op_name_from_call(calls[0]) == "root_op"

    # trace roots only + output query
    calls = client.get_calls(
        filter={"trace_roots_only": True},
        query={
            "$expr": {
                "$eq": [
                    {"$convert": {"input": {"$getField": "output.n"}, "to": "int"}},
                    {"$literal": 2},
                ],
            }
        },
    )
    assert len(calls) == 1
    assert op_name_from_call(calls[0]) == "root_op"

    # trace roots only + op filter
    calls = client.get_calls(
        filter={"trace_roots_only": True, "op_names": [root_op_ref]},
    )
    assert len(calls) == 2
    assert op_name_from_call(calls[0]) == "root_op"
    assert op_name_from_call(calls[1]) == "root_op"


def test_filter_calls_by_ref(client):
    obj = {"a": 1}
    ref = client.save(obj, "obj").ref
    ref2 = client.save(obj, "obj2").ref
    ref3 = client.save(obj, "obj3").ref

    @weave.op
    def log_obj(ref: str):
        return {
            "ref2": ref2,
            "ref3": ref3,
        }

    log_obj(ref)

    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].inputs["ref"] == obj
    assert calls[0].output["ref2"] == obj

    # now query by filtering for input ref
    calls = client.get_calls(filter={"input_refs": [ref.uri()]})
    assert len(calls) == 1
    assert calls[0].inputs["ref"] == obj
    assert calls[0].output["ref2"] == obj

    # now query by filtering for output ref
    calls = client.get_calls(filter={"output_refs": [ref2.uri()]})
    assert len(calls) == 1
    assert calls[0].inputs["ref"] == obj
    assert calls[0].output["ref2"] == obj

    # filter by both input and output ref
    calls = client.get_calls(
        filter={"input_refs": [ref.uri()], "output_refs": [ref2.uri()]}
    )
    assert len(calls) == 1
    assert calls[0].inputs["ref"] == obj
    assert calls[0].output["ref2"] == obj

    # filter by two output refs
    calls = client.get_calls(filter={"output_refs": [ref2.uri(), ref3.uri()]})
    assert len(calls) == 1
    assert calls[0].inputs["ref"] == obj
    assert calls[0].output["ref2"] == obj
    assert calls[0].output["ref3"] == obj

    # filter by the wrong ref
    calls = client.get_calls(filter={"input_refs": [ref2.uri()]})
    assert len(calls) == 0

    # filter by the wrong ref
    calls = client.get_calls(filter={"output_refs": [ref.uri()]})
    assert len(calls) == 0

    # filter by duplicate refs
    calls = client.get_calls(filter={"input_refs": [ref.uri(), ref.uri()]})
    assert len(calls) == 1
    assert calls[0].inputs["ref"] == obj
    assert calls[0].output["ref2"] == obj

    # filter by empty refs, this is ambiguously defined, currently we treat
    # this as "no filter"
    calls = client.get_calls(filter={"input_refs": [], "output_refs": []})
    assert len(calls) == 1


def test_files_stats(client):
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")

    f_bytes = b"0" * 10000005
    client.server.file_create(
        FileCreateReq(project_id="shawn/test-project", name="my-file", content=f_bytes)
    )
    read_res = client.server.files_stats(FilesStatsReq(project_id="shawn/test-project"))

    assert read_res.total_size_bytes == 10000005


def test_no_400_on_invalid_artifact_url(client):
    @weave.op
    def test() -> str:
        # This url is too long, should be wandb-artifact:///entity/project/name:version
        return "wandb-artifact:///entity/project/toxic-extra-path/artifact:latest"

    _, call = test.call()
    id = call.id
    server_call = client.get_call(id)
    assert server_call.id == id


def test_no_400_on_invalid_refs(client):
    @weave.op
    def test() -> str:
        # This ref is too long, should be weave:///entity/project/object/name:version
        return "weave:///entity/project/object/toxic-extra-path/object:latest"

    _, call = test.call()
    id = call.id
    server_call = client.get_call(id)
    assert server_call.id == id


def test_get_evaluation(client, make_evals):
    ref, _ = make_evals
    ev = client.get_evaluation(ref.uri())
    assert isinstance(ev, Evaluation)
    assert ev.ref.uri() == ref.uri()


def test_get_evaluations(client, make_evals):
    ref, ref2 = make_evals
    evs = client.get_evaluations()
    assert len(evs) == 2
    assert isinstance(evs[0], Evaluation)
    assert isinstance(evs[1], Evaluation)

    assert evs[0].ref.uri() == ref.uri()
    assert evs[0].dataset.rows[0] == {"dataset_id": "def"}

    assert evs[1].ref.uri() == ref2.uri()
    assert evs[1].dataset.rows[0] == {"dataset_id": "jkl"}


def test_feedback_batching(network_proxy_client):
    """Test that feedback batching works correctly when enabled."""
    # Set up advanced client that uses the RemoteHttpTraceServer handler
    # with batching
    basic_client, remote_client, records = network_proxy_client
    client = TestOnlyFlushingWeaveClient(
        entity=basic_client.entity,
        project=basic_client.project,
        server=remote_client,
        ensure_project_exists=False,
    )
    # Disably autoflush so we can manually control
    client.set_autoflush(False)

    # Create a test call to add feedback to
    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    result = test_op(5)
    client.flush()

    test_call = client.get_calls()[0]
    client.server.attribute_access_log = []

    feedback_items = []
    start = time.time()
    for i in range(10):
        id = test_call.feedback.add(
            feedback_type=f"test_feedback_{i}",
            payload={"score": i, "note": f"Test feedback {i}"},
        )
        assert id is not None
        feedback_items.append(id)

    # make sure we aren't actually waiting for 10 feedbacks, should be quick
    assert time.time() - start < 0.5, "Feedback creation took too long"
    assert client.server.get_feedback_processor() is not None

    # Flush to ensure all feedback is processed
    client.flush()

    log = client.server.attribute_access_log
    feedback_creates = [l for l in log if l == "feedback_create"]

    assert_err = f"Expected 0 feedback creates, got {len(feedback_creates)}"
    assert len(feedback_creates) == 0, assert_err

    # Query feedback to verify all items were created
    all_feedback = list(test_call.feedback)
    created_feedback = [
        f for f in all_feedback if f.feedback_type.startswith("test_feedback_")
    ]
    assert len(created_feedback) == 10

    # Verify the feedback content
    for i, feedback in enumerate(
        sorted(created_feedback, key=lambda x: x.feedback_type)
    ):
        assert feedback.id in feedback_items, (
            f"Feedback {i} not found in feedback_items"
        )
        assert feedback.feedback_type == f"test_feedback_{i}"
        assert feedback.payload["score"] == i
        assert feedback.payload["note"] == f"Test feedback {i}"


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("use_parallel_table_upload", [False, True])
def test_parallel_table_uploads_digest_consistency(
    client, monkeypatch, use_parallel_table_upload
):
    """Test parallel table uploads are consistent with one shot uploads."""
    # Set the parallel table upload setting for this test
    test_settings = settings.UserSettings(
        use_parallel_table_upload=use_parallel_table_upload
    )
    settings.parse_and_apply_settings(test_settings)

    # Set up the mock before creating the client
    # We'll use a mutable container to control the chunk size dynamically
    current_chunk_size = [table_upload_chunking.TARGET_CHUNK_BYTES]
    original_table_chunk_manager = table_upload_chunking.TableChunkManager

    class MockTableChunkManager(original_table_chunk_manager):
        def __init__(self, max_workers=None, target_chunk_bytes=None):
            super().__init__(
                max_workers=max_workers or table_upload_chunking.MAX_CONCURRENT_CHUNKS,
                target_chunk_bytes=current_chunk_size[0],  # Use the dynamic value
            )

    # Apply the mock before creating the client
    monkeypatch.setattr(
        table_upload_chunking, "TableChunkManager", MockTableChunkManager
    )

    # Create large rows that will trigger chunking behavior
    # Use 500KB per row with 3 rows = ~1.5MB total, much more efficient for testing
    large_row_size = 500 * 1024  # 500KB per row (reduced from 12MB for performance)
    large_data = "x" * large_row_size

    # Create table with 3 large rows in order [1, 2, 3]
    table1_rows = [
        {"id": 1, "data": large_data + "_1", "order": "first"},
        {"id": 2, "data": large_data + "_2", "order": "second"},
        {"id": 3, "data": large_data + "_3", "order": "third"},
    ]

    # Use client.save() with Table object to trigger _save_table chunking logic
    table1 = weave_client.Table(table1_rows)
    saved_table1 = client.save(table1, "test-table-1")

    # Get the table reference from the saved table
    table1_ref = saved_table1.table_ref

    # Get the digest information from the saved table
    table1_res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=table1_ref.digest)
    )
    digest1 = table1_ref.digest
    row_digests1 = [row.digest for row in table1_res.rows]

    # Create table with same rows but scrambled order [3, 1, 2]
    table2_rows = [
        {"id": 3, "data": large_data + "_3", "order": "third"},
        {"id": 1, "data": large_data + "_1", "order": "first"},
        {"id": 2, "data": large_data + "_2", "order": "second"},
    ]

    # Use client.save() with Table object to trigger _save_table chunking logic
    table2 = weave_client.Table(table2_rows)
    saved_table2 = client.save(table2, "test-table-2")

    # Get the table reference from the saved table
    table2_ref = saved_table2.table_ref

    # Get the digest information from the saved table
    table2_res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=table2_ref.digest)
    )
    digest2 = table2_ref.digest
    row_digests2 = [row.digest for row in table2_res.rows]

    # Now switch to smaller chunk size to force more parallel uploads
    # This will force chunking since each row is 500KB and chunk will be 300KB
    small_chunk_size = 300 * 1024  # 300KB (smaller than our 500KB rows)

    # Switch to the smaller chunk size
    current_chunk_size[0] = small_chunk_size

    # Create the same tables again with the smaller chunk size
    # This should trigger parallel uploads since each row is larger than the chunk size

    # Table 3: [1, 2, 3] with small chunk size
    table3 = weave_client.Table(table1_rows)
    saved_table3 = client.save(table3, "test-table-3")

    # Get the table reference from the saved table
    table3_ref = saved_table3.table_ref

    # Get the digest information from the saved table
    table3_res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=table3_ref.digest)
    )
    digest3 = table3_ref.digest
    row_digests3 = [row.digest for row in table3_res.rows]

    # Table 4: [3, 1, 2] with small chunk size
    table4 = weave_client.Table(table2_rows)
    saved_table4 = client.save(table4, "test-table-4")

    # Get the table reference from the saved table
    table4_ref = saved_table4.table_ref

    # Get the digest information from the saved table
    table4_res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=table4_ref.digest)
    )
    digest4 = table4_ref.digest
    row_digests4 = [row.digest for row in table4_res.rows]

    # Verify that digests are consistent:
    # - digest1 and digest3 should be the same (same row order, different chunking)
    # - digest2 and digest4 should be the same (same row order, different chunking)
    # - digest1 and digest2 should be different (different row order)
    # - digest3 and digest4 should be different (different row order)

    assert digest1 == digest3, (
        f"Digests should be same for same row order: {digest1} vs {digest3}"
    )
    assert digest2 == digest4, (
        f"Digests should be same for same row order: {digest2} vs {digest4}"
    )
    assert digest1 != digest2, (
        f"Digests should be different for different row order: {digest1} vs {digest2}"
    )
    assert digest3 != digest4, (
        f"Digests should be different for different row order: {digest3} vs {digest4}"
    )

    # Verify row digests are also consistent
    assert row_digests1 == row_digests3, "Row digests should be same for same row order"
    assert row_digests2 == row_digests4, "Row digests should be same for same row order"
    assert row_digests1 != row_digests2, (
        "Row digests should be different for different row order"
    )

    # Verify that chunking actually happened by checking the access log
    access_log = client.server.attribute_access_log

    # Look for chunking-related method calls
    table_create_calls = [call for call in access_log if "table_create" in call]
    table_create_from_digests_calls = [
        call for call in access_log if "table_create_from_digests" in call
    ]
    # Test with smaller chunk size to verify more aggressive chunking
    # Set a very small chunk size to force chunking even on smaller data
    test_chunk_size = 100 * 1024  # 100KB (much smaller than our 500KB rows)
    current_chunk_size[0] = test_chunk_size

    # Create another table with the aggressive chunking settings
    table5 = weave_client.Table(table1_rows)
    saved_table5 = client.save(table5, "test-table-5")

    # Verify it was saved successfully
    assert saved_table5.table_ref is not None


def test_table_create_from_digests(network_proxy_client):
    """Test that table_create_from_digests works correctly to merge existing row digests."""
    basic_client, remote_client, records = network_proxy_client
    client = TestOnlyFlushingWeaveClient(
        entity=basic_client.entity,
        project=basic_client.project,
        server=remote_client,
        ensure_project_exists=False,
    )

    # First, create some individual rows to get their digests
    rows = [
        {"id": 1, "name": "Alice", "value": 100},
        {"id": 2, "name": "Bob", "value": 200},
        {"id": 3, "name": "Charlie", "value": 300},
    ]

    # Create a table with these rows to get the row digests
    table_res = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=rows,
            )
        )
    )

    original_digest = table_res.digest
    row_digests = table_res.row_digests

    # Now create a new table using the same row digests
    from_digests_res = client.server.table_create_from_digests(
        tsi.TableCreateFromDigestsReq(
            project_id=client._project_id(),
            row_digests=row_digests,
        )
    )

    # The digest should be the same since we're using the same rows
    assert from_digests_res.digest == original_digest, (
        f"Digests should match: {from_digests_res.digest} vs {original_digest}"
    )

    more_rows = [
        {"id": 4, "name": "Dave", "value": 400},
        {"id": 5, "name": "Eve", "value": 500},
        {"id": 6, "name": "Frank", "value": 600},
    ]

    more_table_res = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=more_rows,
            )
        )
    )

    combined_digests = row_digests + more_table_res.row_digests

    # Test with a different order of row digests - should produce different digest
    combined_res = client.server.table_create_from_digests(
        tsi.TableCreateFromDigestsReq(
            project_id=client._project_id(),
            row_digests=combined_digests,
        )
    )

    # now get the new table
    new_table_res = basic_client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=combined_res.digest,
        )
    )
    assert len(new_table_res.rows) == 6
    new_table_rows = [row.val for row in new_table_res.rows]
    assert new_table_rows == [
        {"id": 1, "name": "Alice", "value": 100},
        {"id": 2, "name": "Bob", "value": 200},
        {"id": 3, "name": "Charlie", "value": 300},
        {"id": 4, "name": "Dave", "value": 400},
        {"id": 5, "name": "Eve", "value": 500},
        {"id": 6, "name": "Frank", "value": 600},
    ]

    # Test with a different order of row digests - should produce different digest
    shuffled_digests = [row_digests[2], row_digests[0], row_digests[1]]  # [3, 1, 2]
    shuffled_res = client.server.table_create_from_digests(
        tsi.TableCreateFromDigestsReq(
            project_id=client._project_id(),
            row_digests=shuffled_digests,
        )
    )

    # Different order should produce different digest
    assert shuffled_res.digest != original_digest, (
        f"Different row order should produce different digest: {shuffled_res.digest} vs {original_digest}"
    )


def test_calls_query_with_wb_run_id_not_null(client, monkeypatch):
    """Test optimized stats query for wb_run_id not null."""
    mock_run_id = f"{client._project_id()}/test_run_123"
    monkeypatch.setattr(
        weave_client,
        "get_global_wb_run_context",
        lambda: WandbRunContext(run_id="test_run_123", step=0),
    )

    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    test_op(5)
    client.flush()

    calls = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    ).calls
    assert len(calls) == 1
    assert calls[0].wb_run_id == mock_run_id


def test_get_calls_columns_wb_run_id(client, monkeypatch):
    # Step 1: Mock wandb run context so a deterministic wb_run_id is attached to the call.
    mock_run_id = f"{client._project_id()}/test_run_456"
    monkeypatch.setattr(
        weave_client,
        "get_global_wb_run_context",
        lambda: WandbRunContext(run_id="test_run_456", step=7),
    )

    # Step 2: Create a traced call and flush so it can be queried.
    @weave.op
    def test_op(x: int) -> int:
        return x * 3

    _, call = test_op.call(2)
    client.flush()

    # Step 3: Request only the wb_run_id column through client.get_calls.
    calls = list(
        client.get_calls(
            columns=["wb_run_id"],
            filter=tsi.CallsFilter(call_ids=[call.id]),
        )
    )

    assert len(calls) == 1
    assert hasattr(calls[0], "wb_run_id")
    assert calls[0].wb_run_id == mock_run_id

    # Step 4: Query via optimized server path (limit=1 + query expression) and
    # verify wb_run_id is still available.
    query = tsi.Query(
        **{
            "$expr": {
                "$not": [{"$eq": [{"$getField": "wb_run_id"}, {"$literal": None}]}]
            }
        }
    )
    calls = list(
        client.server.calls_query(
            tsi.CallsQueryReq(project_id=client._project_id(), query=query, limit=1)
        ).calls
    )

    assert len(calls) == 1
    assert calls[0].wb_run_id == mock_run_id


def test_calls_query_with_dotted_field_keys(client):
    """Test querying calls with nested field keys containing dots."""
    test_id = str(uuid.uuid4())
    nested1 = {
        "double.nested": "hello",
        "triple.nested.dot": "world",
    }
    nested2 = {
        "double.nested": "goodbye",
        "triple.nested.dot": "universe",
    }

    @weave.op
    def log_nested_output(test_id: str, variant: str):
        return nested1 if variant == "nested1" else nested2

    @weave.op
    def log_nested_input(test_id: str, nested: dict):
        return None

    # Create calls with nested outputs and inputs
    log_nested_output(test_id, "nested1")
    log_nested_output(test_id, "nested2")
    log_nested_input(test_id, nested1)
    log_nested_input(test_id, nested2)

    client.flush()

    test_cases = [
        {
            "name": "output with double.nested field (eq)",
            "field": "output.double\\.nested",  # Escaped  dot in the key name
            "operator": "$eq",
            "value": "hello",
            "expected_count": 1,
            "assertions": lambda calls: [
                calls[0].output["double.nested"] == "hello",
                calls[0].output["triple.nested.dot"] == "world",
            ],
        },
        {
            "name": "output with triple.nested.dot field (eq)",
            "field": "output.triple\\.nested\\.dot",
            "operator": "$eq",
            "value": "world",
            "expected_count": 1,
            "assertions": lambda calls: [
                calls[0].output["triple.nested.dot"] == "world",
            ],
        },
        {
            "name": "input with double.nested field (eq)",
            "field": "inputs.nested.double\\.nested",
            "operator": "$eq",
            "value": "goodbye",
            "expected_count": 1,
            "assertions": lambda calls: [
                calls[0].inputs["nested"]["double.nested"] == "goodbye",
            ],
        },
        {
            "name": "input with triple.nested.dot field (eq)",
            "field": "inputs.nested.triple\\.nested\\.dot",
            "operator": "$eq",
            "value": "universe",
            "expected_count": 1,
            "assertions": lambda calls: [
                calls[0].inputs["nested"]["triple.nested.dot"] == "universe",
            ],
        },
        {
            "name": "output with double.nested field (contains)",
            "field": "output.double\\.nested",
            "operator": "$contains",
            "value": "good",
            "expected_count": 1,
            "assertions": lambda calls: [
                "good" in calls[0].output["double.nested"],
            ],
        },
    ]

    # Run all test cases
    for test_case in test_cases:
        # Build query based on operator
        if test_case["operator"] == "$contains":
            condition = {
                "$contains": {
                    "input": {"$getField": test_case["field"]},
                    "substr": {"$literal": test_case["value"]},
                }
            }
        else:
            condition = {
                test_case["operator"]: [
                    {"$getField": test_case["field"]},
                    {"$literal": test_case["value"]},
                ]
            }

        query = tsi.Query(
            **{
                "$expr": {
                    "$and": [
                        {
                            "$eq": [
                                {"$getField": "inputs.test_id"},
                                {"$literal": test_id},
                            ]
                        },
                        condition,
                    ]
                }
            }
        )

        calls = list(client.get_calls(query=query))
        assert len(calls) == test_case["expected_count"], (
            f"Test '{test_case['name']}' failed: expected {test_case['expected_count']} calls, got {len(calls)}"
        )

        # Run assertions
        assertions = test_case["assertions"](calls)
        assert all(assertions), f"Test '{test_case['name']}' failed assertions"

    # Test OR query with multiple dotted fields (with escaped dots)
    or_query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$or": [
                            {
                                "$eq": [
                                    {"$getField": "output.double\\.nested"},
                                    {"$literal": "hello"},
                                ]
                            },
                            {
                                "$eq": [
                                    {"$getField": "output.triple\\.nested\\.dot"},
                                    {"$literal": "universe"},
                                ]
                            },
                        ]
                    },
                ]
            }
        }
    )
    calls = list(client.get_calls(query=or_query))
    assert len(calls) == 2
    outputs = [call.output for call in calls]
    assert any(o.get("double.nested") == "hello" for o in outputs)
    assert any(o.get("triple.nested.dot") == "universe" for o in outputs)


def test_evaluate_with_llm_completion_model_and_prompt_template_vars(client):
    """Test that LLMStructuredCompletionModel correctly passes prompt and template_vars in evaluation context.

    This test verifies that:
    1. A MessagesPrompt with template variables can be created and published
    2. An LLMStructuredCompletionModel can reference the prompt
    3. When used in evaluation, the model correctly prepares requests with prompt and template_vars
    4. The template variables are correctly passed through the predict() method
    """
    # Create and publish a MessagesPrompt with template variables
    messages_prompt = MessagesPrompt(
        messages=[
            {
                "role": "system",
                "content": "You are {assistant_name}, answering questions about {topic}.",
            },
            {"role": "user", "content": "{question}"},
        ]
    )
    prompt_ref = weave.publish(messages_prompt, name="eval_test_prompt")

    # Create an LLMStructuredCompletionModel with the prompt reference
    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4o-mini",
        default_params=LLMStructuredCompletionModelDefaultParams(
            prompt=prompt_ref.uri(),
            temperature=0.7,
            max_tokens=50,
            response_format="text",
        ),
    )

    # Verify that the model correctly prepares completion requests with prompt and template_vars
    # This tests the core functionality without requiring actual LLM API calls
    req = model.prepare_completion_request(
        project_id=client._project_id(),
        user_input=[],
        config=None,
        assistant_name="MathBot",
        topic="mathematics",
        question="What is 2+2?",
    )

    # Verify the request has prompt reference and template_vars
    assert req.inputs.prompt == prompt_ref.uri(), (
        "Request should include prompt reference"
    )
    assert req.inputs.template_vars == {
        "assistant_name": "MathBot",
        "topic": "mathematics",
        "question": "What is 2+2?",
    }, "Request should include template_vars"

    # Verify messages are empty (prompt resolution happens in completions endpoint)
    assert req.inputs.messages == [], "Messages should be empty when using prompt"

    # Verify other params are set
    assert req.inputs.temperature == 0.7
    assert req.inputs.max_tokens == 50

    # Test with additional user_input messages
    req_with_input = model.prepare_completion_request(
        project_id=client._project_id(),
        user_input=[{"role": "user", "content": "Additional context"}],
        config=None,
        assistant_name="MathBot",
        topic="mathematics",
        question="What is 2+2?",
    )

    # Should still have prompt and template_vars
    assert req_with_input.inputs.prompt == prompt_ref.uri()
    assert req_with_input.inputs.template_vars == {
        "assistant_name": "MathBot",
        "topic": "mathematics",
        "question": "What is 2+2?",
    }

    # Should have user_input messages
    assert req_with_input.inputs.messages == [
        {"role": "user", "content": "Additional context"}
    ]
