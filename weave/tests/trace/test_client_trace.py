import dataclasses
import datetime
import platform
import sys
import time
import typing
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from contextvars import copy_context

import pytest
import wandb
from pydantic import BaseModel, ValidationError

import weave
from weave import Thread, ThreadPoolExecutor, weave_client
from weave.trace.vals import MissingSelfInstanceError
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.trace_server.trace_server_interface_util import (
    TRACE_REF_SCHEME,
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    extract_refs_from_values,
)

pytestmark = pytest.mark.trace


## Hacky interface compatibility helpers

ClientType = weave_client.WeaveClient


def get_client_trace_server(
    client: weave_client.WeaveClient,
) -> tsi.TraceServerInterface:
    return client.server


def get_client_project_id(client: weave_client.WeaveClient) -> str:
    return client._project_id()


## End hacky interface compatibility helpers


def test_simple_op(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    assert my_op(5) == 6

    op_ref = weave_client.get_ref(my_op)
    # assert client._ref_is_own(op_ref)
    got_op = client.get(op_ref)

    calls = list(client.calls())
    assert len(calls) == 1
    fetched_call = calls[0]
    digest = "Zo4OshYu57R00QNlBBGjuiDGyewGYsJ1B69IKXSXYQY"
    expected_name = (
        f"{TRACE_REF_SCHEME}:///{client.entity}/{client.project}/op/my_op:{digest}"
    )
    assert fetched_call == weave_client.Call(
        op_name=expected_name,
        project_id=f"{client.entity}/{client.project}",
        trace_id=fetched_call.trace_id,
        parent_id=None,
        id=fetched_call.id,
        inputs={"a": 5},
        exception=None,
        output=6,
        summary={},
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


def test_dataset(client):
    from weave.flow.dataset import Dataset

    d = Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.ref(ref.uri()).get()
    assert list(d2.rows) == list(d2.rows)


def test_trace_server_call_start_and_end(client):
    call_id = generate_id()
    trace_id = generate_id()
    parent_id = generate_id()
    start = tsi.StartedCallSchemaForInsert(
        project_id=client._project_id(),
        id=call_id,
        op_name="test_name",
        trace_id=trace_id,
        parent_id=parent_id,
        started_at=datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(seconds=1),
        attributes={"a": 5},
        inputs={"b": 5},
    )
    client.server.call_start(tsi.CallStartReq(start=start))

    res = client.server.call_read(
        tsi.CallReadReq(
            project_id=client._project_id(),
            id=call_id,
        )
    )

    exp_started_at = datetime.datetime.fromisoformat(
        start.started_at.isoformat(timespec="milliseconds")
    )

    class FuzzyDateTimeMatcher:
        def __init__(self, dt):
            self.dt = dt

        def __eq__(self, other):
            # Checks within 1ms
            return abs((self.dt - other).total_seconds()) < 0.001

    class MaybeStringMatcher:
        def __init__(self, s):
            self.s = s

        def __eq__(self, other):
            if other is None:
                return True
            return self.s == other

    assert res.call.model_dump() == {
        "project_id": client._project_id(),
        "id": call_id,
        "op_name": "test_name",
        "trace_id": trace_id,
        "parent_id": parent_id,
        "started_at": FuzzyDateTimeMatcher(start.started_at),
        "ended_at": None,
        "exception": None,
        "attributes": {"a": 5},
        "inputs": {"b": 5},
        "output": None,
        "summary": None,
        "wb_user_id": MaybeStringMatcher(client.entity),
        "wb_run_id": None,
        "deleted_at": None,
        "display_name": None,
    }

    end = tsi.EndedCallSchemaForInsert(
        project_id=client._project_id(),
        id=call_id,
        ended_at=datetime.datetime.now(tz=datetime.timezone.utc),
        summary={"c": 5},
        output={"d": 5},
    )
    client.server.call_end(tsi.CallEndReq(end=end))

    res = client.server.call_read(
        tsi.CallReadReq(
            project_id=client._project_id(),
            id=call_id,
        )
    )

    exp_ended_at = datetime.datetime.fromisoformat(
        end.ended_at.isoformat(timespec="milliseconds")
    )

    assert res.call.model_dump() == {
        "project_id": client._project_id(),
        "id": call_id,
        "op_name": "test_name",
        "trace_id": trace_id,
        "parent_id": parent_id,
        "started_at": FuzzyDateTimeMatcher(start.started_at),
        "ended_at": FuzzyDateTimeMatcher(end.ended_at),
        "exception": None,
        "attributes": {"a": 5},
        "inputs": {"b": 5},
        "output": {"d": 5},
        "summary": {"c": 5},
        "wb_user_id": MaybeStringMatcher(client.entity),
        "wb_run_id": None,
        "deleted_at": None,
        "display_name": None,
    }


def test_call_read_not_found(client):
    call_id = generate_id()
    res = client.server.call_read(
        tsi.CallReadReq(
            project_id=client._project_id(),
            id=call_id,
        )
    )
    assert res.call is None


def test_graph_call_ordering(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    for i in range(10):
        my_op(i)

    calls = list(client.calls())
    assert len(calls) == 10

    # We want to preserve insert order
    assert [call.inputs["a"] for call in calls] == list(range(10))


class OpCallSummary(BaseModel):
    op: typing.Callable
    num_calls: int = 0


class OpCallSpec(BaseModel):
    call_summaries: typing.Dict[str, OpCallSummary]
    total_calls: int
    root_calls: int
    run_calls: int


def simple_line_call_bootstrap(init_wandb: bool = False) -> OpCallSpec:
    # @weave.type()
    # class Number:
    #     value: int

    class Number(BaseModel):
        value: int

    @weave.op()
    def adder(a: Number) -> Number:
        return Number(value=a.value + a.value)

    adder_v0 = adder

    @weave.op()
    def adder(a: Number, b) -> Number:
        return Number(value=a.value + b)

    @weave.op()
    def subtractor(a: Number, b) -> Number:
        return Number(value=a.value - b)

    @weave.op()
    def multiplier(
        a: Number, b
    ) -> int:  # intentionally deviant in returning plain int - so that we have a different type
        return a.value * b

    @weave.op()
    def liner(m: Number, b, x) -> Number:
        return adder(Number(value=multiplier(m, x)), b)

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
        adder_v0(Number(value=i))
    result["adder_v0"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 2
    for i in range(num_calls):
        adder(Number(value=i), i)
    result["adder"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 3
    for i in range(num_calls):
        subtractor(Number(value=i), i)
    result["subtractor"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 4
    for i in range(num_calls):
        multiplier(Number(value=i), i)
    result["multiplier"].num_calls += num_calls
    root_calls += num_calls

    num_calls = 5
    run_calls = 0
    if init_wandb:
        run = wandb.init()
    for i in range(num_calls):
        liner(Number(value=i), i, i)
    if init_wandb:
        run.finish()
    result["liner"].num_calls += num_calls
    result["adder"].num_calls += num_calls
    result["multiplier"].num_calls += num_calls
    run_calls += num_calls * 3
    root_calls += num_calls

    total_calls = sum([op_call.num_calls for op_call in result.values()])

    return OpCallSpec(
        call_summaries=result,
        total_calls=total_calls,
        root_calls=root_calls,
        run_calls=run_calls,
    )


def ref_str(op):
    return weave_client.get_ref(op).uri()


def test_trace_call_query_filter_op_version_refs(client):
    call_spec = simple_line_call_bootstrap()
    call_summaries = call_spec.call_summaries

    # This is just a string representation of the ref
    # this only reason we are doing this assertion is to make sure the
    # manually constructed wildcard string is correct
    assert ref_str(call_summaries["adder"].op).startswith(
        f"{TRACE_REF_SCHEME}:///{client.entity}/{client.project}/op/adder:"
    )
    wildcard_adder_ref_str = f"{TRACE_REF_SCHEME}:///{client.entity}/{client.project}/op/adder{WILDCARD_ARTIFACT_VERSION_AND_PATH}"

    for i, (op_version_refs, exp_count) in enumerate(
        [
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
                call_summaries["adder"].num_calls
                + call_summaries["subtractor"].num_calls,
            ),
            # Test the wildcard case
            (
                [wildcard_adder_ref_str],
                call_summaries["adder"].num_calls
                + call_summaries["adder_v0"].num_calls,
            ),
            # Test the wildcard case and specific case
            (
                [wildcard_adder_ref_str, ref_str(call_summaries["subtractor"].op)],
                call_summaries["adder"].num_calls
                + call_summaries["adder_v0"].num_calls
                + call_summaries["subtractor"].num_calls,
            ),
        ]
    ):
        res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(op_names=op_version_refs),
            )
        )
        print(f"TEST CASE [{i}]", op_version_refs, exp_count)

        assert len(res.calls) == exp_count


def has_any(list_a: typing.List[str], list_b: typing.List[str]) -> bool:
    return any([a in list_b for a in list_a])


def unique_vals(list_a: typing.List[str]) -> typing.List[str]:
    return list(set(list_a))


def get_all_calls_asserting_finished(
    client: ClientType, call_spec: OpCallSpec
) -> tsi.CallsQueryRes:
    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
        )
    )
    assert len(res.calls) == call_spec.total_calls
    assert all([call.ended_at for call in res.calls])
    return res


def test_trace_call_query_filter_input_object_version_refs(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

    input_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.inputs)]
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
                        extract_refs_from_values(call.inputs),
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
                        extract_refs_from_values(call.inputs),
                        input_object_version_refs[:3],
                    )
                ]
            ),
        ),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(input_refs=input_object_version_refs),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_output_object_version_refs(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

    output_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.output)]
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
                        extract_refs_from_values(call.output),
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
                        extract_refs_from_values(call.output),
                        output_object_version_refs[:3],
                    )
                ]
            ),
        ),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(output_refs=output_object_version_refs),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_parent_ids(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

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
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(parent_ids=parent_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_trace_ids(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

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
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(trace_ids=trace_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_call_ids(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

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
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(call_ids=call_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_trace_roots_only(client):
    call_spec = simple_line_call_bootstrap()

    for trace_roots_only, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the True
        (True, call_spec.root_calls),
        # Test the False
        (False, call_spec.total_calls),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(trace_roots_only=trace_roots_only),
            )
        )

        assert len(inner_res.calls) == exp_count


@pytest.mark.skip("too slow")
def test_trace_call_query_filter_wb_run_ids(client, user_by_api_key_in_env):
    call_spec = simple_line_call_bootstrap(init_wandb=True)

    res = get_all_calls_asserting_finished(client, call_spec)

    wb_run_ids = list(set([call.wb_run_id for call in res.calls]) - set([None]))

    for wb_run_ids, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test the empty list case
        ([], call_spec.total_calls),
        # Test List (of 1)
        (wb_run_ids, call_spec.run_calls),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(wb_run_ids=wb_run_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_limit(client):
    call_spec = simple_line_call_bootstrap()

    for limit, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test limit of 1
        (1, 1),
        # Test limit of 10
        (10, 10),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                limit=limit,
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_offset(client):
    call_spec = simple_line_call_bootstrap()

    for offset, exp_count in [
        # Test the None case
        (None, call_spec.total_calls),
        # Test offset of 1
        (1, call_spec.total_calls - 1),
        # Test offset of 10
        (10, call_spec.total_calls - 10),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                offset=offset,
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_sort(client):
    @weave.op()
    def basic_op(in_val: dict, delay) -> dict:
        import time

        time.sleep(delay)
        return in_val

    for i in range(3):
        basic_op({"prim": i, "list": [i], "dict": {"inner": i}}, i / 10)

    for first, last, sort_by in [
        (2, 0, [tsi.SortBy(field="started_at", direction="desc")]),
        (2, 0, [tsi.SortBy(field="inputs.in_val.prim", direction="desc")]),
        (2, 0, [tsi.SortBy(field="inputs.in_val.list.0", direction="desc")]),
        (2, 0, [tsi.SortBy(field="inputs.in_val.dict.inner", direction="desc")]),
        (2, 0, [tsi.SortBy(field="output.prim", direction="desc")]),
        (2, 0, [tsi.SortBy(field="output.list.0", direction="desc")]),
        (2, 0, [tsi.SortBy(field="output.dict.inner", direction="desc")]),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=sort_by,
            )
        )

        assert inner_res.calls[0].inputs["in_val"]["prim"] == first
        assert inner_res.calls[2].inputs["in_val"]["prim"] == last


def test_trace_call_sort_with_mixed_types(client):
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # SQLite does not support sorting over mixed types in a column, so we skip this test
        return

    @weave.op()
    def basic_op(in_val: dict) -> dict:
        import time

        time.sleep(1 / 10)
        return in_val

    basic_op({"prim": None})
    basic_op({"not_prim": 1})
    basic_op({"prim": 100})
    basic_op({"prim": 2})
    basic_op({"prim": "b"})
    basic_op({"prim": "a"})

    for direction, seq in [
        ("desc", [100, 2, "b", "a", None, None]),
        (
            "asc",
            [
                2,
                100,
                "a",
                "b",
                None,
                None,
            ],
        ),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[tsi.SortBy(field="inputs.in_val.prim", direction=direction)],
            )
        )

        for i, call in enumerate(inner_res.calls):
            assert call.inputs["in_val"].get("prim") == seq[i]


def client_is_sqlite(client):
    return isinstance(client.server._internal_trace_server, SqliteTraceServer)


def test_trace_call_filter(client):
    is_sqlite = client_is_sqlite(client)

    @weave.op()
    def basic_op(in_val: dict, delay) -> dict:
        return in_val

    for i in range(10):
        basic_op(
            {"prim": i, "list": [i], "dict": {"inner": i}, "str": "str_" + str(i)},
            i / 10,
        )

    # Adding a row of a different type here to make sure we safely exclude it without it messing up other things
    basic_op(
        {
            "prim": "Different Type",
            "list": "Different Type",
            "dict": "Different Type",
            "str": False,
        },
        0.1,
    )

    basic_op("simple_primitive", 0.1)
    basic_op(42, 0.1)

    failed_cases = []
    for count, query in [
        # Base Case - simple True
        (
            13,
            {"$eq": [{"$literal": 1}, {"$literal": 1}]},
        ),
        # Base Case - simple false
        (
            0,
            {"$eq": [{"$literal": 1}, {"$literal": 2}]},
        ),
        # eq
        (
            1,
            {
                "$eq": [
                    {"$literal": 5},
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.prim"},
                            "to": "int",
                        }
                    },
                ]
            },
        ),
        # eq - string
        (
            1,
            {
                "$eq": [
                    {"$literal": "simple_primitive"},
                    {"$getField": "inputs.in_val"},
                ]
            },
        ),
        # eq - string out
        (
            1,
            {"$eq": [{"$literal": "simple_primitive"}, {"$getField": "output"}]},
        ),
        # gt
        (
            4,
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.prim"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
        # gte
        (
            5,
            {
                "$gte": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.prim"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
        # not gt = lte
        (
            6
            + (
                1 if is_sqlite else 0
            ),  # SQLite casting transforms strings to 0, instead of NULL
            {
                "$not": [
                    {
                        "$gt": [
                            {
                                "$convert": {
                                    "input": {"$getField": "inputs.in_val.prim"},
                                    "to": "int",
                                }
                            },
                            {"$literal": 5},
                        ]
                    }
                ]
            },
        ),
        # not gte = lt
        (
            5
            + (
                1 if is_sqlite else 0
            ),  # SQLite casting transforms strings to 0, instead of NULL
            {
                "$not": [
                    {
                        "$gte": [
                            {
                                "$convert": {
                                    "input": {"$getField": "inputs.in_val.prim"},
                                    "to": "int",
                                }
                            },
                            {"$literal": 5},
                        ]
                    }
                ]
            },
        ),
        # like all
        (
            13
            + (
                -2 if is_sqlite else 0
            ),  # SQLite returns NULL for non-existent fields rather than ''.
            {
                "$contains": {
                    "input": {"$getField": "inputs.in_val.str"},
                    "substr": {"$literal": ""},
                }
            },
        ),
        # like select
        (
            10,
            {
                "$contains": {
                    "input": {"$getField": "inputs.in_val.str"},
                    "substr": {"$literal": "str"},
                }
            },
        ),
        (
            0,
            {
                "$contains": {
                    "input": {"$getField": "inputs.in_val.str"},
                    "substr": {"$literal": "STR"},
                }
            },
        ),
        (
            10,
            {
                "$contains": {
                    "input": {"$getField": "inputs.in_val.str"},
                    "substr": {"$literal": "STR"},
                    "case_insensitive": True,
                }
            },
        ),
        # and
        (
            3,
            {
                "$and": [
                    {
                        "$not": [
                            {
                                "$gt": [
                                    {
                                        "$convert": {
                                            "input": {
                                                "$getField": "inputs.in_val.prim"
                                            },
                                            "to": "int",
                                        }
                                    },
                                    {"$literal": 7},
                                ]
                            }
                        ]
                    },
                    {
                        "$gte": [
                            {
                                "$convert": {
                                    "input": {"$getField": "inputs.in_val.prim"},
                                    "to": "int",
                                }
                            },
                            {"$literal": 5},
                        ]
                    },
                ]
            },
        ),
        # or
        (
            5
            + (
                1 if is_sqlite else 0
            ),  # SQLite casting transforms strings to 0, instead of NULL
            {
                "$or": [
                    {
                        "$not": [
                            {
                                "$gt": [
                                    {
                                        "$convert": {
                                            "input": {
                                                "$getField": "inputs.in_val.prim"
                                            },
                                            "to": "int",
                                        }
                                    },
                                    {"$literal": 3},
                                ]
                            }
                        ]
                    },
                    {
                        "$gte": [
                            {
                                "$convert": {
                                    "input": {"$getField": "inputs.in_val.prim"},
                                    "to": "int",
                                }
                            },
                            {"$literal": 9},
                        ]
                    },
                ]
            },
        ),
        # Invalid type - safely return none
        (
            0,
            {
                "$eq": [
                    {"$literal": 5},
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.str"},
                            "to": "int",
                        }
                    },
                ]
            },
        ),
        # Cast across type
        (
            1,
            {
                "$eq": [
                    {"$literal": "5"},
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.prim"},
                            "to": "string",
                        }
                    },
                ]
            },
        ),
        # Different key access
        (
            4,
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {
                                "$getField": "inputs.in_val.list.0"
                            },  # changing this to a dot instead of [0]
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
        (
            4,
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.dict.inner"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
        (
            4,
            {
                "$gt": [
                    {"$convert": {"input": {"$getField": "output.prim"}, "to": "int"}},
                    {"$literal": 5},
                ]
            },
        ),
        (
            4,
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "output.list.0"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
        (
            4,
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "output.dict.inner"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
    ]:
        print(f"TEST CASE [{count}]", query)
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq.model_validate(
                dict(
                    project_id=get_client_project_id(client),
                    query={"$expr": query},
                )
            )
        )

        if len(inner_res.calls) != count:
            failed_cases.append(
                f"(ALL) Query {query} expected {count}, but found {len(inner_res.calls)}"
            )
        inner_res = get_client_trace_server(client).calls_query_stats(
            tsi.CallsQueryStatsReq.model_validate(
                dict(
                    project_id=get_client_project_id(client),
                    query={"$expr": query},
                )
            )
        )

        if inner_res.count != count:
            failed_cases.append(
                f"(Stats) Query {query} expected {count}, but found {inner_res.count}"
            )

    if failed_cases:
        raise AssertionError(
            f"Failed {len(failed_cases)} cases:\n" + "\n".join(failed_cases)
        )


def test_ops_with_default_params(client):
    @weave.op()
    def op_with_default(a: int, b: int = 10) -> int:
        return a + b

    assert op_with_default(1) == 11
    assert op_with_default(1, 5) == 6
    assert op_with_default(1, b=5) == 6
    assert op_with_default(a=1) == 11
    assert op_with_default(a=1, b=5) == 6
    assert op_with_default(b=5, a=1) == 6

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert len(inner_res.calls) == 6
    assert inner_res.calls[0].inputs == {"a": 1, "b": 10}
    assert inner_res.calls[1].inputs == {"a": 1, "b": 5}
    assert inner_res.calls[2].inputs == {"a": 1, "b": 5}
    assert inner_res.calls[3].inputs == {"a": 1, "b": 10}
    assert inner_res.calls[4].inputs == {"a": 1, "b": 5}
    assert inner_res.calls[5].inputs == {"a": 1, "b": 5}


def test_root_type(client):
    class BaseTypeA(weave.Object):
        a: int

    class BaseTypeX(weave.Object):
        x: int

    class BaseTypeB(BaseTypeA):
        b: int

    class BaseTypeC(BaseTypeB):
        c: int

    c = BaseTypeC(a=1, b=2, c=3)
    x = BaseTypeX(x=5)

    ref = weave.publish(x)
    x2 = weave.ref(ref.uri()).get()
    assert x2.x == 5

    ref = weave.publish(c)
    c2 = weave.ref(ref.uri()).get()

    assert c2.a == 1
    assert c2.b == 2
    assert c2.c == 3

    inner_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
        )
    )

    assert len(inner_res.objs) == 2

    inner_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["BaseTypeA"],
            ),
        )
    )

    assert len(inner_res.objs) == 1


