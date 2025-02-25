import dataclasses
import datetime
import json
import platform
import random
import sys
import time
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from contextvars import copy_context
from dataclasses import dataclass
from typing import Any, Callable

import pytest
import wandb
from pydantic import BaseModel, ValidationError

import weave
from tests.trace.util import (
    AnyIntMatcher,
    DatetimeMatcher,
    FuzzyDateTimeMatcher,
    MaybeStringMatcher,
    client_is_sqlite,
    get_info_loglines,
)
from weave import Thread, ThreadPoolExecutor
from weave.trace import weave_client
from weave.trace.context.weave_client_context import (
    get_weave_client,
    set_weave_client_global,
)
from weave.trace.vals import MissingSelfInstanceError
from weave.trace.weave_client import sanitize_object_name
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ENTITY_TOO_LARGE_PAYLOAD
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.ids import generate_id
from weave.trace_server.refs_internal import extra_value_quoter
from weave.trace_server.trace_server_interface_util import (
    TRACE_REF_SCHEME,
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    extract_refs_from_values,
)

## Hacky interface compatibility helpers

ClientType = weave_client.WeaveClient


@dataclass
class ComplexAttribute:
    a: int
    b: dict[str, Any]


def get_client_trace_server(
    client: weave_client.WeaveClient,
) -> tsi.TraceServerInterface:
    return client.server


def get_client_project_id(client: weave_client.WeaveClient) -> str:
    return client._project_id()


## End hacky interface compatibility helpers


def test_simple_op(client):
    @weave.op
    def my_op(a: int) -> int:
        return a + 1

    assert my_op(5) == 6

    op_ref = weave_client.get_ref(my_op)
    # assert client._ref_is_own(op_ref)
    got_op = client.get(op_ref)

    calls = list(client.get_calls())
    assert len(calls) == 1
    fetched_call = calls[0]
    digest = "Zo4OshYu57R00QNlBBGjuiDGyewGYsJ1B69IKXSXYQY"
    expected_name = (
        f"{TRACE_REF_SCHEME}:///{client.entity}/{client.project}/op/my_op:{digest}"
    )
    assert fetched_call == weave_client.Call(
        _op_name=expected_name,
        project_id=f"{client.entity}/{client.project}",
        trace_id=fetched_call.trace_id,
        parent_id=None,
        id=fetched_call.id,
        inputs={"a": 5},
        exception=None,
        output=6,
        summary={
            "weave": {
                "status": "success",
                "trace_name": "my_op",
                "latency_ms": AnyIntMatcher(),
            }
        },
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
        "summary": {
            "weave": {
                "trace_name": "test_name",
                "status": "running",
            },
        },
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
        "summary": {
            "c": 5,
            "weave": {
                "trace_name": "test_name",
                "latency_ms": AnyIntMatcher(),
                "status": "success",
            },
        },
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
    @weave.op
    def my_op(a: int) -> int:
        return a + 1

    for i in range(10):
        my_op(i)

    calls = list(client.get_calls())
    assert len(calls) == 10

    # We want to preserve insert order
    assert [call.inputs["a"] for call in calls] == list(range(10))


class OpCallSummary(BaseModel):
    op: Callable
    num_calls: int = 0


class OpCallSpec(BaseModel):
    call_summaries: dict[str, OpCallSummary]
    total_calls: int
    root_calls: int
    run_calls: int


def simple_line_call_bootstrap(init_wandb: bool = False) -> OpCallSpec:
    # @weave.type()
    # class Number:
    #     value: int

    class Number(weave.Object):
        value: int

    @weave.op
    def adder(a: Number) -> Number:
        return Number(value=a.value + a.value)

    adder_v0 = adder

    @weave.op  # type: ignore
    def adder(a: Number, b) -> Number:
        return Number(value=a.value + b)

    @weave.op
    def subtractor(a: Number, b) -> Number:
        return Number(value=a.value - b)

    @weave.op
    def multiplier(
        a: Number, b
    ) -> int:  # intentionally deviant in returning plain int - so that we have a different type
        return a.value * b

    @weave.op
    def liner(m: Number, b, x) -> Number:
        return adder(Number(value=multiplier(m, x)), b)

    result: dict[str, OpCallSummary] = {}
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

    total_calls = sum(op_call.num_calls for op_call in result.values())

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


def has_any(list_a: list[str], list_b: list[str]) -> bool:
    return any(a in list_b for a in list_a)


def unique_vals(list_a: list[str]) -> list[str]:
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
    assert all(call.ended_at for call in res.calls)
    return res


def test_trace_call_query_filter_input_object_version_refs(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

    input_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.inputs)]
    )
    assert len(input_object_version_refs) > 3  # > 3

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
    @weave.op
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

    @weave.op
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


