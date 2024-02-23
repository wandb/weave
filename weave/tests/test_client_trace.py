import datetime
import typing

from pydantic import BaseModel
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


def test_graph_call_ordering(trace_client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    for i in range(10):
        my_op(i)

    runs = trace_client.runs()
    assert len(runs) == 10

    # We want to preserve insert order
    assert [run._call.inputs["a"] for run in runs] == list(range(10))



class OpCallSummary(BaseModel):
    op: typing.Callable
    num_calls: int = 0


def simple_line_call_bootstrap() -> typing.Dict[str, OpCallSummary]:
    @weave.op()
    def adder(a):
        return a + a

    adder_v0 = adder

    @weave.op()
    def adder(a, b):
        return a + b

    @weave.op()
    def subtractor(a, b):
        return a - b

    @weave.op()
    def multiplier(a, b):
        return a * b

    @weave.op()
    def liner(m, b, x):
        return adder(multiplier(m, x), b)

    result: typing.Dict[str, OpCallSummary] = {}
    result["adder_v0"] = OpCallSummary(op=adder_v0)
    result["adder"] = OpCallSummary(op=adder)
    result["subtractor"] = OpCallSummary(op=subtractor)
    result["multiplier"] = OpCallSummary(op=multiplier)
    result["liner"] = OpCallSummary(op=liner)

    # Call each op a distinct number of time (allows for easier assertions later)
    num_calls = 1
    for i in range(num_calls):
        adder_v0(i)
    result["adder_v0"].num_calls += num_calls

    num_calls = 2
    for i in range(num_calls):
        adder(i, i)
    result["adder"].num_calls += num_calls

    num_calls = 3
    for i in range(num_calls):
        subtractor(i, i)
    result["subtractor"].num_calls += num_calls

    num_calls = 4
    for i in range(num_calls):
        multiplier(i, i)
    result["multiplier"].num_calls += num_calls

    num_calls = 5
    for i in range(num_calls):
        liner(i, i, i)
    result["liner"].num_calls += num_calls
    result["adder"].num_calls += num_calls
    result["multiplier"].num_calls += num_calls

    return result


def ref_str(op):
    return str(weave.obj_ref(op))


def test_trace_call_query_query_filter_op_version_refs(trace_client):
    call_spec = simple_line_call_bootstrap()

    # This is just a string representation of the ref
    # this only reason we are doing this assertion is to make sure the
    # manually constructed wildcard string is correct
    adder_ref_str = f"wandb-trace:///{trace_client.entity}/{trace_client.project}/op/op-adder:22eec6273f8becbf7b518205469f4453"
    assert adder_ref_str == ref_str(call_spec["adder"].op)
    wildcard_adder_ref_str = (
        f"wandb-trace:///{trace_client.entity}/{trace_client.project}/op/op-adder:*"
    )

    total_calls = sum([op_call.num_calls for op_call in call_spec.values()])

    for op_version_refs, exp_count in [
        # Test the None case
        (None, total_calls),
        # Test the empty list case
        ([], total_calls),
        # Base case of most recent version of adder
        ([ref_str(call_spec["adder"].op)], call_spec["adder"].num_calls),
        # Base case of non-recent version of adder
        ([ref_str(call_spec["adder_v0"].op)], call_spec["adder_v0"].num_calls),
        # more than one op
        (
            [ref_str(call_spec["adder"].op), ref_str(call_spec["subtractor"].op)],
            call_spec["adder"].num_calls + call_spec["subtractor"].num_calls,
        ),
        # Test the wildcard case
        (
            [wildcard_adder_ref_str],
            call_spec["adder"].num_calls + call_spec["adder_v0"].num_calls,
        ),
        # Test the wildcard case and specific case
        (
            [wildcard_adder_ref_str, ref_str(call_spec["subtractor"].op)],
            call_spec["adder"].num_calls
            + call_spec["adder_v0"].num_calls
            + call_spec["subtractor"].num_calls,
        ),
    ]:
        res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(op_version_refs=op_version_refs),
            )
        )

        assert len(res.calls) == exp_count


def test_trace_call_query_query_filter_input_object_version_refs(trace_client):
    raise NotImplementedError()


def test_trace_call_query_query_filter_output_object_version_refs(trace_client):
    raise NotImplementedError()


def test_trace_call_query_query_filter_parent_ids(trace_client):
    raise NotImplementedError()


def test_trace_call_query_query_filter_trace_ids(trace_client):
    raise NotImplementedError()


def test_trace_call_query_query_filter_call_ids(trace_client):
    raise NotImplementedError()


def test_trace_call_query_query_filter_trace_roots_only(trace_client):
    call_spec = simple_line_call_bootstrap()

    for trace_roots_only, exp_count in [
        # Test the None case
        (None, num_calls),
        # Test the empty list case
        (True, num_calls),
        # Base case of most recent version of adder
        (False, num_calls),
    ]:
        res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(op_version_refs=op_version_refs),
            )
        )

        assert len(res.calls) == exp_count