def test_attributes_on_ops(client):
    @weave.op()
    def op_with_attrs(a: int, b: int) -> int:
        return a + b

    with weave.attributes({"custom": "attribute"}):
        op_with_attrs(1, 2)

    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            filter=tsi.CallsFilter(op_names=[ref_str(op_with_attrs)]),
        )
    )

    assert len(res.calls) == 1
    assert res.calls[0].attributes == {
        "custom": "attribute",
        "weave": {
            "client_version": weave.version.VERSION,
            "source": "python-sdk",
            "os_name": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "sys_version": sys.version,
        },
    }


def test_dataset_row_type(client):
    d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    with pytest.raises(ValidationError):
        d = weave.Dataset(rows=[])
    with pytest.raises(ValidationError):
        d = weave.Dataset(rows=[{"a": 1}, "a", "b"])
    with pytest.raises(ValidationError):
        d = weave.Dataset(rows=[{"a": 1}, {}])


def test_dataclass_support(client):
    @dataclasses.dataclass
    class MyDataclass:
        val: int

    @weave.op()
    def dataclass_maker(a: MyDataclass, b: MyDataclass) -> MyDataclass:
        return MyDataclass(a.val + b.val)

    a = MyDataclass(1)
    b = MyDataclass(2)
    act = dataclass_maker(a, b)
    exp = MyDataclass(3)
    assert act == exp

    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            filter=tsi.CallsFilter(op_names=[ref_str(dataclass_maker)]),
        )
    )

    exp_ref = weave.publish(exp)
    exp_2 = weave.ref(exp_ref.uri()).get()
    assert exp_2.val == 3

    assert len(res.calls) == 1
    assert res.calls[0].inputs == {
        "a": "weave:///shawn/test-project/object/MyDataclass:qDo5jHFme5xIM1LwgeiXXVxYoGnp4LQ9hulqkX5zunY",
        "b": "weave:///shawn/test-project/object/MyDataclass:We1slmdrWzi2NYSWObBsLybTTNSP4M9zfQbCMf8rQMc",
    }
    assert (
        res.calls[0].output
        == "weave:///shawn/test-project/object/MyDataclass:2exnZIHkq8DyHTbJzhL0m5Ew1XrqIBCstZWilQS6Lpo"
    )