def test_trace_call_filter(client):
    is_sqlite = client_is_sqlite(client)

    @weave.op
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
                {
                    "project_id": get_client_project_id(client),
                    "query": {"$expr": query},
                }
            )
        )

        if len(inner_res.calls) != count:
            failed_cases.append(
                f"(ALL) Query {query} expected {count}, but found {len(inner_res.calls)}"
            )
        inner_res = get_client_trace_server(client).calls_query_stats(
            tsi.CallsQueryStatsReq.model_validate(
                {
                    "project_id": get_client_project_id(client),
                    "query": {"$expr": query},
                }
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
    @weave.op
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
    @weave.op
    def op_with_attrs(a: int, b: int) -> int:
        return a + b

    with weave.attributes(
        {
            "custom": "attribute",
            "complex": ComplexAttribute(a=1, b={"c": 2}),
        }
    ):
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
        "complex": {
            "__class__": {
                "module": "test_client_trace",
                "name": "ComplexAttribute",
                "qualname": "ComplexAttribute",
            },
            "a": 1,
            "b": {"c": 2},
        },
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

    @weave.op
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
        "a": {
            "_bases": [],
            "_class_name": "MyDataclass",
            "_type": "MyDataclass",
            "val": 1,
        },
        "b": {
            "_bases": [],
            "_class_name": "MyDataclass",
            "_type": "MyDataclass",
            "val": 2,
        },
    }
    assert res.calls[0].output == {
        "_bases": [],
        "_class_name": "MyDataclass",
        "_type": "MyDataclass",
        "val": 3,
    }


def test_op_retrieval(client):
    @weave.op
    def my_op(a: int) -> int:
        return a + 1

    assert my_op(1) == 2
    my_op_ref = weave_client.get_ref(my_op)
    my_op2 = my_op_ref.get()
    assert my_op2(1) == 2


def test_bound_op_retrieval(client):
    class CustomType(weave.Object):
        a: int

        @weave.op
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

        @weave.op
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
    exp_ref = "weave:///shawn/test-project/object/Dataset:tiRVKBWTP7LOwjBEqe79WFS7HEibm1WG8nfe94VWZBo/attr/rows/id/XfhC9dNA5D4taMvhKT4MKN2uce7F56Krsyv4Q6mvVMA/key/a"
    assert inner == 5
    assert inner.ref.uri() == exp_ref
    gotten = weave.ref(exp_ref).get()
    assert gotten == 5


def test_tuple_support(client):
    @weave.op
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
    @weave.op
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

    @weave.op
    async def dummy_score(output):
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
    class MyUnknownClassA:
        a_val: float

        def __init__(self, a_val) -> None:
            self.a_val = a_val

    class MyUnknownClassB:
        b_val: float

        def __init__(self, b_val) -> None:
            self.b_val = b_val

    @weave.op
    def op_with_unknown_types(a: MyUnknownClassA, b: float) -> MyUnknownClassB:
        return MyUnknownClassB(a.a_val + b)

    a = MyUnknownClassA(3)
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
    class MyUnknownClass:
        val: int

        def __init__(self, a_val) -> None:
            self.a_val = a_val

    class MySerializableClass(weave.Object):
        obj: MyUnknownClass

    a_obj = MyUnknownClass(1)
    a = MySerializableClass(obj=a_obj)
    b_obj = MyUnknownClass(2)
    b = MySerializableClass(obj=b_obj)

    ref_a = weave.publish(a)
    ref_b = weave.publish(b)

    a2 = weave.ref(ref_a.uri()).get()
    b2 = weave.ref(ref_b.uri()).get()

    assert a2.obj == repr(a_obj)
    assert b2.obj == repr(b_obj)


@contextmanager
def _no_graph_client():
    client = get_weave_client()
    set_weave_client_global(None)
    try:
        yield
    finally:
        set_weave_client_global(client)


@contextmanager
def _patched_default_initializer(trace_client: weave_client.WeaveClient):
    from weave.trace import weave_init

    def init_weave_get_server_patched(api_key):
        return trace_client.server

    orig = weave_init.init_weave_get_server
    weave_init.init_weave_get_server = init_weave_get_server_patched

    try:
        yield
    finally:
        weave_init.init_weave_get_server = orig


def test_single_primitive_output(client):
    @weave.op
    def single_int_output(a: int) -> int:
        return a

    @weave.op
    def single_bool_output(a: int) -> bool:
        return a == 1

    @weave.op
    def single_none_output(a: int) -> None:
        return None

    @weave.op
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
@pytest.mark.flaky(retries=5)  # <-- Flakes in CI
@pytest.mark.parametrize(
    "mapper",
    [
        map_simple,
        map_with_threads_no_executor,
        # # map_with_thread_executor,  # <-- Flakes in CI
        # map_with_copying_thread_executor, # <-- Flakes in CI
    ],
)
def test_mapped_execution(client, mapper):
    import time

    events = []

    @weave.op
    def op_a(a: int) -> int:
        events.append("A(S):" + str(a))
        time.sleep(0.3)
        events.append("A(E):" + str(a))
        return a

    @weave.op
    def op_b(b: int) -> int:
        events.append("B(S):" + str(b))
        time.sleep(0.2)
        res = op_a(b)
        events.append("B(E):" + str(b))
        return res

    @weave.op
    def op_c(c: int) -> int:
        events.append("C(S):" + str(c))
        time.sleep(0.1)
        res = op_b(c)
        events.append("C(E):" + str(c))
        return res

    @weave.op
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
    def calculate(a: int, b: int) -> dict[str, Any]:
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


def test_call_query_stream_columns_with_costs(client):
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    @weave.op
    def calculate(a: int, b: int) -> dict[str, Any]:
        return {
            "result": {"a + b": a + b},
            "not result": 123,
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            "model": "test_model",
        }

    for i in range(2):
        calculate(i, i * i)

    # Test that costs are returned if we include the summary field
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "summary"],
            include_costs=True,
        )
    )
    calls = list(calls)
    assert len(calls) == 2
    assert calls[0].summary is not None
    assert calls[0].summary.get("weave").get("costs") is not None

    # This should not happen, users should not request summary_dump
    # Test that costs are returned if we include the summary_dump field
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "summary_dump"],
            include_costs=True,
        )
    )
    calls = list(calls)
    assert len(calls) == 2
    assert calls[0].summary is not None
    assert calls[0].summary.get("weave").get("costs") is not None

    # Test that costs are returned if we don't include the summary field
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id"],
            include_costs=True,
        )
    )

    calls = list(calls)
    assert len(calls) == 2
    # Summary should come back even though it wasn't requested, because we include costs
    assert calls[0].summary.get("weave").get("costs") is not None

    # Test that costs are not returned if we include the summary field, but don't include costs
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "summary"],
        )
    )

    calls = list(calls)
    assert len(calls) == 2
    assert calls[0].summary is not None
    assert calls[0].summary.get("weave", {}).get("costs") is None


