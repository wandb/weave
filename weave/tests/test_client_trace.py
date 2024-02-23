import datetime
import weave
from ..trace_server.trace_server_interface_util import TRACE_REF_SCHEME
from ..trace_server import trace_server_interface as tsi


def test_simple_op(trace_client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    assert my_op(5) == 6

    op_ref = weave.obj_ref(my_op)
    assert trace_client.ref_is_own(op_ref)
    got_op = weave.storage.get(str(op_ref))

    runs = trace_client.runs()
    assert len(runs) == 1
    fetched_call = runs[0]._call
    assert (
        fetched_call.name
        == f"{TRACE_REF_SCHEME}:///{trace_client.entity}/{trace_client.project}/op/op-my_op:873a064f5e172ac4dfd1b869028d749b"
    )
    assert fetched_call == tsi.CallSchema(
        entity=trace_client.entity,
        project=trace_client.project,
        id=fetched_call.id,
        name=fetched_call.name,
        trace_id=fetched_call.trace_id,
        parent_id=None,
        start_datetime=fetched_call.start_datetime,
        end_datetime=fetched_call.end_datetime,
        exception=None,
        attributes={},
        inputs={"a": 5, "_keys": ["a"]},
        outputs={"_result": 6, "_keys": ["_result"]},
        summary={},
    )


def test_dataset(trace_client):
    from weave.weaveflow import Dataset

    d = Dataset([{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.storage.get(str(ref))
    assert d2.rows == d2.rows


def test_trace_server_call_start(clickhouse_trace_server):
    start = tsi.StartedCallSchemaForInsert(
        entity="test_entity",
        project="test_project",
        id="test_id",
        name="test_name",
        trace_id="test_trace_id",
        parent_id="test_parent_id",
        start_datetime=datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(seconds=1),
        attributes={"a": 5},
        inputs={"b": 5},
    )
    clickhouse_trace_server.call_start(tsi.CallStartReq(start=start))
    end = tsi.EndedCallSchemaForInsert(
        entity="test_entity",
        project="test_project",
        id="test_id",
        end_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
        summary={"c": 5},
        outputs={"d": 5},
    )
    clickhouse_trace_server.call_end(tsi.CallEndReq(end=end))

    res = clickhouse_trace_server.call_read(
        tsi.CallReadReq(
            entity="test_entity",
            project="test_project",
            id="test_id",
        )
    )

    assert res.call.model_dump() == {
        "entity": "test_entity",
        "project": "test_project",
        "id": "test_id",
        "name": "test_name",
        "trace_id": "test_trace_id",
        "parent_id": "test_parent_id",
        "start_datetime": datetime.datetime.fromisoformat(
            start.start_datetime.isoformat(timespec="milliseconds")
        ).replace(tzinfo=None),
        "end_datetime": datetime.datetime.fromisoformat(
            end.end_datetime.isoformat(timespec="milliseconds")
        ).replace(tzinfo=None),
        "exception": None,
        "attributes": {"_keys": ["a"], "a": 5},
        "inputs": {"_keys": ["b"], "b": 5},
        "outputs": {"_keys": ["d"], "d": 5},
        "summary": {"_keys": ["c"], "c": 5},
    }