def test_op_retrieval(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    assert my_op(1) == 2
    my_op_ref = weave_client.get_ref(my_op)
    my_op2 = my_op_ref.get()
    assert my_op2(1) == 2


def test_bound_op_retrieval(client):
    class CustomType(weave.Object):
        a: int

        @weave.op()
        def op_with_custom_type(self, v):
            return self.a + v

    obj = CustomType(a=1)
    obj_ref = weave.publish(obj)
    obj2 = obj_ref.get()
    assert obj2.op_with_custom_type(1) == 2

    my_op_ref = weave_client.get_ref(CustomType.op_with_custom_type)
    with pytest.raises(MissingSelfInstanceError):
        my_op2 = my_op_ref.get()

    my_op_ref2 = weave_client.get_ref(obj2.op_with_custom_type)
    with pytest.raises(MissingSelfInstanceError):
        my_op2 = my_op_ref2.get()


@pytest.mark.skip("Not implemented: general bound op designation")
def test_bound_op_retrieval_no_self(client):
    class CustomTypeWithoutSelf(weave.Object):
        a: int

        @weave.op()
        def op_with_custom_type(me, v):
            return me.a + v

    obj = CustomTypeWithoutSelf(a=1)
    obj_ref = weave.publish(obj)
    obj2 = obj_ref.get()
    assert obj2.op_with_custom_type(1) == 2

    my_op_ref = weave_client.get_ref(CustomTypeWithoutSelf.op_with_custom_type)
    with pytest.raises(MissingSelfInstanceError):
        my_op2 = my_op_ref.get()


def test_dataset_row_ref(client):
    d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.ref(ref.uri()).get()

    inner = d2.rows[0]["a"]
    exp_ref = "weave:///shawn/test-project/object/Dataset:0xTDJ6hEmsx8Wg9H75y42bL2WgvW5l4IXjuhHcrMh7A/attr/rows/id/XfhC9dNA5D4taMvhKT4MKN2uce7F56Krsyv4Q6mvVMA/key/a"
    assert inner == 5
    assert inner.ref.uri() == exp_ref
    gotten = weave.ref(exp_ref).get()
    assert gotten == 5


def test_tuple_support(client):
    @weave.op()
    def tuple_maker(a, b):
        return (a, b)

    act = tuple_maker((1, 2), 3)
    exp = ((1, 2), 3)
    assert act == exp

    exp_ref = weave.publish(exp)
    exp_2 = weave.ref(exp_ref.uri()).get()
    assert exp_2 == [[1, 2], 3]

    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            filter=tsi.CallsFilter(op_names=[ref_str(tuple_maker)]),
        )
    )

    assert len(res.calls) == 1
    assert res.calls[0].output == [[1, 2], 3]