@pytest.mark.skip("Not implemented: filter / sort through refs")
def test_sort_and_filter_through_refs(client):
    @weave.op
    def test_op(label, val):
        return val

    class TestObj(weave.Object):
        val: Any

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
        values[7],
        {"a": test_obj({"b": test_obj({"c": test_obj({"d": values[7]})})})},
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
                {
                    "project_id": get_client_project_id(client),
                    "sort_by": [
                        tsi.SortBy(field="inputs.val.a.b.c.d", direction="asc")
                    ],
                    "query": {"$expr": query},
                }
            )
        )

        assert len(inner_res.calls) == count
        inner_res = get_client_trace_server(client).calls_query_stats(
            tsi.CallsQueryStatsReq.model_validate(
                {
                    "project_id": get_client_project_id(client),
                    "query": {"$expr": query},
                }
            )
        )

        assert inner_res.count == count


def test_in_operation(client):
    @weave.op
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
            {
                "project_id": get_client_project_id(client),
                "query": {"$expr": query},
            }
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
            {
                "project_id": get_client_project_id(client),
                "query": {"$expr": query},
            }
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
    @weave.op
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


def test_calls_stream_column_expansion(client):
    # make an object, and a nested object
    # make an op that accepts the nested object, and returns it
    # call the op

    class ObjectRef(weave.Object):
        id: str

    obj = ObjectRef(id="123")
    ref = weave.publish(obj)

    class SimpleObject(weave.Object):
        a: str

    class NestedObject(weave.Object):
        b: SimpleObject

    @weave.op
    def return_nested_object(nested_obj: NestedObject):
        return nested_obj

    simple_obj = SimpleObject(a=ref.uri())
    simple_ref = weave.publish(simple_obj)
    nested_obj = NestedObject(b=simple_obj)
    nested_ref = weave.publish(nested_obj)

    return_nested_object(nested_obj)

    # output is a ref
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    call_result = list(res)[0]
    assert call_result.output == nested_ref.uri()

    # output is dereffed
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output"],
            expand_columns=["output"],
        )
    )

    call_result = list(res)[0]
    assert call_result.output["b"] == simple_ref.uri()

    # expand 2 refs, should be {"b": {"a": ref}}
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output.b"],
            expand_columns=["output", "output.b"],
        )
    )
    call_result = list(res)[0]
    assert call_result.output["b"]["a"] == ref.uri()

    # expand 3 refs, should be {"b": {"a": {"id": 123}}}
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output.b.a"],
            expand_columns=["output", "output.b", "output.b.a"],
        )
    )
    call_result = list(res)[0]
    assert call_result.output["b"]["a"]["id"] == "123"

    # incomplete expansion columns, output should be un expanded
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output"],
            expand_columns=["output.b"],
        )
    )
    call_result = list(res)[0]
    assert call_result.output == nested_ref.uri()

    # non-existent column, should be un expanded
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output.b.a"],
            expand_columns=["output.b", "output.zzzz"],
        )
    )
    call_result = list(res)[0]
    assert call_result.output == nested_ref.uri()


