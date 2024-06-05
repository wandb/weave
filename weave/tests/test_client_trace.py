from contextlib import contextmanager
import dataclasses
from collections import namedtuple
import datetime
import os
import typing
import pytest

from pydantic import BaseModel, ValidationError
import wandb
import weave
from weave import weave_client
from weave import context_state
from weave.trace.vals import MissingSelfInstanceError, TraceObject
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from ..trace_server.trace_server_interface_util import (
    TRACE_REF_SCHEME,
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    extract_refs_from_values,
    generate_id,
)
from ..trace_server import trace_server_interface as tsi

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
    # assert client.ref_is_own(op_ref)
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
    )


def test_dataset(client):
    from weave.flow.dataset import Dataset

    d = Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.ref(ref.uri()).get()
    assert list(d2.rows) == list(d2.rows)


def test_trace_server_call_start_and_end(client):
    call_id = generate_id()
    start = tsi.StartedCallSchemaForInsert(
        project_id=client._project_id(),
        id=call_id,
        op_name="test_name",
        trace_id="test_trace_id",
        parent_id="test_parent_id",
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
        "trace_id": "test_trace_id",
        "parent_id": "test_parent_id",
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
        "trace_id": "test_trace_id",
        "parent_id": "test_parent_id",
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
    }


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
    ) -> (
        int
    ):  # intentionally deviant in returning plain int - so that we have a different type
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
                filter=tsi._CallsFilter(op_names=op_version_refs),
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
                filter=tsi._CallsFilter(input_refs=input_object_version_refs),
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
                filter=tsi._CallsFilter(output_refs=output_object_version_refs),
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
                filter=tsi._CallsFilter(parent_ids=parent_ids),
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
                filter=tsi._CallsFilter(trace_ids=trace_ids),
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
                filter=tsi._CallsFilter(call_ids=call_ids),
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
                filter=tsi._CallsFilter(trace_roots_only=trace_roots_only),
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
                filter=tsi._CallsFilter(wb_run_ids=wb_run_ids),
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
        (2, 0, [tsi._SortBy(field="started_at", direction="desc")]),
        (2, 0, [tsi._SortBy(field="inputs.in_val.prim", direction="desc")]),
        (2, 0, [tsi._SortBy(field="inputs.in_val.list.0", direction="desc")]),
        (2, 0, [tsi._SortBy(field="inputs.in_val.dict.inner", direction="desc")]),
        (2, 0, [tsi._SortBy(field="output.prim", direction="desc")]),
        (2, 0, [tsi._SortBy(field="output.list.0", direction="desc")]),
        (2, 0, [tsi._SortBy(field="output.dict.inner", direction="desc")]),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=sort_by,
            )
        )

        assert inner_res.calls[0].inputs["in_val"]["prim"] == first
        assert inner_res.calls[2].inputs["in_val"]["prim"] == last


def test_trace_call_filter(client):
    is_sql_lite = isinstance(client.server, SqliteTraceServer)

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
    for (count, query) in [
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
                1 if is_sql_lite else 0
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
                1 if is_sql_lite else 0
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
                -2 if is_sql_lite else 0
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
                1 if is_sql_lite else 0
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
            filter=tsi._ObjectVersionFilter(
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
            filter=tsi._CallsFilter(op_names=[ref_str(op_with_attrs)]),
        )
    )

    assert len(res.calls) == 1
    assert res.calls[0].attributes == {"custom": "attribute"}


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
            filter=tsi._CallsFilter(op_names=[ref_str(dataclass_maker)]),
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


@pytest.mark.skip_clickhouse_client
def test_dataset_row_ref(client):
    d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.ref(ref.uri()).get()

    inner = d2.rows[0]["a"]
    exp_ref = "weave:///shawn/test-project/object/Dataset:aF7lCSKo9BTXJaPxYHEBsH51dOKtwzxS6Hqvw4RmAdc/attr/rows/id/XfhC9dNA5D4taMvhKT4MKN2uce7F56Krsyv4Q6mvVMA/key/a"
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
            filter=tsi._CallsFilter(op_names=[ref_str(tuple_maker)]),
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
            filter=tsi._CallsFilter(op_names=[ref_str(tuple_maker)]),
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
            filter=tsi._ObjectVersionFilter(
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
    token = context_state._graph_client.set(None)
    try:
        yield
    finally:
        context_state._graph_client.reset(token)


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
    assert c == None
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
    assert inner_res.calls[2].output == None
    assert inner_res.calls[3].output == {"a": 1, "b": True, "c": None}


def test_sort_through_refs(client):
    @weave.op()
    def test_op(label, val):
        return val

    class TestObj(weave.Object):
        val: typing.Any

    def test_obj(val):
        return weave.publish(TestObj(val=val))

    import random

    # Purposely shuffled and contains values that would not sort correctly as strings
    values = [3, 9, 15, 21, 12, 6, 18]
    random.shuffle(values)

    res = test_op(values[0], {"a": {"b": {"c": {"d": values[0]}}}})

    # Ref at A
    res = test_op(values[1], {"a": test_obj({"b": {"c": {"d": values[1]}}})})
    # Ref at B
    res = test_op(values[2], {"a": {"b": test_obj({"c": {"d": values[2]}})}})
    # Ref at C
    res = test_op(values[3], {"a": {"b": {"c": test_obj({"d": values[3]})}}})

    # Ref at A and B
    res = test_op(values[4], {"a": test_obj({"b": test_obj({"c": {"d": values[4]}})})})
    # Ref at A and C
    res = test_op(values[5], {"a": test_obj({"b": {"c": test_obj({"d": values[5]})}})})
    # Ref at B and C
    res = test_op(values[6], {"a": {"b": test_obj({"c": test_obj({"d": values[6]})})}})

    # Ref at A, B and C
    res = test_op(
        values[7], {"a": test_obj({"b": test_obj({"c": test_obj({"d": values[7]})})})}
    )

    for first, last, sort_by in [
        (0, 21, [tsi._SortBy(field="inputs.val.a.b.c.d", direction="asc")]),
        (21, 0, [tsi._SortBy(field="inputs.val.a.b.c.d", direction="desc")]),
        (0, 21, [tsi._SortBy(field="output.a.b.c.d", direction="asc")]),
        (21, 0, [tsi._SortBy(field="output.a.b.c.d", direction="desc")]),
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
                    sort_by=[tsi._SortBy(field="inputs.val.a.b.c.d", direction="asc")],
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