def test_namedtuple_support(client):
    @weave.op()
    def tuple_maker(a, b):
        return (a, b)

    Point = namedtuple("Point", ["x", "y"])
    act = tuple_maker(Point(1, 2), 3)
    exp = (Point(1, 2), 3)
    assert act == exp

    exp_ref = weave.publish(exp)
    exp_2 = weave.ref(exp_ref.uri()).get()
    assert exp_2 == [{"x": 1, "y": 2}, 3]

    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            filter=tsi.CallsFilter(op_names=[ref_str(tuple_maker)]),
        )
    )

    assert len(res.calls) == 1
    assert res.calls[0].output == [{"x": 1, "y": 2}, 3]


def test_named_reuse(client):
    import asyncio

    d = weave.Dataset(rows=[{"x": 1}, {"x": 2}])
    d_ref = weave.publish(d, "test_dataset")
    dataset = weave.ref(d_ref.uri()).get()

    @weave.op()
    async def dummy_score(model_output):
        return 1

    class SimpleModel(weave.Model):
        async def predict(self, x):
            return {"answer": "42"}

    model = SimpleModel()

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[dummy_score],
    )
    dataset_ref = dataset.ref
    evaluation_dataset = evaluation.dataset
    eval_dataset_ref = evaluation_dataset.ref
    assert dataset_ref == eval_dataset_ref
    asyncio.run(evaluation.evaluate(model))

    res = get_client_trace_server(client).objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
            filter=tsi.ObjectVersionFilter(
                is_op=False, latest_only=True, base_object_classes=["Dataset"]
            ),
        )
    )

    # There are a lot of additional assertions that could be made here!
    print(res.objs)
    assert len(res.objs) == 1