# Batch size is dynamically increased from 10 to MAX_CALLS_STREAM_BATCH_SIZE (500)
# in clickhouse_trace_server_batched.py, this test verifies that the dynamic
# increase works as expected
@pytest.mark.parametrize("batch_size", [1, 10, 100, 110])
def test_calls_stream_column_expansion_dynamic_batch_size(client, batch_size):
    @weave.op
    def test_op(x):
        return x

    for i in range(batch_size):
        test_op(i)

    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output"],
            expand_columns=["output"],
        )
    )
    calls = list(res)
    assert len(calls) == batch_size
    for i in range(batch_size):
        assert calls[i].output == i


class Custom(weave.Object):
    val: dict


def test_object_with_disallowed_keys(client):
    name = "thing % with / disallowed : keys"
    obj = Custom(name=name, val={"1": 1})

    weave.publish(obj)

    # we sanitize the name
    assert obj.ref.name == "thing-with-disallowed-keys"

    create_req = tsi.ObjCreateReq.model_validate(
        {
            "obj": {
                "project_id": client._project_id(),
                "object_id": name,
                "val": {"1": 1},
            }
        }
    )
    with pytest.raises(InvalidFieldError):
        client.server.obj_create(create_req)


CHAR_LIMIT = 128


def test_object_with_char_limit(client):
    name = "l" * CHAR_LIMIT
    obj = Custom(name=name, val={"1": 1})

    weave.publish(obj)

    # we sanitize the name
    assert obj.ref.name == name

    create_req = tsi.ObjCreateReq.model_validate(
        {
            "obj": {
                "project_id": client._project_id(),
                "object_id": name,
                "val": {"1": 1},
            }
        }
    )
    client.server.obj_create(create_req)


def test_object_with_char_over_limit(client):
    name = "l" * (CHAR_LIMIT + 1)
    obj = Custom(name=name, val={"1": 1})

    weave.publish(obj)

    # we sanitize the name
    assert obj.ref.name == name[:-1]

    create_req = tsi.ObjCreateReq.model_validate(
        {
            "obj": {
                "project_id": client._project_id(),
                "object_id": name,
                "val": {"1": 1},
            }
        }
    )
    with pytest.raises(Exception):
        client.server.obj_create(create_req)


chars = "+_(){}|\"'<>!@$^&*#:,.[]-=;~`"


def test_objects_and_keys_with_special_characters(client):
    # make sure to include ":", "/" which are URI-related

    name_with_special_characters = "n-a_m.e: /" + chars + "100"
    dict_payload = {name_with_special_characters: "hello world"}

    obj = Custom(name=name_with_special_characters, val=dict_payload)

    weave.publish(obj)
    assert obj.ref is not None

    entity, project = client._project_id().split("/")
    project_id = f"{entity}/{project}"
    ref_base = f"weave:///{project_id}"
    exp_name = sanitize_object_name(name_with_special_characters)
    assert exp_name == "n-a_m.e-100"
    exp_key = extra_value_quoter(name_with_special_characters)
    assert (
        exp_key
        == "n-a_m.e%3A%20%2F%2B_%28%29%7B%7D%7C%22%27%3C%3E%21%40%24%5E%26%2A%23%3A%2C.%5B%5D-%3D%3B~%60100"
    )
    exp_digest = "iVLhViJ3vm8vMMo3Qj35mK7GiyP8jv3OJqasIGXjN0s"

    exp_obj_ref = f"{ref_base}/object/{exp_name}:{exp_digest}"
    assert obj.ref.uri() == exp_obj_ref

    @weave.op
    def test(obj: Custom):
        return obj.val[name_with_special_characters]

    test.name = name_with_special_characters

    res = test(obj)

    exp_res_ref = f"{exp_obj_ref}/attr/val/key/{exp_key}"
    found_ref = res.ref.uri()
    assert res == "hello world"
    assert found_ref == exp_res_ref

    gotten_res = weave.ref(found_ref).get()
    assert gotten_res == "hello world"

    exp_op_digest = "xEPCVKKjDWxKzqaCxxU09jD82FGGf5WcNy2fC9VUF3M"
    exp_op_ref = f"{ref_base}/op/{exp_name}:{exp_op_digest}"

    found_ref = test.ref.uri()
    assert found_ref == exp_op_ref
    gotten_fn = weave.ref(found_ref).get()
    assert gotten_fn(obj) == "hello world"


