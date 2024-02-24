import datetime
import typing

from pydantic import BaseModel
import weave
from ..trace_server.trace_server_interface_util import (
    TRACE_REF_SCHEME,
    extract_refs_from_values,
)
from ..trace_server import trace_server_interface as tsi
from ..trace_server.graph_client_trace import GraphClientTrace


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


def test_trace_server_call_start_and_end(clickhouse_trace_server):
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
        ),
        "end_datetime": None,
        "exception": None,
        "attributes": {"_keys": ["a"], "a": 5},
        "inputs": {"_keys": ["b"], "b": 5},
        "outputs": None,
        "summary": None,
    }

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
        ),
        "end_datetime": datetime.datetime.fromisoformat(
            end.end_datetime.isoformat(timespec="milliseconds")
        ),
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


class OpCallSpec(BaseModel):
    call_summaries: typing.Dict[str, OpCallSummary]
    total_calls: int
    root_calls: int


def simple_line_call_bootstrap() -> OpCallSpec:
    @weave.type()
    class Number:
        value: int

    @weave.op()
    def adder(a: Number) -> Number:
        return Number(a.value + a.value)

    adder_v0 = adder

    @weave.op()
    def adder(a: Number, b) -> Number:
        return Number(a.value + b)

    @weave.op()
    def subtractor(a: Number, b) -> Number:
        return Number(a.value - b)

    @weave.op()
    def multiplier(
        a: Number, b
    ) -> int:  # intentionally deviant in returning plain int - so that we have a different type
        return a.value * b

    @weave.op()
    def liner(m: Number, b, x) -> Number:
        return adder(Number(multiplier(m, x)), b)

    result: typing.Dict[str, OpCallSummary] = {}
    result["adder_v0"] = OpCallSummary(op=adder_v0)
    result["adder"] = OpCallSummary(op=adder)
    result["subtractor"] = OpCallSummary(op=subtractor)
    result["multiplier"] = OpCallSummary(op=multiplier)
    result["liner"] = OpCallSummary(op=liner)
    root_calls = 0

    # Call each op a distinct number of time (allows for easier assertions later)
    num_calls = 1
    for i in range(num_calls):
        adder_v0(Number(i))
    result["adder_v0"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 2
    for i in range(num_calls):
        adder(Number(i), i)
    result["adder"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 3
    for i in range(num_calls):
        subtractor(Number(i), i)
    result["subtractor"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 4
    for i in range(num_calls):
        multiplier(Number(i), i)
    result["multiplier"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 5
    for i in range(num_calls):
        liner(Number(i), i, i)
    result["liner"].num_calls += num_calls
    result["adder"].num_calls += num_calls
    result["multiplier"].num_calls += num_calls
    root_calls += num_calls

    total_calls = sum([op_call.num_calls for op_call in result.values()])

    return OpCallSpec(
        call_summaries=result, total_calls=total_calls, root_calls=root_calls
    )


def ref_str(op):
    return str(weave.obj_ref(op))


def test_trace_call_query_filter_op_version_refs(trace_client):
    call_spec = simple_line_call_bootstrap()
    call_summaries = call_spec.call_summaries

    # This is just a string representation of the ref
    # this only reason we are doing this assertion is to make sure the
    # manually constructed wildcard string is correct
    assert ref_str(call_summaries["adder"].op).startswith(
        f"wandb-trace:///{trace_client.entity}/{trace_client.project}/op/op-adder:"
    )
    wildcard_adder_ref_str = (
        f"wandb-trace:///{trace_client.entity}/{trace_client.project}/op/op-adder:*/obj"
    )

    for op_version_refs, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Base case of most recent version of adder
        ([ref_str(call_summaries["adder"].op)], call_summaries["adder"].num_calls),
        # Base case of non-recent version of adder
        (
            [ref_str(call_summaries["adder_v0"].op)],
            call_summaries["adder_v0"].num_calls,
        ),
        # more than one op
        (
            [
                ref_str(call_summaries["adder"].op),
                ref_str(call_summaries["subtractor"].op),
            ],
            call_summaries["adder"].num_calls + call_summaries["subtractor"].num_calls,
        ),
        # Test the wildcard case
        (
            [wildcard_adder_ref_str],
            call_summaries["adder"].num_calls + call_summaries["adder_v0"].num_calls,
        ),
        # Test the wildcard case and specific case
        (
            [wildcard_adder_ref_str, ref_str(call_summaries["subtractor"].op)],
            call_summaries["adder"].num_calls
            + call_summaries["adder_v0"].num_calls
            + call_summaries["subtractor"].num_calls,
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


def has_any(list_a: typing.List[str], list_b: typing.List[str]) -> bool:
    return any([a in list_b for a in list_a])


def unique_vals(list_a: typing.List[str]) -> typing.List[str]:
    return list(set(list_a))


def get_all_calls_asserting_finished(
    trace_client: GraphClientTrace, call_spec: OpCallSpec
) -> tsi.CallsQueryRes:
    res = trace_client.trace_server.calls_query(
        tsi.CallsQueryReq(
            entity=trace_client.entity,
            project=trace_client.project,
        )
    )
    assert len(res.calls) == call_spec.total_calls
    assert all([call.end_datetime for call in res.calls])
    return res


def test_trace_call_query_filter_input_object_version_refs(trace_client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(trace_client, call_spec)

    input_object_version_refs = unique_vals(
        [
            ref
            for call in res.calls
            for ref in extract_refs_from_values(call.inputs.values())
        ]
    )
    assert len(input_object_version_refs) > 3

    for input_object_version_refs, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Test single
        (
            input_object_version_refs[:1],
            len(
                [
                    call
                    for call in res.calls
                    if has_any(
                        extract_refs_from_values(call.inputs.values()),
                        input_object_version_refs[:1],
                    )
                ]
            ),
        ),
        # Test multiple
        (
            input_object_version_refs[:3],
            len(
                [
                    call
                    for call in res.calls
                    if has_any(
                        extract_refs_from_values(call.inputs.values()),
                        input_object_version_refs[:3],
                    )
                ]
            ),
        ),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(
                    input_object_version_refs=input_object_version_refs
                ),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_output_object_version_refs(trace_client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(trace_client, call_spec)

    output_object_version_refs = unique_vals(
        [
            ref
            for call in res.calls
            for ref in extract_refs_from_values(call.outputs.values())
        ]
    )
    assert len(output_object_version_refs) > 3

    for output_object_version_refs, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Test single
        (
            output_object_version_refs[:1],
            len(
                [
                    call
                    for call in res.calls
                    if has_any(
                        extract_refs_from_values(call.outputs.values()),
                        output_object_version_refs[:1],
                    )
                ]
            ),
        ),
        # Test multiple
        (
            output_object_version_refs[:3],
            len(
                [
                    call
                    for call in res.calls
                    if has_any(
                        extract_refs_from_values(call.outputs.values()),
                        output_object_version_refs[:3],
                    )
                ]
            ),
        ),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(
                    output_object_version_refs=output_object_version_refs
                ),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_parent_ids(trace_client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(trace_client, call_spec)

    parent_ids = unique_vals(
        [call.parent_id for call in res.calls if call.parent_id is not None]
    )
    assert len(parent_ids) > 3

    for parent_ids, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Test single
        (
            parent_ids[:1],
            len([call for call in res.calls if call.parent_id in parent_ids[:1]]),
        ),
        # Test multiple
        (
            parent_ids[:3],
            len([call for call in res.calls if call.parent_id in parent_ids[:3]]),
        ),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(parent_ids=parent_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_trace_ids(trace_client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(trace_client, call_spec)

    trace_ids = [call.trace_id for call in res.calls]

    for trace_ids, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Test single
        ([trace_ids[0]], 1),
        # Test multiple
        (trace_ids[:3], 3),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(trace_ids=trace_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_call_ids(trace_client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(trace_client, call_spec)

    call_ids = [call.id for call in res.calls]

    for call_ids, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Test single
        ([call_ids[0]], 1),
        # Test multiple
        (call_ids[:3], 3),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(call_ids=call_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_trace_roots_only(trace_client):
    call_spec = simple_line_call_bootstrap()

    for trace_roots_only, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the True
        (True, call_spec.root_calls),
        # Test the False
        (False, call_spec.total_calls),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                filter=tsi._CallsFilter(trace_roots_only=trace_roots_only),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_limit(trace_client):
    call_spec = simple_line_call_bootstrap()

    for limit, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the True
        (1, 1),
        # Test the False
        (10, 10),
    ]:
        inner_res = trace_client.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=trace_client.entity,
                project=trace_client.project,
                limit=limit,
            )
        )

        assert len(inner_res.calls) == exp_count