def test_unknown_input_and_output_types(client):
    class MyUnserializableClassA:
        a_val: float

        def __init__(self, a_val) -> None:
            self.a_val = a_val

    class MyUnserializableClassB:
        b_val: float

        def __init__(self, b_val) -> None:
            self.b_val = b_val

    @weave.op()
    def op_with_unknown_types(
        a: MyUnserializableClassA, b: float
    ) -> MyUnserializableClassB:
        return MyUnserializableClassB(a.a_val + b)

    a = MyUnserializableClassA(3)
    res = op_with_unknown_types(a, 0.14)

    assert res.b_val == 3.14

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert len(inner_res.calls) == 1
    assert inner_res.calls[0].inputs == {
        "a": repr(a),
        "b": 0.14,
    }
    assert inner_res.calls[0].output == repr(res)


def test_unknown_attribute(client):
    class MyUnserializableClass:
        val: int

        def __init__(self, a_val) -> None:
            self.a_val = a_val

    class MySerializableClass(weave.Object):
        obj: MyUnserializableClass

    a_obj = MyUnserializableClass(1)
    a = MySerializableClass(obj=a_obj)
    b_obj = MyUnserializableClass(2)
    b = MySerializableClass(obj=b_obj)

    ref_a = weave.publish(a)
    ref_b = weave.publish(b)

    a2 = weave.ref(ref_a.uri()).get()
    b2 = weave.ref(ref_b.uri()).get()

    assert a2.obj == repr(a_obj)
    assert b2.obj == repr(b_obj)


# Note: this test only works with the `trace_init_client` fixture
def test_ref_get_no_client(trace_init_client):
    trace_client = trace_init_client.client
    data = weave.publish(42)
    data_got = weave.ref(data.uri()).get()
    assert data_got == 42

    # clear the graph client effectively "de-initializing it"
    with _no_graph_client():
        # This patching is required just to make the test path work
        with _patched_default_initializer(trace_client):
            # Now we will try to get the data again
            data_got = weave.ref(data.uri()).get()
            assert data_got == 42


@contextmanager
def _no_graph_client():
    client = weave.client_context.weave_client.get_weave_client()
    weave.client_context.weave_client.set_weave_client_global(None)
    try:
        yield
    finally:
        weave.client_context.weave_client.set_weave_client_global(client)


@contextmanager
def _patched_default_initializer(trace_client: weave_client.WeaveClient):
    from weave import weave_init

    def init_weave_get_server_patched(api_key):
        return trace_client.server

    orig = weave_init.init_weave_get_server
    weave_init.init_weave_get_server = init_weave_get_server_patched

    try:
        yield
    finally:
        weave_init.init_weave_get_server = orig


def test_single_primitive_output(client):
    @weave.op()
    def single_int_output(a: int) -> int:
        return a

    @weave.op()
    def single_bool_output(a: int) -> bool:
        return a == 1

    @weave.op()
    def single_none_output(a: int) -> None:
        return None

    @weave.op()
    def dict_output(a: int, b: bool, c: None) -> dict:
        return {"a": a, "b": b, "c": c}

    a = single_int_output(1)
    b = single_bool_output(1)
    c = single_none_output(1)
    d = dict_output(a, b, c)

    assert isinstance(a, int)
    assert a == 1
    assert isinstance(b, bool)
    assert b == True
    assert isinstance(c, type(None))
    assert c is None
    assert isinstance(d, dict)
    assert isinstance(d["a"], int)
    assert isinstance(d["b"], bool)
    assert isinstance(d["c"], type(None))
    assert d == {"a": 1, "b": True, "c": None}

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert len(inner_res.calls) == 4
    assert inner_res.calls[0].output == 1
    assert inner_res.calls[1].output == True
    assert inner_res.calls[2].output is None
    assert inner_res.calls[3].output == {"a": 1, "b": True, "c": None}


def map_simple(fn, vals):
    return [fn(v) for v in vals]


max_workers = 3


def map_with_threads_no_executor(fn, vals):
    def task_wrapper(v):
        return fn(v)

    threads = []

    for v in vals:
        thread = Thread(target=task_wrapper, args=(v,))
        thread.start()
        threads.append(thread)

        if len(threads) >= max_workers:
            for thread in threads:
                thread.join()
            threads = []

        for thread in threads:
            thread.join()


def map_with_thread_executor(fn, vals):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(fn, vals)


# This is how Langchain executes batches (with a manual context copy)
def map_with_copying_thread_executor(fn, vals):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        contexts = [copy_context() for _ in range(len(vals))]

        def _wrapped_fn(*args):
            return contexts.pop().run(fn, *args)

        executor.map(_wrapped_fn, vals)