def test_calls_stream_feedback(client):
    BATCH_SIZE = 10
    num_calls = BATCH_SIZE + 1

    @weave.op
    def test_call(x):
        return "ello chap"

    for i in range(num_calls):
        test_call(i)

    calls = list(test_call.calls())
    assert len(calls) == num_calls

    # add feedback to the first call
    calls[0].feedback.add("note", {"note": "this is a note on call1"})
    calls[0].feedback.add_reaction("👍")
    calls[0].feedback.add_reaction("👍")
    calls[0].feedback.add_reaction("👎")

    calls[1].feedback.add_reaction("👍")

    # now get calls from the server, with the feedback expanded
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            include_feedback=True,
        )
    )
    calls = list(res)

    assert len(calls) == num_calls
    assert len(calls[0].summary["weave"]["feedback"]) == 4
    assert len(calls[1].summary["weave"]["feedback"]) == 1
    assert not calls[2].summary.get("weave", {}).get("feedback")

    call1_payloads = [f["payload"] for f in calls[0].summary["weave"]["feedback"]]
    assert {"note": "this is a note on call1"} in call1_payloads
    assert {
        "alias": ":thumbs_up:",
        "detoned": "👍",
        "detoned_alias": ":thumbs_up:",
        "emoji": "👍",
    } in call1_payloads
    assert {
        "alias": ":thumbs_down:",
        "detoned": "👎",
        "detoned_alias": ":thumbs_down:",
        "emoji": "👎",
    } in call1_payloads

    call2_payloads = [f["payload"] for f in calls[1].summary["weave"]["feedback"]]
    assert {
        "alias": ":thumbs_up:",
        "detoned": "👍",
        "detoned_alias": ":thumbs_up:",
        "emoji": "👍",
    } in call2_payloads


def test_inline_dataclass_generates_no_refs_in_function(client):
    @dataclasses.dataclass
    class A:
        b: int

    @weave.op
    def func(a: A):
        return A(b=a.b + 1)

    a = A(b=1)
    func(a)

    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
        )
    )
    input_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.inputs)]
    )
    assert len(input_object_version_refs) == 0

    output_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.output)]
    )
    assert len(output_object_version_refs) == 0


def test_inline_dataclass_generates_no_refs_in_object(client):
    @dataclasses.dataclass
    class A:
        b: int

    class WeaveObject(weave.Object):
        a: A

    wo = WeaveObject(a=A(b=1))
    ref = weave.publish(wo)

    res = get_client_trace_server(client).objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
        )
    )
    assert len(res.objs) == 1  # Just the weave object, and not the dataclass


def test_inline_pydantic_basemodel_generates_no_refs_in_function(client):
    class A(BaseModel):
        b: int

    @weave.op
    def func(a: A):
        return A(b=a.b + 1)

    a = A(b=1)
    func(a)

    res = get_client_trace_server(client).calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
        )
    )
    input_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.inputs)]
    )
    assert len(input_object_version_refs) == 0

    output_object_version_refs = unique_vals(
        [ref for call in res.calls for ref in extract_refs_from_values(call.output)]
    )
    assert len(output_object_version_refs) == 0


def test_inline_pydantic_basemodel_generates_no_refs_in_object(client):
    class A(BaseModel):
        b: int

    class WeaveObject(weave.Object):
        a: A

    wo = WeaveObject(a=A(b=1))
    ref = weave.publish(wo)

    res = get_client_trace_server(client).objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
        )
    )
    assert len(res.objs) == 1  # Just the weave object, and not the pydantic model


