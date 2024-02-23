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

# def bootstrap_simple_ops_and_types():
#     @weave.type()
#     class Number:
#         value: int

#     @weave.op()
#     def adder(a: Number, b: int) -> Number:
#         raise NotImplementedError("FAKE BUG")
#         return Number(a.value + b)
    
#     buggy_adder = adder
    
#     @weave.op()
#     def adder(a: Number, b: int) -> Number:
#         raise NotImplementedError("FAKE BUG")
#         return Number(a.value + b)
    
#     @weave.op()
#     def multer(l: Number, r: int) -> Number:
#         return Number(l.value * r)
    
#     @weave.op()
#     def liner(m: Number, b: int, x: int) -> Number:
#         return adder(multer(m, x), b)
    
#     def make_line(m, b, x, x_name):
#         x = Number(x)
#         weave.publish('x', x)
#         m = Number(m)
#         weave.publish(x_name, x)
        
#         return liner(m, b, x)
    
#     return make_line, {
#         "Number": Number,
#         "adder": adder,
#         "multer": multer,
#         "liner": liner,
#     }

# def bootstrap_calls(num_calls=10):
#     make_line, ops = bootstrap_simple_ops_and_types()
    
#     for i in range(num_calls):
#         make_line(i, i, i, f"x{i}")


def test_trace_call_query_query_filter_op_version_refs(trace_client):
    @weave.op()
    def adder(a, b):
        # Intentional bug
        return a + a
    
    buggy_adder = adder
    
    @weave.op()
    def adder(a, b):
        return a + b
    
    @weave.op()
    def subtractor(a, b):
        return a - b
    
    for a in range(3):
        for b in range(3):
            # only do the buggy one if a == b (allows for easier counting in assertions)
            if a == b:
                buggy_adder(a, b) # total of 3 calls 
            adder(a, b) # total of 9 calls
            if a != b:
                subtractor(a, b) # total of 6 calls
    num_bugs = 3
    num_adds = 9
    num_subs = 6
    num_calls = num_bugs + num_adds + num_subs

    trace_interface = trace_client.trace_server

    # Test the None case
    res = trace_interface.calls_query(tsi.CallsQueryReq({
        "entity": trace_client.entity,
        "project": trace_client.project,
        "filter": tsi._CallsFilter({
            "op_version_refs": None
        })
    }))

    assert len(res.calls) == num_calls

    # Test the empty list case
    res = trace_interface.calls_query(tsi.CallsQueryReq({
        "entity": trace_client.entity,
        "project": trace_client.project,
        "filter": tsi._CallsFilter({
            "op_version_refs": []
        })
    }))

    assert len(res.calls) == num_calls
    
    # Test the single op case
    adder_op_version_ref = weave.obj_ref(adder)
    res = trace_interface.calls_query(tsi.CallsQueryReq({
        "entity": trace_client.entity,
        "project": trace_client.project,
        "filter": tsi._CallsFilter({
            "op_version_refs": [adder_op_version_ref]
        })
    }))

    assert len(res.calls) == num_adds

    # Test the wildcard case
    res = trace_interface.calls_query(tsi.CallsQueryReq({
        "entity": trace_client.entity,
        "project": trace_client.project,
        "filter": tsi._CallsFilter({
            "op_version_refs": ["*"] # todo, construct a wildcard ref
        })
    }))
    assert len(res.calls) == num_adds + num_bugs


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
    raise NotImplementedError()