# TODO: Make an async version of this
@pytest.mark.flaky(retries=3)  # <-- Flakes in CI
@pytest.mark.parametrize(
    "mapper",
    [
        map_simple,
        map_with_threads_no_executor,
        map_with_thread_executor,
        # map_with_copying_thread_executor, # <-- Flakes in CI
    ],
)
def test_mapped_execution(client, mapper):
    import time

    events = []

    @weave.op()
    def op_a(a: int) -> int:
        events.append("A(S):" + str(a))
        time.sleep(0.3)
        events.append("A(E):" + str(a))
        return a

    @weave.op()
    def op_b(b: int) -> int:
        events.append("B(S):" + str(b))
        time.sleep(0.2)
        res = op_a(b)
        events.append("B(E):" + str(b))
        return res

    @weave.op()
    def op_c(c: int) -> int:
        events.append("C(S):" + str(c))
        time.sleep(0.1)
        res = op_b(c)
        events.append("C(E):" + str(c))
        return res

    @weave.op()
    def op_mapper(vals):
        return mapper(op_c, vals)

    map_vals = list(range(12))
    first_val = map_vals[0]
    last_val = map_vals[-1]
    middle_vals = map_vals[1:-1]
    split = len(middle_vals) // 2
    middle_vals_outer = middle_vals[:split]
    middle_vals_inner = middle_vals[split:]
    op_c(first_val)
    mapper(op_c, middle_vals_outer)
    op_mapper(middle_vals_inner)
    op_c(last_val)

    # Make sure that the events are in the right (or wrong!) order
    sequential_expected_order = []
    for i in map_vals:
        for event in ["S", "E"]:
            order = ["A", "B", "C"]
            if event == "S":
                order = order[::-1]
            for op in order:
                sequential_expected_order.append(f"{op}({event}):{i}")
    if mapper == map_simple:
        assert events == sequential_expected_order

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert len(inner_res.calls) == (len(map_vals) * 3) + 1

    # Now, we want to assert that the calls are in the right topological order - while
    # it is possible that their timestamps are not in order
    # First some helpers:
    roots = [c for c in inner_res.calls if c.parent_id is None]

    def assert_input_of_call(call, input_val):
        assert call.inputs == input_val

    def get_children_of_call(call):
        return [c for c in inner_res.calls if c.parent_id == call.id]

    def assert_valid_trace(root_call, val):
        assert_input_of_call(root_call, {"c": val})
        children = get_children_of_call(root_call)
        assert len(children) == 1
        assert_input_of_call(children[0], {"b": val})
        children = get_children_of_call(children[0])
        assert len(children) == 1
        assert_input_of_call(children[0], {"a": val})

    def assert_valid_batched_trace(root_call):
        val = int(root_call.inputs["c"])
        assert_valid_trace(root_call, val)

    # First, ensure that there are 5 roots
    assert len(roots) == 3 + len(middle_vals_outer)

    # Now we can validate the shape of the calls within their traces.
    # The first and last roots are not batched and therefore deterministic
    # The middle 3 roots are batched and therefore non-deterministic
    root_ndx = 0
    assert_valid_trace(roots[root_ndx], first_val)
    root_ndx += 1
    for outer in middle_vals_outer:
        assert_valid_trace(roots[root_ndx], outer)
        root_ndx += 1

    children = get_children_of_call(roots[root_ndx])
    root_ndx += 1
    assert len(children) == len(middle_vals_inner)
    for child in children:
        assert_valid_batched_trace(child)
    assert_valid_trace(roots[root_ndx], last_val)


def call_structure(calls):
    parent_to_children_map = defaultdict(list)
    roots = []
    for call in calls:
        parent_to_children_map[call.parent_id].append(call.id)
        if call.parent_id is None:
            roots.append(call.id)

    found_structure = {}

    def build_structure(parent_id):
        if parent_id is None:
            return {}
        children = parent_to_children_map[parent_id]
        return {child: build_structure(child) for child in children}

    for root in roots:
        found_structure[root] = build_structure(root)

    return found_structure


def test_call_stack_order_implicit_depth_first(client):
    # Note: There is a debate going on about if the client should
    # be responsible for enforcing the call stack order (vs having)
    # another object that is responsible for this. This test is
    # written with the assumption that the client is responsible
    # for enforcing the call stack order. However, it is plausible
    # that we change this. If so, then this test will need to both
    # `create_call` and `push_call` effectively. Same with finish_call

    # This version of the call sequence matches the happy path
    # without any out-of-order calls
    call_1 = client.create_call("op", {})
    call_2 = client.create_call("op", {})
    call_3 = client.create_call("op", {})
    client.finish_call(call_3)
    call_4 = client.create_call("op", {})
    client.finish_call(call_4)
    client.finish_call(call_2)
    call_5 = client.create_call("op", {})
    call_6 = client.create_call("op", {})
    client.finish_call(call_6)
    call_7 = client.create_call("op", {})
    client.finish_call(call_7)
    client.finish_call(call_5)
    client.finish_call(call_1)

    terminal_root_call = client.create_call("op", {})
    client.finish_call(terminal_root_call)

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert call_structure(inner_res.calls) == {
        call_1.id: {
            call_2.id: {call_3.id: {}, call_4.id: {}},
            call_5.id: {call_6.id: {}, call_7.id: {}},
        },
        terminal_root_call.id: {},
    }


def test_call_stack_order_explicit_depth_first(client):
    # Note: There is a debate going on about if the client should
    # be responsible for enforcing the call stack order (vs having)
    # another object that is responsible for this. This test is
    # written with the assumption that the client is responsible
    # for enforcing the call stack order. However, it is plausible
    # that we change this. If so, then this test will need to both
    # `create_call` and `push_call` effectively. Same with finish_call
    #
    #
    # This version of the call sequence matches the happy path
    # without any out-of-order calls, but with explicit parentage
    # specified.
    call_1 = client.create_call("op", {})
    call_2 = client.create_call("op", {}, call_1)
    call_3 = client.create_call("op", {}, call_2)
    client.finish_call(call_3)
    call_4 = client.create_call("op", {}, call_2)
    client.finish_call(call_4)
    client.finish_call(call_2)
    call_5 = client.create_call("op", {}, call_1)
    call_6 = client.create_call("op", {}, call_5)
    client.finish_call(call_6)
    call_7 = client.create_call("op", {}, call_5)
    client.finish_call(call_7)
    client.finish_call(call_5)
    client.finish_call(call_1)

    terminal_root_call = client.create_call("op", {})
    client.finish_call(terminal_root_call)

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert call_structure(inner_res.calls) == {
        call_1.id: {
            call_2.id: {call_3.id: {}, call_4.id: {}},
            call_5.id: {call_6.id: {}, call_7.id: {}},
        },
        terminal_root_call.id: {},
    }


def test_call_stack_order_langchain_batch(client):
    # Note: There is a debate going on about if the client should
    # be responsible for enforcing the call stack order (vs having)
    # another object that is responsible for this. This test is
    # written with the assumption that the client is responsible
    # for enforcing the call stack order. However, it is plausible
    # that we change this. If so, then this test will need to both
    # `create_call` and `push_call` effectively. Same with finish_call
    #
    #
    # This sequence is pretty much exactly what langchain does when handling
    # a batch of calls. Specifically (prompt | llm).batch([1,2])
    call_1 = client.create_call("op", {})  # <- Implicit Parent, no stack = root
    call_2 = client.create_call("op", {}, call_1)  # <- RunnableSequence1
    call_5 = client.create_call("op", {}, call_1)  # <- RunnableSequence2
    call_3 = client.create_call("op", {}, call_2)  # <- Prompt1
    client.finish_call(call_3)
    call_4 = client.create_call("op", {}, call_2)  # <- LLM1
    call_4gpt = client.create_call("op", {})  # <- Openai
    client.finish_call(call_4gpt)
    client.finish_call(call_4)
    call_6 = client.create_call("op", {}, call_5)  # <- Prompt2
    client.finish_call(call_6)
    call_7 = client.create_call("op", {}, call_5)  # <- LLM2
    call_7gpt = client.create_call("op", {})  # <- Openai
    client.finish_call(call_7gpt)
    client.finish_call(call_7)
    client.finish_call(call_2)
    client.finish_call(call_5)
    client.finish_call(call_1)

    terminal_root_call = client.create_call("op", {})
    client.finish_call(terminal_root_call)

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert call_structure(inner_res.calls) == {
        call_1.id: {
            call_2.id: {call_3.id: {}, call_4.id: {call_4gpt.id: {}}},
            call_5.id: {call_6.id: {}, call_7.id: {call_7gpt.id: {}}},
        },
        terminal_root_call.id: {},
    }