def test_large_keys_are_stripped_call(client, caplog):
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to strip in sqlite
        return

    data = {"dictionary": {f"{i}": i for i in range(300_000)}}

    @weave.op
    def test_op_dict(input_data: dict):
        return {"output": input_data}

    test_op_dict(data)

    calls = list(test_op_dict.calls())
    assert len(calls) == 1
    assert calls[0].output == json.loads(ENTITY_TOO_LARGE_PAYLOAD)
    assert calls[0].inputs == json.loads(ENTITY_TOO_LARGE_PAYLOAD)

    # now test for inputs/output as raw string
    @weave.op
    def test_op_str(input_data: str):
        return input_data

    test_op_str(json.dumps(data))

    calls = list(test_op_str.calls())
    assert len(calls) == 1
    assert calls[0].output == json.loads(ENTITY_TOO_LARGE_PAYLOAD)
    assert calls[0].inputs == json.loads(ENTITY_TOO_LARGE_PAYLOAD)

    # and now list
    @weave.op
    def test_op_list(input_data: list[str]):
        return input_data

    test_op_list([json.dumps(data)])

    calls = list(test_op_list.calls())
    assert len(calls) == 1
    assert calls[0].output == json.loads(ENTITY_TOO_LARGE_PAYLOAD)
    assert calls[0].inputs == json.loads(ENTITY_TOO_LARGE_PAYLOAD)

    error_messages = [
        record.message for record in caplog.records if record.levelname == "ERROR"
    ]
    for error_message in error_messages:
        assert "Retrying with large objects stripped" in error_message


def test_weave_finish_unsets_client(client):
    @weave.op
    def foo():
        return 1

    set_weave_client_global(None)
    weave.trace.weave_init._current_inited_client = (
        weave.trace.weave_init.InitializedClient(client)
    )
    weave_client = weave.trace.weave_init._current_inited_client.client
    assert weave.trace.weave_init._current_inited_client is not None

    foo()
    assert len(list(weave_client.get_calls())) == 1

    weave.finish()

    foo()
    assert len(list(weave_client.get_calls())) == 1
    assert weave.trace.weave_init._current_inited_client is None


def test_op_sampling(client):
    never_traced_calls = 0
    always_traced_calls = 0
    sometimes_traced_calls = 0

    random.seed(0)

    @weave.op(tracing_sample_rate=0.0)
    def never_traced(x: int) -> int:
        nonlocal never_traced_calls
        never_traced_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=1.0)
    def always_traced(x: int) -> int:
        nonlocal always_traced_calls
        always_traced_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=0.5)
    def sometimes_traced(x: int) -> int:
        nonlocal sometimes_traced_calls
        sometimes_traced_calls += 1
        return x + 1

    weave.publish(never_traced)
    # Never traced should execute but not be traced
    for i in range(10):
        never_traced(i)
    assert never_traced_calls == 10  # Function was called
    assert len(list(never_traced.calls())) == 0  # Not traced

    # Always traced should execute and be traced
    for i in range(10):
        always_traced(i)
    assert always_traced_calls == 10  # Function was called
    assert len(list(always_traced.calls())) == 10  # And traced
    # Sanity check that the call_start was logged, unlike in the never_traced case.
    assert "call_start" in client.server.attribute_access_log

    # Sometimes traced should execute always but only be traced sometimes
    num_runs = 100
    for i in range(num_runs):
        sometimes_traced(i)
    assert sometimes_traced_calls == num_runs  # Function was called every time
    num_traces = len(list(sometimes_traced.calls()))
    assert num_traces == 38


def test_op_sampling_async(client):
    never_traced_calls = 0
    always_traced_calls = 0
    sometimes_traced_calls = 0

    random.seed(0)

    @weave.op(tracing_sample_rate=0.0)
    async def never_traced(x: int) -> int:
        nonlocal never_traced_calls
        never_traced_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=1.0)
    async def always_traced(x: int) -> int:
        nonlocal always_traced_calls
        always_traced_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=0.5)
    async def sometimes_traced(x: int) -> int:
        nonlocal sometimes_traced_calls
        sometimes_traced_calls += 1
        return x + 1

    import asyncio

    weave.publish(never_traced)
    # Never traced should execute but not be traced
    for i in range(10):
        asyncio.run(never_traced(i))
    assert never_traced_calls == 10  # Function was called
    assert len(list(never_traced.calls())) == 0  # Not traced

    # Always traced should execute and be traced
    for i in range(10):
        asyncio.run(always_traced(i))
    assert always_traced_calls == 10  # Function was called
    assert len(list(always_traced.calls())) == 10  # And traced
    assert "call_start" in client.server.attribute_access_log

    # Sometimes traced should execute always but only be traced sometimes
    num_runs = 100
    for i in range(num_runs):
        asyncio.run(sometimes_traced(i))
    assert sometimes_traced_calls == num_runs  # Function was called every time
    num_traces = len(list(sometimes_traced.calls()))
    assert num_traces == 38


def test_op_sampling_inheritance(client):
    parent_calls = 0
    child_calls = 0

    @weave.op
    def child_op(x: int) -> int:
        nonlocal child_calls
        child_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=0.0)
    def parent_op(x: int) -> int:
        nonlocal parent_calls
        parent_calls += 1
        return child_op(x)

    weave.publish(parent_op)
    # When parent is sampled out, child should still execute but not be traced
    for i in range(10):
        parent_op(i)

    assert parent_calls == 10  # Parent function executed
    assert child_calls == 10  # Child function executed
    assert len(list(parent_op.calls())) == 0  # Parent not traced

    # Reset counters
    child_calls = 0

    # Direct calls to child should execute and be traced
    for i in range(10):
        child_op(i)

    assert child_calls == 10  # Child function executed
    assert len(list(child_op.calls())) == 10  # And was traced
    assert "call_start" in client.server.attribute_access_log  # Verify tracing occurred


def test_op_sampling_inheritance_async(client):
    parent_calls = 0
    child_calls = 0

    @weave.op
    async def child_op(x: int) -> int:
        nonlocal child_calls
        child_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=0.0)
    async def parent_op(x: int) -> int:
        nonlocal parent_calls
        parent_calls += 1
        return await child_op(x)

    import asyncio

    weave.publish(parent_op)
    # When parent is sampled out, child should still execute but not be traced
    for i in range(10):
        asyncio.run(parent_op(i))

    assert parent_calls == 10  # Parent function executed
    assert child_calls == 10  # Child function executed
    assert len(list(parent_op.calls())) == 0  # Parent not traced

    # Reset counters
    child_calls = 0

    # Direct calls to child should execute and be traced
    for i in range(10):
        asyncio.run(child_op(i))

    assert child_calls == 10  # Child function executed
    assert len(list(child_op.calls())) == 10  # And was traced
    assert "call_start" in client.server.attribute_access_log  # Verify tracing occurred


def test_op_sampling_invalid_rates(client):
    with pytest.raises(ValueError):

        @weave.op(tracing_sample_rate=-0.5)
        def negative_rate():
            pass

    with pytest.raises(ValueError):

        @weave.op(tracing_sample_rate=1.5)
        def too_high_rate():
            pass

    with pytest.raises(TypeError):

        @weave.op(tracing_sample_rate="invalid")  # type: ignore
        def invalid_type():
            pass


def test_op_sampling_child_follows_parent(client):
    parent_calls = 0
    child_calls = 0

    @weave.op(tracing_sample_rate=0.0)  # Never traced
    def child_op(x: int) -> int:
        nonlocal child_calls
        child_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=1.0)  # Always traced
    def parent_op(x: int) -> int:
        nonlocal parent_calls
        parent_calls += 1
        return child_op(x)

    num_runs = 100
    for i in range(num_runs):
        parent_op(i)

    assert parent_calls == num_runs  # Parent was always executed
    assert child_calls == num_runs  # Child was always executed

    parent_traces = len(list(parent_op.calls()))
    child_traces = len(list(child_op.calls()))

    assert parent_traces == num_runs  # Parent was always traced
    assert child_traces == num_runs  # Child was traced whenever parent was


def test_calls_len(client):
    @weave.op
    def test():
        return 1

    test()
    test()

    assert len(test.calls()) == 2
    assert len(client.get_calls()) == 2


def test_calls_query_multiple_dupe_select_columns(client, capsys, caplog):
    @weave.op
    def test():
        return {"a": {"b": {"c": {"d": 1}}}}

    test()
    test()

    calls = client.get_calls(
        columns=[
            "output",
            "output.a",
            "output.a.b",
            "output.a.b.c",
            "output.a.b.c.d",
        ]
    )

    assert len(calls) == 2
    assert calls[0].output == {"a": {"b": {"c": {"d": 1}}}}
    assert calls[0].output["a"] == {"b": {"c": {"d": 1}}}
    assert calls[0].output["a"]["b"] == {"c": {"d": 1}}
    assert calls[0].output["a"]["b"]["c"] == {"d": 1}
    assert calls[0].output["a"]["b"]["c"]["d"] == 1

    # now make sure we don't make duplicate selects
    if client_is_sqlite(client):
        select_queries = [
            line
            for line in capsys.readouterr().out.split("\n")
            if line.startswith("QUERY SELECT")
        ]
        for query in select_queries:
            assert query.count("output") == 1
    else:
        select_query = get_info_loglines(caplog, "clickhouse_stream_query", ["query"])[
            0
        ]
        assert (
            select_query["query"].count("any(calls_merged.output_dump) AS output_dump")
            == 1
        )