POP_REORDERS_STACK = False


def test_call_stack_order_out_of_order_pop(client):
    # Note: There is a debate going on about if the client should
    # be responsible for enforcing the call stack order (vs having)
    # another object that is responsible for this. This test is
    # written with the assumption that the client is responsible
    # for enforcing the call stack order. However, it is plausible
    # that we change this. If so, then this test will need to both
    # `create_call` and `push_call` effectively. Same with finish_call
    #
    #
    # This ordering is a specifically challenging case where we return to
    # a parent that that was not the top of stack
    call_1 = client.create_call("op", {})
    call_2 = client.create_call("op", {})
    call_3 = client.create_call("op", {})
    # Purposely swap 4 & 5
    call_5 = client.create_call("op", {}, call_1)  # <- Explicit Parent (call_1)
    call_4 = client.create_call("op", {}, call_2)  # <- Explicit Parent (call_2)
    call_6 = client.create_call("op", {}, call_5)  # <- Explicit Parent (call_5)
    client.finish_call(call_6)  # <- Finish call_6
    # (should change stack to call_6.parent which is call_5)
    call_7 = client.create_call("op", {})  # <- Implicit Parent (call_5)
    # (current stack implementation will think this is 4)

    # Finish them in completely reverse order, because why not?
    client.finish_call(call_1)
    client.finish_call(call_2)
    client.finish_call(call_3)
    client.finish_call(call_4)
    client.finish_call(call_5)
    client.finish_call(call_7)

    terminal_root_call = client.create_call("op", {})
    client.finish_call(terminal_root_call)

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    if POP_REORDERS_STACK:
        # In my (Tim) opinion, this is the correct ordering.
        # However, the current implementation results in the
        # "else" branch here. The key difference is when we
        # finish call_6. Since call_6 was started immediately after
        # call_4, we currently will believe the top of the stack is
        # call_4. However, call_6's parent is call_5, so in my
        # opinion, we should pop the stack back to call_5. We
        # can debate this more and change the test/implementation
        # as needed.
        exp = {
            call_1.id: {
                call_2.id: {call_3.id: {}, call_4.id: {}},
                call_5.id: {call_6.id: {}, call_7.id: {}},
            },
            terminal_root_call.id: {},
        }
    else:
        exp = {
            call_1.id: {
                call_2.id: {call_3.id: {}, call_4.id: {call_7.id: {}}},
                call_5.id: {
                    call_6.id: {},
                },
            },
            terminal_root_call.id: {},
        }

    assert call_structure(inner_res.calls) == exp


def test_call_stack_order_height_ordering(client):
    # Note: There is a debate going on about if the client should
    # be responsible for enforcing the call stack order (vs having)
    # another object that is responsible for this. This test is
    # written with the assumption that the client is responsible
    # for enforcing the call stack order. However, it is plausible
    # that we change this. If so, then this test will need to both
    # `create_call` and `push_call` effectively. Same with finish_call
    #
    #
    # This ordering calls ops in the order of their height in the tree
    call_1 = client.create_call("op", {})
    call_2 = client.create_call("op", {}, call_1)
    call_5 = client.create_call("op", {}, call_1)
    call_3 = client.create_call("op", {}, call_2)
    call_6 = client.create_call("op", {}, call_5)
    call_4 = client.create_call("op", {}, call_2)
    call_7 = client.create_call("op", {}, call_5)

    # Finish them in completely reverse order
    client.finish_call(call_1)
    client.finish_call(call_2)
    client.finish_call(call_3)
    client.finish_call(call_4)
    client.finish_call(call_5)
    client.finish_call(call_7)

    terminal_root_call = client.create_call("op", {})
    client.finish_call(terminal_root_call)

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert call_structure(inner_res.calls) == {
        call_1.id: {
            call_2.id: {call_3.id: {}, call_4.id: {}},
            call_5.id: {call_6.id: {}, call_7.id: {}},
        },
        terminal_root_call.id: {},
    }


def test_call_stack_order_mixed(client):
    # Note: There is a debate going on about if the client should
    # be responsible for enforcing the call stack order (vs having)
    # another object that is responsible for this. This test is
    # written with the assumption that the client is responsible
    # for enforcing the call stack order. However, it is plausible
    # that we change this. If so, then this test will need to both
    # `create_call` and `push_call` effectively. Same with finish_call
    #
    #
    # This ordering is as mixed up as I could make it
    call_1 = client.create_call("op", {})
    call_5 = client.create_call("op", {}, call_1)
    call_7 = client.create_call("op", {}, call_5)
    client.finish_call(call_7)
    call_6 = client.create_call("op", {}, call_5)
    client.finish_call(call_5)
    call_2 = client.create_call("op", {}, call_1)
    client.finish_call(call_1)
    call_4 = client.create_call("op", {}, call_2)
    call_3 = client.create_call("op", {}, call_2)
    client.finish_call(call_2)
    client.finish_call(call_3)
    client.finish_call(call_4)

    terminal_root_call = client.create_call("op", {})
    client.finish_call(terminal_root_call)

    inner_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert call_structure(inner_res.calls) == {
        call_1.id: {
            call_5.id: {call_7.id: {}, call_6.id: {}},
            call_2.id: {call_4.id: {}, call_3.id: {}},
        },
        terminal_root_call.id: {},
    }


def test_call_query_stream_equality(client):
    @weave.op
    def calculate(a: int, b: int) -> int:
        return a + b

    for i in range(10):
        calculate(i, i * i)

    calls = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    calls_stream = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    i = 0
    for call in calls_stream:
        assert call == calls.calls[i]
        i += 1

    assert i == len(calls.calls)


def test_call_query_stream_columns(client):
    @weave.op
    def calculate(a: int, b: int) -> int:
        return {"result": {"a + b": a + b}, "not result": 123}

    for i in range(2):
        calculate(i, i * i)

    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "inputs"],
        )
    )
    calls = list(calls)
    assert len(calls) == 2
    assert len(calls[0].inputs) == 2

    # NO output returned because not required and not requested
    assert calls[0].output is None
    assert calls[0].ended_at is None
    assert calls[0].attributes == {}
    assert calls[0].inputs == {"a": 0, "b": 0}

    # now explicitly get output
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "inputs", "output.result"],
        )
    )
    calls = list(calls)
    assert len(calls) == 2
    assert calls[0].output["result"]["a + b"] == 0
    assert calls[0].attributes == {}
    assert calls[0].inputs == {"a": 0, "b": 0}