def test_calls_stream_heavy_condition_aggregation_parts(client):
    def _make_query(field: str, value: str) -> tsi.CallsQueryRes:
        query = {
            "$in": [
                {"$getField": field},
                [{"$literal": value}],
            ]
        }
        res = get_client_trace_server(client).calls_query_stream(
            tsi.CallsQueryReq.model_validate(
                {
                    "project_id": get_client_project_id(client),
                    "query": {"$expr": query},
                }
            )
        )
        return list(res)

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
        inputs={"param": {"value1": "hello"}},
    )
    client.server.call_start(tsi.CallStartReq(start=start))

    res = _make_query("inputs.param.value1", "hello")
    assert len(res) == 1
    assert res[0].inputs["param"]["value1"] == "hello"
    assert not res[0].output

    end = tsi.EndedCallSchemaForInsert(
        project_id=client._project_id(),
        id=call_id,
        ended_at=datetime.datetime.now(tz=datetime.timezone.utc),
        summary={"c": 5},
        output={"d": 5},
    )
    client.server.call_end(tsi.CallEndReq(end=end))

    res = _make_query("inputs.param.value1", "hello")
    assert len(res) == 1
    assert res[0].inputs["param"]["value1"] == "hello"

    if client_is_sqlite(client):
        # Does the query return the output?
        with pytest.raises(TypeError):
            # There will be no output because clickhouse hasn't merged the inputs and
            # output yet
            assert res[0].output["d"] == 5

    # insert some more calls to encourage clickhouse to merge

    @weave.op
    def test():
        return 1

    test()
    test()
    test()

    res = _make_query("inputs.param.value1", "hello")
    assert len(res) == 1
    assert res[0].output["d"] == 5


def test_call_stream_query_heavy_query_batch(client):
    # start 10 calls
    call_ids = []
    project_id = get_client_project_id(client)
    for i in range(10):
        call_id = generate_id()
        call_ids.append(call_id)
        trace_id = generate_id()
        parent_id = generate_id()
        start = tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            op_name="test_name",
            trace_id=trace_id,
            parent_id=parent_id,
            started_at=datetime.datetime.now(tz=datetime.timezone.utc)
            - datetime.timedelta(seconds=1),
            attributes={"a": 5},
            inputs={"param": {"value1": "hello"}},
        )
        client.server.call_start(tsi.CallStartReq(start=start))

    # end 10 calls
    for i in range(10):
        call_id = generate_id()
        trace_id = generate_id()
        parent_id = generate_id()
        end = tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=call_ids[i],
            ended_at=datetime.datetime.now(tz=datetime.timezone.utc),
            summary={"c": 5},
            output={"d": 5, "e": "f"},
        )
        client.server.call_end(tsi.CallEndReq(end=end))

    # filter by output
    output_query = {
        "project_id": project_id,
        "query": {
            "$expr": {
                "$eq": [
                    {"$getField": "output.e"},
                    {"$literal": "f"},
                ]
            }
        },
    }
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq.model_validate(output_query)
    )
    if not client_is_sqlite(client):
        with pytest.raises(AssertionError):
            # in clickhouse we don't know how many calls are merged
            print("res", list(res))
            assert len(list(res)) == 10
            for call in res:
                assert call.attributes["a"] == 5
    else:
        assert len(list(res)) == 10
        for call in res:
            assert call.attributes["a"] == 5

    # Clickhouse normally merges after a query of a table like this.
    # If so, the next query, while only filtering by inputs, will
    # also include the outputs. So we should expect the correct
    # results for both client.

    # now query for inputs by string
    input_string_query = {
        "project_id": project_id,
        "query": {
            "$expr": {
                "$eq": [
                    {"$getField": "inputs.param.value1"},
                    {"$literal": "hello"},
                ]
            }
        },
    }
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq.model_validate(input_string_query)
    )
    assert len(list(res)) == 10
    for call in res:
        assert call.inputs["param"]["value1"] == "hello"
        assert call.output["d"] == 5

    # now that we have merged, the inital query should succeed
    res1 = client.server.calls_query_stream(
        tsi.CallsQueryReq.model_validate(output_query)
    )
    assert len(list(res1)) == 10
    for call in res1:
        assert call.inputs["param"]["value1"] == "hello"
        assert call.output["d"] == 5