@pytest.mark.skip("Not implemented: filter / sort through refs")
def test_sort_and_filter_through_refs(client):
    @weave.op()
    def test_op(label, val):
        return val

    class TestObj(weave.Object):
        val: typing.Any

    def test_obj(val):
        return weave.publish(TestObj(val=val))

    import random

    # Purposely shuffled and contains values that would not sort correctly as strings
    values = [3, 9, 15, 21, 0, 12, 6, 18]
    random.shuffle(values)

    test_op(values[0], {"a": {"b": {"c": {"d": values[0]}}}})

    # Ref at A
    test_op(values[1], {"a": test_obj({"b": {"c": {"d": values[1]}}})})
    # Ref at B
    test_op(values[2], {"a": {"b": test_obj({"c": {"d": values[2]}})}})
    # Ref at C
    test_op(values[3], {"a": {"b": {"c": test_obj({"d": values[3]})}}})

    # Ref at A and B
    test_op(values[4], {"a": test_obj({"b": test_obj({"c": {"d": values[4]}})})})
    # Ref at A and C
    test_op(values[5], {"a": test_obj({"b": {"c": test_obj({"d": values[5]})}})})
    # Ref at B and C
    test_op(values[6], {"a": {"b": test_obj({"c": test_obj({"d": values[6]})})}})

    # Ref at A, B and C
    test_op(
        values[7], {"a": test_obj({"b": test_obj({"c": test_obj({"d": values[7]})})})}
    )

    for first, last, sort_by in [
        (0, 21, [tsi.SortBy(field="inputs.val.a.b.c.d", direction="asc")]),
        (21, 0, [tsi.SortBy(field="inputs.val.a.b.c.d", direction="desc")]),
        (0, 21, [tsi.SortBy(field="output.a.b.c.d", direction="asc")]),
        (21, 0, [tsi.SortBy(field="output.a.b.c.d", direction="desc")]),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=sort_by,
            )
        )

        assert inner_res.calls[0].inputs["label"] == first
        assert inner_res.calls[1].inputs["label"] == first

    for first, last, count, query in [
        (
            6,
            21,
            6,
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.val.a.b.c.d"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            },
        ),
        (
            0,
            3,
            2,
            {
                "$not": [
                    {
                        "$gt": [
                            {
                                "$convert": {
                                    "input": {"$getField": "output.a.b.c.d"},
                                    "to": "int",
                                }
                            },
                            {"$literal": 5},
                        ]
                    }
                ]
            },
        ),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq.model_validate(
                dict(
                    project_id=get_client_project_id(client),
                    sort_by=[tsi.SortBy(field="inputs.val.a.b.c.d", direction="asc")],
                    query={"$expr": query},
                )
            )
        )

        assert len(inner_res.calls) == count
        inner_res = get_client_trace_server(client).calls_query_stats(
            tsi.CallsQueryStatsReq.model_validate(
                dict(
                    project_id=get_client_project_id(client),
                    query={"$expr": query},
                )
            )
        )

        assert inner_res.count == count


def test_in_operation(client):
    @weave.op()
    def test_op(label, val):
        return val

    test_op(1, [1, 2, 3])
    test_op(2, [1, 2, 3])
    test_op(3, [5, 6, 7])
    test_op(4, [8, 2, 3])

    call_ids = [call.id for call in test_op.calls()]
    assert len(call_ids) == 4

    query = {
        "$in": [
            {"$getField": "id"},
            [{"$literal": call_id} for call_id in call_ids[:2]],
        ]
    }

    res = get_client_trace_server(client).calls_query_stats(
        tsi.CallsQueryStatsReq.model_validate(
            dict(
                project_id=get_client_project_id(client),
                query={"$expr": query},
            )
        )
    )
    assert res.count == 2

    query = {
        "$in": [
            {"$getField": "id"},
            [{"$literal": call_id} for call_id in call_ids],
        ]
    }
    res = get_client_trace_server(client).calls_query_stream(
        tsi.CallsQueryReq.model_validate(
            dict(
                project_id=get_client_project_id(client),
                query={"$expr": query},
            )
        )
    )
    res = list(res)
    assert len(res) == 4
    for i in range(4):
        assert res[i].id == call_ids[i]


def test_call_has_client_version(client):
    @weave.op
    def test():
        return 1

    _, c = test.call()
    assert "weave" in c.attributes
    assert "client_version" in c.attributes["weave"]


def test_user_cannot_modify_call_weave_dict(client):
    @weave.op
    def test():
        return 1

    _, call = test.call()

    call.attributes["test"] = 123

    with pytest.raises(KeyError):
        call.attributes["weave"] = {"anything": "blah"}

    with pytest.raises(KeyError):
        call.attributes["weave"]["anything"] = "blah"

    # you can set call.attributes["weave"]["anything"]["something_else"] = "blah"
    # but at that point you're on your own :)


def test_calls_iter_slice(client):
    @weave.op
    def func(x):
        return x

    for i in range(10):
        func(i)

    calls = func.calls()
    calls_subset = calls[2:5]
    assert len(calls_subset) == 3


def test_calls_iter_cached(client):
    @weave.op
    def func(x):
        return x

    for i in range(20):
        func(i)

    calls = func.calls()

    elapsed_times = []
    for i in range(3):
        start_time = time.time()
        c = calls[0]
        end_time = time.time()
        elapsed_times.append(end_time - start_time)

    # cached lookup should be way faster!
    assert elapsed_times[0] > elapsed_times[1] * 10
    assert elapsed_times[0] > elapsed_times[2] * 10


def test_calls_iter_different_value_same_page_cached(client):
    @weave.op
    def func(x):
        return x

    for i in range(20):
        func(i)

    calls = func.calls()

    start_time1 = time.time()
    c1 = calls[0]
    end_time1 = time.time()
    elapsed_time1 = end_time1 - start_time1

    # default page size is 1000, so these lookups should be cached too
    start_time2 = time.time()
    c2 = calls[1]
    end_time2 = time.time()
    elapsed_time2 = end_time2 - start_time2

    start_time3 = time.time()
    c3 = calls[2]
    end_time3 = time.time()
    elapsed_time3 = end_time3 - start_time3

    # cached lookup should be way faster!
    assert elapsed_time1 > elapsed_time2 * 10
    assert elapsed_time1 > elapsed_time3 * 10


class BasicModel(weave.Model):
    @weave.op()
    def predict(self, x):
        return {"answer": "42"}


def test_model_save(client):
    model = BasicModel()
    assert model.predict(1) == {"answer": "42"}
    model_ref = weave.publish(model)
    assert model.predict(1) == {"answer": "42"}
    model2 = model_ref.get()
    assert model2.predict(1) == {"answer": "42"}

    inner_res = get_client_trace_server(client).objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
            filter=tsi.ObjectVersionFilter(
                is_op=False, latest_only=True, base_object_classes=["Model"]
            ),
        )
    )

    assert len(inner_res.objs) == 1
    expected_predict_op = inner_res.objs[0].val["predict"]
    assert isinstance(expected_predict_op, str) and expected_predict_op.startswith(
        "weave:///"
    )
