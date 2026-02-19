import dataclasses
import datetime
import json
import platform
import random
import sys
import time
import uuid
from collections import defaultdict, namedtuple
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import copy_context
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from pydantic import BaseModel, ValidationError

import weave
import weave.trace.call
from tests.trace.util import (
    AnyIntMatcher,
    DatetimeMatcher,
    FuzzyDateTimeMatcher,
    MaybeStringMatcher,
    client_is_sqlite,
    get_info_loglines,
)
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
)
from weave import Thread, ThreadPoolExecutor
from weave.shared.refs_internal import extra_value_quoter
from weave.shared.trace_server_interface_util import (
    TRACE_REF_SCHEME,
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    extract_refs_from_values,
)
from weave.trace import weave_client
from weave.trace.context.call_context import require_current_call
from weave.trace.context.weave_client_context import (
    get_weave_client,
    set_weave_client_global,
)
from weave.trace.refs import TableRef
from weave.trace.vals import MissingSelfInstanceError
from weave.trace.weave_client import sanitize_object_name
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_settings import ENTITY_TOO_LARGE_PAYLOAD
from weave.trace_server.common_interface import SortBy
from weave.trace_server.errors import InsertTooLarge, InvalidFieldError, InvalidRequest
from weave.trace_server.ids import generate_id
from weave.trace_server.token_costs import COST_OBJECT_NAME
from weave.trace_server.validation_util import CHValidationError
from weave.utils.project_id import from_project_id, to_project_id

## Hacky interface compatibility helpers


def extract_weave_refs_from_value(value):
    """Extract all strings that start with 'weave:///' from a value."""
    refs = []
    if isinstance(value, str) and value.startswith("weave:///"):
        refs.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            refs.extend(extract_weave_refs_from_value(v))
    elif isinstance(value, list):
        for v in value:
            refs.extend(extract_weave_refs_from_value(v))
    return refs


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
    digest = "VAjc7UcWtXC9OiUr6jrzM6CURhBaMiBr0gqOddcCxY4"
    expected_name = (
        f"{TRACE_REF_SCHEME}:///{client.entity}/{client.project}/op/my_op:{digest}"
    )
    assert fetched_call == weave.trace.call.Call(
        _op_name=expected_name,
        project_id=to_project_id(client.entity, client.project),
        trace_id=fetched_call.trace_id,
        parent_id=None,
        id=fetched_call.id,
        inputs={"a": 5},
        exception=None,
        output=6,
        summary={
            "status_counts": {
                "success": 1,
                "error": 0,
            },
            "weave": {
                "status": "success",
                "trace_name": "my_op",
                "latency_ms": AnyIntMatcher(),
            },
        },
        attributes={
            "weave": {
                "client_version": weave.version.VERSION,
                "source": "python-sdk",
                "os_name": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "sys_version": sys.version,
                "python": {
                    "type": "function",
                },
            },
        },
        started_at=DatetimeMatcher(),
        ended_at=DatetimeMatcher(),
        deleted_at=None,
    )


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
        "wb_run_step": None,
        "wb_run_step_end": None,
        "deleted_at": None,
        "display_name": None,
        "storage_size_bytes": None,
        "total_storage_size_bytes": None,
        "thread_id": None,
        "turn_id": None,
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
        "wb_run_step": None,
        "wb_run_step_end": None,
        "deleted_at": None,
        "display_name": None,
        "storage_size_bytes": None,
        "total_storage_size_bytes": None,
        "thread_id": None,
        "turn_id": None,
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
    part_sequence: list[tuple[str, str]]


def simple_line_call_bootstrap() -> OpCallSpec:
    part_sequence = []

    def track_sequence(name: str):
        def wrapper(fn):
            def wrapped(*args, **kwargs):
                part_sequence.append(("start", name))
                res = fn(*args, **kwargs)
                part_sequence.append(("end", name))
                return res

            wrapped.__name__ = fn.__name__

            return wrapped

        return wrapper

    class Number(weave.Object):
        value: int

    @weave.op
    @track_sequence("adder")
    def adder(a: Number) -> Number:
        res = Number(value=a.value + a.value)

    adder_v0 = adder

    @weave.op
    @track_sequence("adder")
    def adder(a: Number, b) -> Number:
        return Number(value=a.value + b)

    @weave.op
    @track_sequence("subtractor")
    def subtractor(a: Number, b) -> Number:
        return Number(value=a.value - b)

    @weave.op
    @track_sequence("multiplier")
    def multiplier(
        a: Number, b
    ) -> int:  # intentionally deviant in returning plain int - so that we have a different type
        return a.value * b

    @weave.op
    @track_sequence("liner")
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
    for i in range(num_calls):
        liner(Number(value=i), i, i)
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
        part_sequence=part_sequence,
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
        [
            ref
            for call in res.calls
            for ref in extract_weave_refs_from_value(call.inputs)
        ]
    )
    assert len(input_object_version_refs) > 3  # > 3

    for input_refs, exp_count in [
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
                        extract_weave_refs_from_value(call.inputs),
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
                        extract_weave_refs_from_value(call.inputs),
                        input_object_version_refs[:3],
                    )
                ]
            ),
        ),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(input_refs=input_refs),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_wb_run_step_query(client):
    from weave.trace import weave_client
    from weave.trace.wandb_run_context import WandbRunContext

    step_counter = iter(range(100))

    def mock_context():
        return WandbRunContext(run_id="test-run", step=next(step_counter))

    with mock.patch.object(
        weave_client, "get_global_wb_run_context", side_effect=mock_context
    ):
        call_spec = simple_line_call_bootstrap()

    server = get_client_trace_server(client)
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client))
    )
    exp_start_steps = []
    exp_end_steps = []
    counter = 0
    for part in call_spec.part_sequence:
        if part[0] == "start":
            exp_start_steps.append(counter)
        else:
            exp_end_steps.append(counter)
        counter += 1
    exp_start_steps_set = set(exp_start_steps)
    found_start_steps_set = {c.wb_run_step for c in res.calls}
    assert found_start_steps_set == exp_start_steps_set
    exp_end_steps_set = set(exp_end_steps)
    found_end_steps_set = {c.wb_run_step_end for c in res.calls}
    assert found_end_steps_set == exp_end_steps_set

    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "wb_run_step"}, {"$literal": 0}]}}
    )
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client), query=query)
    )
    assert len(res.calls) == 1

    count = 2
    compare_step = exp_start_steps[-count]
    range_query = tsi.Query(
        **{
            "$expr": {
                "$gte": [{"$getField": "wb_run_step"}, {"$literal": compare_step}]
            }
        }
    )
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client), query=range_query)
    )
    assert len(res.calls) == count

    lt_query = tsi.Query(
        **{"$expr": {"$lt": [{"$getField": "wb_run_step"}, {"$literal": compare_step}]}}
    )
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client), query=lt_query)
    )
    exp_lt_count = len([step for step in exp_start_steps if step < compare_step])
    assert len(res.calls) == exp_lt_count

    count = 4
    compare_step = exp_end_steps[-count]
    range_query = tsi.Query(
        **{
            "$expr": {
                "$gte": [{"$getField": "wb_run_step_end"}, {"$literal": compare_step}]
            }
        }
    )
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client), query=range_query)
    )
    assert len(res.calls) == count

    res = server.calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            sort_by=[SortBy(field="wb_run_step", direction="desc")],
        )
    )
    exp_steps = sorted(exp_start_steps, reverse=True)
    found_steps = [c.wb_run_step for c in res.calls]
    assert found_steps == exp_steps

    res = server.calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            sort_by=[SortBy(field="wb_run_step_end", direction="desc")],
        )
    )
    exp_steps = sorted(exp_end_steps, reverse=True)
    found_steps = [c.wb_run_step_end for c in res.calls]
    assert found_steps == exp_steps


def test_trace_call_wb_run_context_override(client):
    """Test that client.set_wandb_run_context() overrides wandb run info."""
    # Set the context with a specific run_id and step
    client.set_wandb_run_context(run_id="test-run", step=0)

    # Create calls using simple_line_call_bootstrap
    call_spec = simple_line_call_bootstrap()

    # Query the calls to verify the override worked
    server = get_client_trace_server(client)
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client))
    )

    # All calls should have the overridden wb_run_id
    expected_wb_run_id = f"{client.entity}/{client.project}/test-run"
    for call in res.calls:
        assert call.wb_run_id == expected_wb_run_id

    # All calls should have step 0 for both start and end (since we set a fixed value)
    for call in res.calls:
        assert call.wb_run_step == 0
        assert call.wb_run_step_end == 0

    # Test querying by wb_run_step
    query = tsi.Query(
        **{"$expr": {"$eq": [{"$getField": "wb_run_step"}, {"$literal": 0}]}}
    )
    res = server.calls_query(
        tsi.CallsQueryReq(project_id=get_client_project_id(client), query=query)
    )
    # All calls should match since they all have step 0
    assert len(res.calls) == call_spec.total_calls

    # Test sorting by wb_run_step (all should be 0)
    res = server.calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            sort_by=[SortBy(field="wb_run_step", direction="desc")],
        )
    )
    assert all(c.wb_run_step == 0 for c in res.calls)

    # Test sorting by wb_run_step_end (all should be 0)
    res = server.calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            sort_by=[SortBy(field="wb_run_step_end", direction="desc")],
        )
    )
    assert all(c.wb_run_step_end == 0 for c in res.calls)

    # Clear the context
    client.clear_wandb_run_context()

    # Create a new call to verify it no longer has the override
    @weave.op
    def test_op_after_clear():
        return "done"

    test_op_after_clear()

    # Get the latest call (should be the one we just created)
    res = server.calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            sort_by=[SortBy(field="started_at", direction="desc")],
            limit=1,
        )
    )
    assert len(res.calls) == 1
    latest_call = res.calls[0]

    # The wb_run_id and wb_run_step should be None now (no override, no global wandb.run)
    assert latest_call.wb_run_id is None
    assert latest_call.wb_run_step is None


def test_trace_call_query_filter_output_object_version_refs(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

    output_object_version_refs = unique_vals(
        [
            ref
            for call in res.calls
            for ref in extract_weave_refs_from_value(call.output)
        ]
    )
    assert len(output_object_version_refs) > 3

    for output_refs, exp_count in [
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
                        extract_weave_refs_from_value(call.output),
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
                        extract_weave_refs_from_value(call.output),
                        output_object_version_refs[:3],
                    )
                ]
            ),
        ),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(output_refs=output_refs),
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

    for parent_id_list, exp_count in [
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
                filter=tsi.CallsFilter(parent_ids=parent_id_list),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_trace_ids(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

    trace_ids = [call.trace_id for call in res.calls]

    for trace_id_list, exp_count in [
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
                filter=tsi.CallsFilter(trace_ids=trace_id_list),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_call_ids(client):
    call_spec = simple_line_call_bootstrap()

    res = get_all_calls_asserting_finished(client, call_spec)

    call_ids = [call.id for call in res.calls]

    for call_id_list, exp_count in [
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
                filter=tsi.CallsFilter(call_ids=call_id_list),
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


def test_trace_call_query_filter_wb_run_ids(client):
    full_wb_run_id_1 = f"{client.entity}/{client.project}/test-run-1"
    full_wb_run_id_2 = f"{client.entity}/{client.project}/test-run-2"
    from weave.trace import weave_client
    from weave.trace.wandb_run_context import WandbRunContext

    with mock.patch.object(
        weave_client,
        "get_global_wb_run_context",
        return_value=WandbRunContext(run_id="test-run-1", step=0),
    ):
        call_spec_1 = simple_line_call_bootstrap()
    with mock.patch.object(
        weave_client,
        "get_global_wb_run_context",
        return_value=WandbRunContext(run_id="test-run-2", step=0),
    ):
        call_spec_2 = simple_line_call_bootstrap()
    call_spec_3 = simple_line_call_bootstrap()

    total_calls = (
        call_spec_1.total_calls + call_spec_2.total_calls + call_spec_3.total_calls
    )

    for wb_run_ids, exp_count in [
        (None, total_calls),
        ([], total_calls),
        ([full_wb_run_id_1], call_spec_1.total_calls),
        (
            [full_wb_run_id_1, full_wb_run_id_2],
            call_spec_1.total_calls + call_spec_2.total_calls,
        ),
        ([f"{client.entity}/{client.project}/NOT_A_RUN"], 0),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(wb_run_ids=wb_run_ids),
            )
        )

        assert len(inner_res.calls) == exp_count


def test_trace_call_query_filter_wb_user_ids(client):
    call_spec_1 = simple_line_call_bootstrap()

    # OMG! How ugly is this?! The layers of testing servers is nasty
    client.server.server._next_trace_server._user_id = "second_user"
    call_spec_2 = simple_line_call_bootstrap()

    # OMG! How ugly is this?! The layers of testing servers is nasty
    client.server.server._next_trace_server._user_id = "third_user"
    call_spec_3 = simple_line_call_bootstrap()

    for wb_user_ids, exp_count in [
        (
            None,
            call_spec_1.total_calls + call_spec_2.total_calls + call_spec_3.total_calls,
        ),
        (
            [],
            call_spec_1.total_calls + call_spec_2.total_calls + call_spec_3.total_calls,
        ),
        (["second_user"], call_spec_2.total_calls),
        (
            ["second_user", "third_user"],
            call_spec_2.total_calls + call_spec_3.total_calls,
        ),
        (["NOT_A_USER"], 0),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.CallsFilter(wb_user_ids=wb_user_ids),
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


def test_trace_call_query_timings(client):
    now = datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    later = now + datetime.timedelta(seconds=1)
    even_later = later + datetime.timedelta(seconds=1)

    num_calls = 100

    # Create calls with controlled timing - mock only datetime.datetime.now()
    call_index = 0

    def mock_now(*args, **kwargs):
        nonlocal call_index
        # Each create_call increments the index once at the start
        # Return the appropriate time based on which call we're processing
        if call_index <= num_calls - 3:  # calls 0-97 get 'now'
            return now
        elif call_index == num_calls - 2:  # call 98 gets 'later'
            return later
        else:  # call 99 gets 'even_later'
            return even_later

    with mock.patch(
        "weave.trace.weave_client.datetime.datetime"
    ) as mock_datetime_class:
        # Mock only the .now() method, keep everything else as-is
        mock_datetime_class.now = mock.Mock(side_effect=mock_now)
        # Preserve other datetime functionality
        mock_datetime_class.side_effect = lambda *args, **kw: datetime.datetime(
            *args, **kw
        )

        for i in range(num_calls):
            call_index = i
            client.create_call("y", {"a": i})

    def query_server():
        result = get_client_trace_server(client).calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[SortBy(field="started_at", direction="desc")],
            )
        )
        return list(result)

    def query_client(page_size):
        res = client.get_calls(
            sort_by=[SortBy(field="started_at", direction="desc")],
            page_size=page_size,
        )
        return list(res)

    # get all calls, sorted by started_at
    res = query_server()
    assert len(res) == num_calls
    assert res[0].started_at == even_later
    assert res[1].started_at == later
    for c in res[2:]:
        assert c.started_at == now

    ids = [c.id for c in res]

    # indeterminite ordering should always default to the same thing
    for _i in range(5):
        tres = query_server()
        tids = [c.id for c in tres]
        assert tids == ids

    # page_size 10 to test ordering within pages
    for _i in range(3):
        tres = query_client(page_size=10)
        tids = [c.id for c in tres]
        assert tids == ids


def test_trace_call_sort(client):
    @weave.op
    def basic_op(in_val: dict, delay) -> dict:
        import time

        time.sleep(delay)
        return in_val

    for i in range(3):
        basic_op({"prim": i, "list": [i], "dict": {"inner": i}}, i / 10)

    for first, last, sort_by in [
        (2, 0, [SortBy(field="started_at", direction="desc")]),
        (2, 0, [SortBy(field="inputs.in_val.prim", direction="desc")]),
        (2, 0, [SortBy(field="inputs.in_val.list.0", direction="desc")]),
        (2, 0, [SortBy(field="inputs.in_val.dict.inner", direction="desc")]),
        (2, 0, [SortBy(field="output.prim", direction="desc")]),
        (2, 0, [SortBy(field="output.list.0", direction="desc")]),
        (2, 0, [SortBy(field="output.dict.inner", direction="desc")]),
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
                sort_by=[SortBy(field="inputs.in_val.prim", direction=direction)],
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
            "python": {
                "type": "function",
            },
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
        def op_with_custom_type(self, v):
            return self.a + v

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
    exp_ref = "weave:///shawn/test-project/object/Dataset:FkWFKCRcl9wsGp3yclN7v1IIAICTPenpZYrWo0otI4Y/attr/rows/id/XfhC9dNA5D4taMvhKT4MKN2uce7F56Krsyv4Q6mvVMA/key/a"
    assert inner == 5
    assert inner.ref.uri() == exp_ref
    gotten = weave.ref(exp_ref).get()
    assert gotten == 5


def test_table_query_empty_sort_field_validation(client):
    """Test that empty or invalid sort fields in table queries are properly validated."""
    # Create a dataset with table data
    d = weave.Dataset(name="test_dataset", rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    weave.publish(d)

    # Query the object to get its val
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
            filter={"object_ids": ["test_dataset"]},
        )
    )
    assert len(res.objs) == 1
    queried_obj = res.objs[0]

    # Get table reference from the dataset
    table_ref = TableRef.parse_uri(queried_obj.val["rows"])

    # Test various invalid sort field scenarios that should trigger validation errors
    invalid_sort_fields = [
        "",  # Empty field
        ".",  # Just a dot
        "..",  # Multiple dots
        "...",  # More dots
        "a.",  # Field ending with dot
        ".a",  # Field starting with dot
        "a..b",  # Double dots in middle
    ]

    for invalid_field in invalid_sort_fields:
        with pytest.raises((ValueError, InvalidRequest)) as exc_info:
            # This should fail with a validation error, not a ClickHouse jsonpath error
            list(
                client.server.table_query_stream(
                    tsi.TableQueryReq(
                        project_id=get_client_project_id(client),
                        digest=table_ref.digest,
                        sort_by=[SortBy(field=invalid_field, direction="asc")],
                    )
                )
            )
        # The error should be a validation error, not a ClickHouse error
        assert "jsonpath" not in str(exc_info.value).lower()


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
        time.sleep(0.03)
        events.append("A(E):" + str(a))
        return a

    @weave.op
    def op_b(b: int) -> int:
        events.append("B(S):" + str(b))
        time.sleep(0.02)
        res = op_a(b)
        events.append("B(E):" + str(b))
        return res

    @weave.op
    def op_c(c: int) -> int:
        events.append("C(S):" + str(c))
        time.sleep(0.01)
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

    # now get summary
    calls2 = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "summary"],
        )
    )
    calls2 = list(calls2)
    assert len(calls2) == 2
    # assert derived summary fields are included when getting summary
    assert calls2[0].summary["weave"]["status"] == "success"
    assert isinstance(calls2[0].summary["weave"]["latency_ms"], int)
    assert calls2[0].summary["weave"]["trace_name"] == "calculate"
    # this means other fields on the call should be set
    assert calls2[0].started_at is not None
    assert calls2[0].ended_at is not None
    assert calls2[0].op_name is not None
    # but not other big fields
    assert calls2[0].attributes == {}
    assert calls2[0].inputs == {}
    assert calls2[0].output is None


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
    # Costs should be None because we don't have a cost entry for test_model
    assert calls[0].summary.get("weave").get("costs") is None

    client.add_cost(
        "test_model",
        Decimal("0.00001"),
        Decimal("0.00003"),
        datetime.datetime.now(tz=datetime.timezone.utc),
    )

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

    # also assert that derived summary fields are included when getting costs
    assert calls[0].summary["weave"]["status"] == "success"
    assert calls[0].summary["weave"]["latency_ms"] > 0
    assert "calculate" in calls[0].summary["weave"]["trace_name"]

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


def test_read_call_start_with_cost(client):
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    project_id = client._project_id()
    call_id = generate_id()
    trace_id = generate_id()
    llm_id = "test-model-v1"  # Price needed for potential joins, even if no usage
    start_time = datetime.datetime.now(tz=datetime.timezone.utc)
    price_effective_date = start_time - datetime.timedelta(days=1)

    # --- 1. Insert Prerequisite Data ---
    cost_data = {
        llm_id: {
            "prompt_token_cost": Decimal("0.00001"),  # Cost per token
            "completion_token_cost": Decimal("0.00003"),  # Cost per token
            "effective_date": price_effective_date,
        }
    }
    cost_res = client.server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs=cost_data,
            wb_user_id="test_user",  # Assuming a user ID is needed
        )
    )
    price_id = cost_res.ids[0][0]

    # Insert a call record with summary_dump=None
    call_start_data = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name="test_op_null_summary",
        display_name="Test Operation Null Summary",
        started_at=start_time,
        inputs={"arg1": "no summary"},
        summary_dump=None,  # Explicitly set to None
        attributes={},
    )
    client.server.call_start(tsi.CallStartReq(start=call_start_data))

    # --- 2. Call call_read with include_costs=True ---
    res = client.server.call_read(
        tsi.CallReadReq(
            project_id=project_id,
            id=call_id,
            include_costs=True,  # Request cost calculation
        )
    )

    # --- 3. Assert Results ---
    assert res.call is not None, "Expected call record to be found"
    assert res.call.id == call_id

    # The summary dump should exist but be null or an empty object initially.
    # The cost query should handle this gracefully and *not* add a costs object.
    summary = res.call.summary
    assert isinstance(summary, dict), "Expected summary_dump to be a dictionary"

    if summary is None:
        # If call_read returns None summary, this is fine for this case.
        pass
    elif isinstance(summary, dict):
        # Check that the costs object was NOT added
        assert COST_OBJECT_NAME not in summary.get("weave", {}), (
            f"Did not expect '{COST_OBJECT_NAME}' key in summary['weave'] when initial summary was null/empty"
        )
    else:
        pytest.fail(f"summary_dump was not None or dict: {type(summary)} {summary}")

    # --- 4. Cleanup ---
    client.server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_id])
    )
    client.purge_costs(price_id)


def test_call_read_with_unkown_llm(client):
    """Tests that if an op reports usage for an LLM ID that has no cost entry
    in the database, the cost calculation handles it gracefully (by not adding cost info).
    """
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    # Generate a unique LLM ID unlikely to exist
    llm_id_no_cost = f"non_existent_llm_{generate_id()}"

    @weave.op
    def op_with_usage_no_cost(input_val: int) -> dict[str, Any]:
        usage_details = {
            "requests": 1,
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        }
        # WeaveClient should automatically extract 'usage' from the return dict
        # and place it into the call's summary.
        return {
            "output_val": input_val * 3,
            "usage": usage_details,
            "model": llm_id_no_cost,
        }

    op_with_usage_no_cost(10)

    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["id", "summary", "output_dump"],
            include_costs=True,
        )
    )
    calls = list(calls)
    assert len(calls) == 1
    assert calls[0].output["output_val"] == 30
    assert calls[0].summary is not None

    summary = calls[0].summary
    # Basic checks on the summary
    assert summary is not None
    assert "usage" in summary
    assert llm_id_no_cost in summary["usage"]
    assert summary["usage"][llm_id_no_cost]["prompt_tokens"] == 15

    # Check the cost calculation part
    assert "weave" in summary
    assert "costs" not in summary["weave"]


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

    for first, _last, sort_by in [
        (0, 21, [SortBy(field="inputs.val.a.b.c.d", direction="asc")]),
        (21, 0, [SortBy(field="inputs.val.a.b.c.d", direction="desc")]),
        (0, 21, [SortBy(field="output.a.b.c.d", direction="asc")]),
        (21, 0, [SortBy(field="output.a.b.c.d", direction="desc")]),
    ]:
        inner_res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=sort_by,
            )
        )

        assert inner_res.calls[0].inputs["label"] == first
        assert inner_res.calls[1].inputs["label"] == first

    for _first, _last, count, query in [
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
                    "sort_by": [SortBy(field="inputs.val.a.b.c.d", direction="asc")],
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
        call = require_current_call()

        # allowed in this context
        call.attributes["test"] = 123

        with pytest.raises(KeyError):
            call.attributes["weave"] = {"anything": "blah"}

        with pytest.raises(KeyError):
            call.attributes["weave"]["anything"] = "blah"

        return 1

    _, call = test.call()

    with pytest.raises(TypeError):
        call.attributes["test"] = 123

    with pytest.raises(TypeError):
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
    for _ in range(3):
        start_time = time.time()
        c = calls[0]
        end_time = time.time()
        elapsed_times.append(end_time - start_time)

    # cached lookup should be way faster!
    if sys.platform == "win32":  # Test on windows is slower...
        assert elapsed_times[0] > elapsed_times[1]
        assert elapsed_times[0] > elapsed_times[2]
    else:
        # Use 3x threshold instead of 10x to reduce flakiness while still verifying caching
        assert elapsed_times[0] > elapsed_times[1] * 3
        assert elapsed_times[0] > elapsed_times[2] * 3


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
    if sys.platform == "win32":  # Test on windows is slower...
        assert elapsed_time1 > elapsed_time2
        assert elapsed_time1 > elapsed_time3
    else:
        # Use 3x threshold instead of 10x to reduce flakiness while still verifying caching
        assert elapsed_time1 > elapsed_time2 * 3
        assert elapsed_time1 > elapsed_time3 * 3


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
    assert isinstance(expected_predict_op, str)
    assert expected_predict_op.startswith("weave:///")


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

    call_result = next(iter(res))
    assert call_result.output == nested_ref.uri()

    # output is dereffed
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output"],
            expand_columns=["output"],
        )
    )

    call_result = next(iter(res))
    assert call_result.output["b"] == simple_ref.uri()

    # expand 2 refs, should be {"b": {"a": ref}}
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output.b"],
            expand_columns=["output", "output.b"],
        )
    )
    call_result = next(iter(res))
    assert call_result.output["b"]["a"] == ref.uri()

    # expand 3 refs, should be {"b": {"a": {"id": 123}}}
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output.b.a"],
            expand_columns=["output", "output.b", "output.b.a"],
        )
    )
    call_result = next(iter(res))
    assert call_result.output["b"]["a"]["id"] == "123"

    # incomplete expansion columns, output should be un expanded
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output"],
            expand_columns=["output.b"],
        )
    )
    call_result = next(iter(res))
    assert call_result.output == nested_ref.uri()

    # non-existent column, should be un expanded
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            columns=["output.b.a"],
            expand_columns=["output.b", "output.zzzz"],
        )
    )
    call_result = next(iter(res))
    assert call_result.output == nested_ref.uri()


# Batch size is dynamically increased from 10 to MAX_CALLS_STREAM_BATCH_SIZE (500)
# in clickhouse_trace_server_settings.py, this test verifies that the dynamic
# increase works as expected
@pytest.mark.parametrize("batch_size", [1, 5, 6])
def test_calls_stream_column_expansion_dynamic_batch_size(
    client, batch_size, monkeypatch
):
    monkeypatch.setattr(
        "weave.trace_server.clickhouse_trace_server_settings.INITIAL_CALLS_STREAM_BATCH_SIZE",
        1,
    )
    monkeypatch.setattr(
        "weave.trace_server.clickhouse_trace_server_settings.MAX_CALLS_STREAM_BATCH_SIZE",
        5,
    )

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
    with pytest.raises(CHValidationError):
        client.server.obj_create(create_req)


chars = "+_(){}|\"'<>!@$^&*#:,.[]-=;~`"


def test_objects_and_keys_with_special_characters(client):
    # make sure to include ":", "/" which are URI-related

    name_with_special_characters = "n-a_m.e: /" + chars + "100"
    dict_payload = {name_with_special_characters: "hello world"}

    obj = Custom(name=name_with_special_characters, val=dict_payload)

    weave.publish(obj)
    assert obj.ref is not None

    entity, project = from_project_id(client._project_id())
    project_id = to_project_id(entity, project)
    ref_base = f"weave:///{project_id}"
    exp_name = sanitize_object_name(name_with_special_characters)
    assert exp_name == "n-a_m.e-100"
    exp_key = extra_value_quoter(name_with_special_characters)
    assert (
        exp_key
        == "n-a_m.e%3A%20%2F%2B_%28%29%7B%7D%7C%22%27%3C%3E%21%40%24%5E%26%2A%23%3A%2C.%5B%5D-%3D%3B~%60100"
    )
    exp_digest = "k8nuYiUMP6VgAP6wMjeY8dRYnMz2lCqlCyzu2F7iFMw"

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

    exp_op_digest = "UsyKRnrEyBIieYPDU6eGrbGJgtXjFVFoR6PEemZma68"
    exp_op_ref = f"{ref_base}/op/{exp_name}:{exp_op_digest}"

    found_ref = test.ref.uri()
    assert found_ref == exp_op_ref
    gotten_fn = weave.ref(found_ref).get()
    assert gotten_fn(obj) == "hello world"


def test_calls_stream_feedback(client):
    batch_size = 10
    num_calls = batch_size + 1

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


def test_large_keys_are_stripped_call(client, caplog, monkeypatch):
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to strip in sqlite
        return

    original_insert_call_batch = weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer._insert_call_batch
    max_size = 10 * 1024

    # Patch _insert_call_batch to raise InsertTooLarge
    def mock_insert_call_batch(self, batch):
        # mock raise insert error
        if len(str(batch)) > max_size:
            raise InsertTooLarge(
                "Database insertion failed. Record too large. "
                "A likely cause is that a single row or cell exceeded "
                "the limit. If logging images, save them as `Image.PIL`."
            )
        original_insert_call_batch(self, batch)

    monkeypatch.setattr(
        weave.trace_server.clickhouse_trace_server_settings,
        "CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT",
        max_size,
    )
    monkeypatch.setattr(
        weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer,
        "_insert_call_batch",
        mock_insert_call_batch,
    )

    # Use a dictionary that will exceed our new 10KB limit
    data = {"dictionary": {f"{i}": i for i in range(max_size // 10)}}

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

    # test that when inputs + output > max_size but input < max_size
    # we only strip the inputs
    smaller_data = {"dictionary": {f"{i}": i for i in range(max_size // 16)}}

    @weave.op
    def test_op_strip_inputs(input_data: dict):
        # combined output is larger than single row size
        return {"output1": input_data, "output2": smaller_data}

    def _compare_inputs(inputs, expected):
        for k, v in expected.items():
            assert inputs[k] == v

    test_op_strip_inputs(smaller_data)

    calls = list(test_op_strip_inputs.calls())
    assert len(calls) == 1
    assert calls[0].output == json.loads(ENTITY_TOO_LARGE_PAYLOAD)
    _compare_inputs(calls[0].inputs, {"input_data": smaller_data})

    # test when inputs + output + attributes > max_size and attributes is largest
    # we strip the attributes
    @weave.op
    def test_op_strip_summary(input_data: dict):
        return "really_small"

    with weave.attributes({"slightly_larger_data": smaller_data | {"a": 1}}):
        test_op_strip_summary(smaller_data)

    call = next(iter(test_op_strip_summary.calls()))
    assert call.attributes == json.loads(ENTITY_TOO_LARGE_PAYLOAD)
    assert call.output == "really_small"
    _compare_inputs(call.inputs, {"input_data": smaller_data})

    # Test case where we have a batch with mixed sizes - some calls need stripping, some don't
    # This ensures we hit the lines where total_json_bytes <= limit (lines 2355-2357)
    # for items that don't need stripping within a batch that overall needs stripping

    @weave.op
    def test_op_mixed_batch_small(input_data: str):
        return input_data

    @weave.op
    def test_op_mixed_batch_large(input_data: dict):
        return {"large_output": input_data}

    # Create a small call that fits under the limit
    test_op_mixed_batch_small("tiny data")

    # Create a large call that needs stripping
    large_data = {"dictionary": {f"{i}": i for i in range(max_size // 10)}}
    test_op_mixed_batch_large(large_data)

    # Create another small call
    test_op_mixed_batch_small("another tiny piece")

    # Flush to ensure they're in the same batch
    client.flush()

    # Check that the small calls preserved their data while the large one was stripped
    small_calls = list(test_op_mixed_batch_small.calls())
    assert len(small_calls) == 2
    assert small_calls[0].output == "tiny data"
    assert small_calls[0].inputs == {"input_data": "tiny data"}
    assert small_calls[1].output == "another tiny piece"
    assert small_calls[1].inputs == {"input_data": "another tiny piece"}

    large_calls = list(test_op_mixed_batch_large.calls())
    assert len(large_calls) == 1
    # The large call should have been stripped
    assert large_calls[0].output == json.loads(ENTITY_TOO_LARGE_PAYLOAD)
    assert large_calls[0].inputs == json.loads(ENTITY_TOO_LARGE_PAYLOAD)


def test_weave_finish_unsets_client(client, monkeypatch):
    @weave.op
    def foo():
        return 1

    set_weave_client_global(client)
    weave_client = get_weave_client()
    assert get_weave_client() is not None

    finish_called = False
    original_finish = weave_client.finish

    def tracked_finish(*args, **kwargs):
        nonlocal finish_called
        finish_called = True
        return original_finish(*args, **kwargs)

    monkeypatch.setattr(weave_client, "finish", tracked_finish)

    foo()
    assert len(list(weave_client.get_calls())) == 1

    weave.finish()
    assert finish_called

    foo()
    assert len(list(weave_client.get_calls())) == 1
    assert get_weave_client() is None


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


def test_op_sampling_inheritance_generator(client):
    parent_calls = 0
    child_calls = 0

    @weave.op
    def child_op(x: int) -> int:
        nonlocal child_calls
        child_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=0.0)
    def parent_op(x: int):
        nonlocal parent_calls
        parent_calls += 1
        yield child_op(x)

    # When parent is sampled out, child should execute but also remain untraced.
    for i in range(10):
        assert list(parent_op(i)) == [i + 1]

    assert parent_calls == 10
    assert child_calls == 10
    assert len(client.get_calls()) == 0


@pytest.mark.asyncio
async def test_op_sampling_inheritance_async_generator(client):
    parent_calls = 0
    child_calls = 0

    @weave.op
    async def child_op(x: int) -> int:
        nonlocal child_calls
        child_calls += 1
        return x + 1

    @weave.op(tracing_sample_rate=0.0)
    async def parent_op(x: int):
        nonlocal parent_calls
        parent_calls += 1
        yield await child_op(x)

    # When parent is sampled out, child should execute but also remain untraced.
    for i in range(10):
        assert [item async for item in parent_op(i)] == [i + 1]

    assert parent_calls == 10
    assert child_calls == 10
    assert len(client.get_calls()) == 0


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

    num_runs = 5
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
    assert res[0].output["d"] == 5


def test_call_stream_query_heavy_query_batch(client):
    # start 10 calls
    call_ids = []
    project_id = get_client_project_id(client)
    for _ in range(10):
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
            attributes={"a": 5, "empty": "", "null": None},
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
            output={"d": 5, "e": "f", "result": {"message": "completed"}},
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
    assert len(list(res)) == 10
    for call in res:
        assert call.attributes["a"] == 5

    # now query for inputs by string. This should be okay,
    # because we don't filter out started_at is NULL
    input_string_query = {
        "project_id": project_id,
        "query": {
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.param.value1"},
                            {"$literal": "hello"},
                        ]
                    },
                    {
                        "$contains": {
                            "input": {"$getField": "output.result.message"},
                            "substr": {"$literal": "COMPleted"},
                            "case_insensitive": True,
                        }
                    },
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
        assert call.output["result"]["message"] == "COMPLETED"

    # Now lets add a light filter, which
    # changes how we filter out calls. Make sure that still works
    input_string_query["filter"] = {"op_names": ["test_name"]}
    res = client.server.calls_query_stream(
        tsi.CallsQueryReq.model_validate(input_string_query)
    )
    assert len(list(res)) == 10
    for call in res:
        assert call.inputs["param"]["value1"] == "helslo"
        assert call.output["d"] == 5

    # now try to filter by the empty attribute string
    query = {
        "project_id": project_id,
        "query": {
            "$expr": {"$eq": [{"$getField": "attributes.empty"}, {"$literal": ""}]}
        },
    }
    res = client.server.calls_query_stream(tsi.CallsQueryReq.model_validate(query))
    assert len(list(res)) == 10
    for call in res:
        assert call.attributes["empty"] == ""


@pytest.fixture
def clickhouse_client(client):
    if client_is_sqlite(client):
        return None
    return client.server._next_trace_server.ch_client


def test_calls_query_with_storage_size_clickhouse(client, clickhouse_client):
    """Test querying calls with storage size information."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    @weave.op
    def test_op(x: dict):
        return x

    # Create a call with some data
    result = test_op({"data": "x" * 1000})

    # This is a best effort to achive consistency in the calls_merged_stats table.
    # due to some race condition/optimizations in clickhouse, there is a chance
    # that the calls_merged_stats table is not updated in time for the query below
    # to return the correct results.
    clickhouse_client.command(
        "OPTIMIZE TABLE calls_merged_stats FINAL",
    )

    # Query with storage size
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client), include_storage_size=True
            )
        )
    )
    assert len(calls) == 1
    call = calls[0]

    # Verify storage size is present, despite that the race condition
    # that the calls_merged_stats table is not updated in time, and we are unable to
    # verify the value against an expected value.
    assert call.storage_size_bytes is not None


def test_calls_query_with_total_storage_size_clickhouse(client, clickhouse_client):
    """Test querying calls with total storage size."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    @weave.op
    def parent_op(x: dict):
        return child_op(x)  # Call child op to create a trace

    @weave.op
    def child_op(x: dict):
        return x

    # Create a call with nested structure
    parent_op({"data": "x" * 1000})

    # This is a best effort to achive consistency in the calls_merged_stats table.
    # due to some race condition/optimizations in clickhouse, there is a chance
    # that the calls_merged_stats table is not updated in time for the query below
    # to return the correct results.
    clickhouse_client.command(
        "OPTIMIZE TABLE calls_merged_stats FINAL",
    )

    # Query with total storage size
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                include_total_storage_size=True,
            )
        )
    )
    assert len(calls) == 2  # Parent and child calls

    # Find parent and child calls
    parent_call = next(c for c in calls if c.parent_id is None)
    child_call = next(c for c in calls if c.parent_id is not None)

    # Verify that both parent and child calls are present
    assert parent_call is not None
    assert child_call is not None

    # Verify the total storage size is present, despite that the race condition
    # that the calls_merged_stats table is not updated in time, and we are unable to
    # verify the value against an expected value.
    assert (
        parent_call.total_storage_size_bytes is not None
    )  # Parent should have total size
    assert child_call.storage_size_bytes is None
    assert (
        child_call.total_storage_size_bytes is None
    )  # Child should not have total size


def test_calls_query_with_both_storage_sizes_clickhouse(client, clickhouse_client):
    """Test querying calls with total storage size."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    @weave.op
    def parent_op(x: dict):
        return child_op(x)  # Call child op to create a trace

    @weave.op
    def child_op(x: dict):
        return x

    # Create a call with nested structure
    parent_op({"data": "x" * 1000})

    # This is a best effort to achive consistency in the calls_merged_stats table.
    # due to some race condition/optimizations in clickhouse, there is a chance
    # that the calls_merged_stats table is not updated in time for the query below
    # to return the correct results.
    clickhouse_client.command(
        "OPTIMIZE TABLE calls_merged_stats FINAL",
    )

    # Query with total storage size
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                include_storage_size=True,
                include_total_storage_size=True,
            )
        )
    )

    assert len(calls) == 2  # Parent and child calls

    # Find parent and child calls
    parent_call = next(c for c in calls if c.parent_id is None)
    child_call = next(c for c in calls if c.parent_id is not None)

    # Verify that both parent and child calls are present
    assert parent_call is not None
    assert child_call is not None

    # Verify the storage sizes are present, despite that the race condition
    # that the calls_merged_stats table is not updated in time, and we are unable to
    # verify the value against an expected value.
    assert parent_call.storage_size_bytes is not None
    assert parent_call.total_storage_size_bytes is not None
    assert child_call.storage_size_bytes is not None
    # Child should not have total size
    assert child_call.total_storage_size_bytes is None


def test_calls_hydrated(client):
    nested = {"hi": {"there": {"foo": "bar"}}}
    nested_ref = weave.publish(nested)

    @weave.op
    def nest(input_ref: str):
        my_obj = {
            "woahhhh": input_ref,
        }
        ref = weave.publish(my_obj)
        return ref

    nest(nested_ref)
    nest(nested_ref)
    nest(nested_ref)

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                columns=["inputs", "output", "output.woahhhh"],
                expand_columns=[
                    "inputs",
                    "inputs.input_ref",
                    "output",
                    "output.woahhhh",
                ],
            )
        )
    )

    assert len(calls) == 3
    assert calls[0].output["woahhhh"]["hi"]["there"]["foo"] == "bar"
    assert calls[0].inputs["input_ref"]["hi"]["there"]["foo"] == "bar"
    assert calls[1].output["woahhhh"]["hi"]["there"]["foo"] == "bar"
    assert calls[1].inputs["input_ref"]["hi"]["there"]["foo"] == "bar"
    assert calls[2].output["woahhhh"]["hi"]["there"]["foo"] == "bar"
    assert calls[2].inputs["input_ref"]["hi"]["there"]["foo"] == "bar"


def test_obj_query_with_storage_size_clickhouse(client):
    """Test querying objects with storage size information."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    # Create a test object with some data to ensure it has size
    dataset = weave.Dataset(name="test_dataset", rows=[{"key": "value" * 1000}])
    weave.publish(dataset)

    # Query the object with storage size included
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
            include_storage_size=True,
            filter={"object_ids": ["test_dataset"]},
        )
    )

    assert len(res.objs) == 1
    queried_obj = res.objs[0]

    # Verify that storage size is present
    assert queried_obj.size_bytes is not None
    assert queried_obj.size_bytes == 257  # Should have some size due to the test data

    # Test that a table is created and its size is correct
    table_ref = TableRef.parse_uri(queried_obj.val["rows"])
    res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client._project_id(),
            digests=[table_ref.digest],
            include_storage_size=True,
        )
    )

    assert res.tables[0].storage_size_bytes == 5011

    # Query without storage size (default behavior)
    res_without_size = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=get_client_project_id(client),
            filter={"object_ids": ["test_dataset"]},
        )
    )

    assert len(res_without_size.objs) == 1
    queried_obj_without_size = res_without_size.objs[0]

    # Verify that storage size is not included when not requested
    assert queried_obj_without_size.size_bytes is None


def test_call_query_stream_with_costs_and_storage_size(client, clickhouse_client):
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    @weave.op
    def child_op(a: int, b: int) -> dict[str, Any]:
        return {
            "result": {"a + b": a + b},
            "not result": 123,
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            "model": "test_model",
        }

    @weave.op
    def parent_op(x: dict):
        return child_op(x["a"], x["b"])  # Call child op to create a trace

    parent_op({"a": 1, "b": 2})

    # This is a best effort to achive consistency in the calls_merged_stats table.
    # due to some race condition/optimizations in clickhouse, there is a chance
    # that the calls_merged_stats table is not updated in time for the query below
    # to return the correct results.
    clickhouse_client.command(
        "OPTIMIZE TABLE calls_merged FINAL",
    )
    clickhouse_client.command(
        "OPTIMIZE TABLE calls_merged_stats FINAL",
    )

    # Test that "include_costs" and "include_total_storage_size" can be used together
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                columns=["id", "summary", "total_storage_size_bytes"],
                include_costs=True,
                include_total_storage_size=True,
            )
        )
    )

    assert len(calls) == 2

    # Find parent and child calls
    parent_call = next(c for c in calls if "parent_op" in c.op_name)
    child_call = next(c for c in calls if "child_op" in c.op_name)

    # Verify that both parent and child calls are present
    assert parent_call is not None
    assert child_call is not None

    assert parent_call.summary["usage"] is not None
    assert child_call.summary["usage"] is not None

    assert parent_call.total_storage_size_bytes is not None
    assert child_call.storage_size_bytes is None


def test_call_query_stream_with_invalid_filter_field(client):
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    with pytest.raises(InvalidFieldError):
        res = get_client_trace_server(client).calls_query(
            tsi.CallsQueryReq.model_validate(
                {
                    "project_id": get_client_project_id(client),
                    "query": {
                        "$expr": {
                            "$contains": {
                                "input": {"$getField": "total_storage_size_bytes"},
                                "substr": {"$literal": "2025-04-11T05:56:12.957Z"},
                            }
                        }
                    },
                }
            )
        )


@pytest.mark.parametrize(
    "obj",
    [
        weave.Dataset(rows=[{"a": 1, "b": 2}]),
        weave.Evaluation(dataset=weave.Dataset(rows=[{"a": 1, "b": 2}])),
    ],
)
def test_get_object_from_uri(client, obj):
    ref = weave.publish(obj)
    uri = ref.uri()

    assert weave.get(uri) == obj


def test_get_object_from_uri_non_registered_object(client):
    class MyModel(weave.Model):
        a: int
        b: float = 2.0

        @weave.op
        def predict(self, x: int) -> int:
            return x + 1

    model = MyModel(name="example", description="fancy", a=1)
    ref = weave.publish(model)
    uri = ref.uri()

    res = weave.get(uri)
    assert res.name == "example"
    assert res.description == "fancy"
    assert res.a == 1
    assert res.b == 2.0
    assert res._class_name == "MyModel"
    assert res._bases == ["Model", "Object", "BaseModel"]
    assert res.predict(5) == 6


def test_dedupe_ref_in_calls_stream(client):
    nested_obj = {"nested": 123}
    nested_ref = weave.publish(nested_obj)

    obj = {
        "my_dataset1": nested_ref,
        "my_dataset2": nested_ref,
        "my_dataset3": nested_ref,
        "my_dataset4": nested_ref,
        "my_dataset5": nested_ref,
        "ref_list": {
            "1": nested_ref,
            "2": nested_ref,
            "3": nested_ref,
        },
    }
    obj_ref = weave.publish(obj)

    @weave.op
    def log():
        return obj_ref

    log()

    def call_stream(columns, expand_columns):
        return list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=client._project_id(),
                    columns=columns,
                    expand_columns=expand_columns,
                )
            )
        )

    calls_hydrated = call_stream(columns=["output"], expand_columns=["output"])
    assert len(calls_hydrated) == 1
    assert calls_hydrated[0].output == {
        "_ref": obj_ref.uri(),
        "my_dataset1": nested_ref.uri(),
        "my_dataset2": nested_ref.uri(),
        "my_dataset3": nested_ref.uri(),
        "my_dataset4": nested_ref.uri(),
        "my_dataset5": nested_ref.uri(),
        "ref_list": {
            "1": nested_ref.uri(),
            "2": nested_ref.uri(),
            "3": nested_ref.uri(),
        },
    }

    cols = [
        "output",
        "output.my_dataset1",
        "output.my_dataset2",
        "output.my_dataset3",
        "output.my_dataset4",
        "output.my_dataset5",
        "output.ref_list",
        "output.ref_list.1",
        "output.ref_list.2",
        "output.ref_list.3",
    ]
    nested_obj_with_ref = {"nested": 123, "_ref": nested_ref.uri()}
    calls_all_columns = call_stream(columns=cols, expand_columns=cols)
    assert len(calls_all_columns) == 1
    assert calls_all_columns[0].output["my_dataset1"] == nested_obj_with_ref
    assert calls_all_columns[0].output["my_dataset2"] == nested_obj_with_ref
    assert calls_all_columns[0].output["my_dataset3"] == nested_obj_with_ref
    assert calls_all_columns[0].output["my_dataset4"] == nested_obj_with_ref
    assert calls_all_columns[0].output["my_dataset5"] == nested_obj_with_ref
    assert calls_all_columns[0].output["ref_list"] == {
        "1": nested_obj_with_ref,
        "2": nested_obj_with_ref,
        "3": nested_obj_with_ref,
    }


def test_calls_query_stats_with_limit(client):
    def calls_stats(limit=None, filter=None, include_total_storage_size=False):
        return client.server.calls_query_stats(
            tsi.CallsQueryStatsReq(
                project_id=get_client_project_id(client),
                limit=limit,
                filter=filter,
                include_total_storage_size=include_total_storage_size,
            )
        )

    @weave.op
    def child_op():
        return 1

    @weave.op
    def parent_op():
        return child_op()

    assert calls_stats().count == 0

    parent_op()
    assert calls_stats().count == 2

    trace_id = client.get_calls()[0].trace_id

    # test limit, uses special optimization
    assert calls_stats(limit=1).count == 1
    # test limit, does not use special optimization
    assert calls_stats(limit=2).count == 2
    # test limit and filter, should use limit but not special optimization
    assert calls_stats(limit=1, filter={"trace_roots_only": True}).count == 1
    # test filter, should not use special optimization
    assert calls_stats(filter={"trace_ids": [trace_id]}).count == 2

    with pytest.raises(ValueError):
        calls_stats(limit=-1)

    # Test that the query works with include_total_storage_size
    result = calls_stats(limit=1, include_total_storage_size=True)
    assert result.count == 1
    assert result.total_storage_size_bytes is not None


@pytest.mark.parametrize(
    "thread_ids",
    [
        ["thread_does_not_exist"],  # single thread id that does not match
        ["thread_exists_no_calls"],  # thread exists but has zero calls
        [],  # empty list -> no threads -> 0 calls
    ],
)
def test_calls_query_stats_thread_ids_filter_not_minimal(client, thread_ids):
    """Ensure that we do not optimize away the thread_ids filter when it is present."""
    client.set_wandb_run_context(run_id="stats-thread-run", step=0)

    @weave.op
    def stats_thread_op() -> int:
        return 1

    # Create calls in one thread (so project has calls with wb_run_id; optimized path would return 1)
    with weave.thread("thread_with_calls"):
        stats_thread_op()
        stats_thread_op()

    # Thread that exists but has zero calls (ensures we test this distinct case)
    with weave.thread("thread_exists_no_calls"):
        pass

    # A query is required to exercise the "Pattern 2" check in _try_optimized_stats_query.
    # Use a query that matches the created calls (wb_run_id not null).
    wb_run_id_not_null_query = tsi.Query(
        **{
            "$expr": {
                "$not": [{"$eq": [{"$getField": "wb_run_id"}, {"$literal": None}]}]
            }
        }
    )
    # Confirm that this query returns results, so we can test filtering with the second query below.
    res_with_matching_thread = client.server.calls_query_stats(
        tsi.CallsQueryStatsReq(
            project_id=get_client_project_id(client),
            limit=1,
            query=wb_run_id_not_null_query,
            filter=tsi.CallsFilter(thread_ids=["thread_with_calls"]),
        )
    )
    assert res_with_matching_thread.count == 1

    # Query with thread_ids that match zero calls. Full path -> 0. Incorrectly choosing the optimized path -> 1.
    res = client.server.calls_query_stats(
        tsi.CallsQueryStatsReq(
            project_id=get_client_project_id(client),
            limit=1,
            query=wb_run_id_not_null_query,
            filter=tsi.CallsFilter(thread_ids=thread_ids),
        )
    )
    assert res.count == 0


def test_calls_query_thread_ids_filter_returns_matching_thread(client):
    """Create 3 threads, request the second one, assert the returned call has the correct thread_id."""
    client.set_wandb_run_context(run_id="thread-filter-run", step=0)

    @weave.op
    def thread_op() -> int:
        return 1

    thread_1, thread_2, thread_3 = "thread_first", "thread_second", "thread_third"
    with weave.thread(thread_1):
        thread_op()
    with weave.thread(thread_2):
        thread_op()
    with weave.thread(thread_3):
        thread_op()

    # Use a query that matches the created calls (wb_run_id not null).
    wb_run_id_not_null_query = tsi.Query(
        **{
            "$expr": {
                "$not": [{"$eq": [{"$getField": "wb_run_id"}, {"$literal": None}]}]
            }
        }
    )
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=get_client_project_id(client),
            limit=1,
            query=wb_run_id_not_null_query,
            filter=tsi.CallsFilter(thread_ids=[thread_2]),
        )
    )
    assert len(res.calls) == 1
    assert res.calls[0].thread_id == thread_2


def test_calls_query_stats_total_storage_size_clickhouse(client, clickhouse_client):
    """Test querying calls with total storage size."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    @weave.op
    def parent_op(x: dict):
        return child_op(x)  # Call child op to create a trace

    @weave.op
    def child_op(x: dict):
        return x

    # Create a call with nested structure
    parent_op({"data": "x" * 1000})

    # This is a best effort to achive consistency in the calls_merged_stats table.
    # due to some race condition/optimizations in clickhouse, there is a chance
    # that the calls_merged_stats table is not updated in time for the query below
    # to return the correct results.
    clickhouse_client.command(
        "OPTIMIZE TABLE calls_merged_stats FINAL",
    )

    # Query with total storage size
    result = client.server.calls_query_stats(
        tsi.CallsQueryStatsReq(
            project_id=get_client_project_id(client),
            include_total_storage_size=True,
        )
    )

    print(result)
    assert result is not None
    assert result.count == 2
    # Unfortunate that we can't assert the exact value here, because of the
    # uncertainty of the clickhouse materialized view merging moment.
    assert result.total_storage_size_bytes is not None


def test_project_stats_clickhouse(client, clickhouse_client):
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    project_id = get_client_project_id(client)
    internal_project_id = DummyIdConverter().ext_to_int_project_id(project_id)

    # Insert test data directly into stats tables
    attr_size = 100
    inputs_size = 200
    output_size = 300
    summary_size = 400
    trace_size = attr_size + inputs_size + output_size + summary_size
    object_size = 5678
    file_size = 4321
    table_size = 1234  # New test data for table storage size

    # Insert a row into calls_merged to establish project data residence
    # This ensures the table routing resolver routes to calls_merged_stats
    clickhouse_client.command(
        f"""
        INSERT INTO calls_merged (project_id, id, op_name, started_at, trace_id,
                                  parent_id, attributes_dump, inputs_dump, output_dump, summary_dump)
        VALUES ('{internal_project_id}', '{uuid.uuid4()}', 'test_op', now(), '{uuid.uuid4()}',
                '', '{{}}', '{{}}', 'null', '{{}}')
        """
    )

    # directly insert into stats tables to avoid materialized views's consistency issue
    # Insert into calls_merged_stats
    clickhouse_client.command(
        f"INSERT INTO calls_merged_stats (project_id, attributes_size_bytes, inputs_size_bytes, output_size_bytes, summary_size_bytes) "
        f"VALUES ('{internal_project_id}', {attr_size}, {inputs_size}, {output_size}, {summary_size})"
    )
    # Insert into object_versions_stats
    clickhouse_client.command(
        f"INSERT INTO object_versions_stats (project_id, size_bytes) VALUES ('{internal_project_id}', {object_size})"
    )
    # Insert into files_stats
    clickhouse_client.command(
        f"INSERT INTO files_stats (project_id, size_bytes) VALUES ('{internal_project_id}', {file_size})"
    )
    # Insert into table_rows_stats
    clickhouse_client.command(
        f"INSERT INTO table_rows_stats (project_id, size_bytes) VALUES ('{internal_project_id}', {table_size})"
    )

    # Query project stats with all storage sizes included
    res = client.server.project_stats(tsi.ProjectStatsReq(project_id=project_id))

    # Assert the result fields match the inserted values
    assert res.trace_storage_size_bytes == trace_size
    assert res.objects_storage_size_bytes == object_size
    assert res.tables_storage_size_bytes == table_size
    assert res.files_storage_size_bytes == file_size

    # test that requesting with none of the include_* params returns an error
    with pytest.raises(ValueError):
        client.server.project_stats(
            tsi.ProjectStatsReq(
                project_id=project_id,
                include_trace_storage_size=False,
                include_object_storage_size=False,
                include_table_storage_size=False,
                include_file_storage_size=False,
            )
        )


def test_calls_query_with_descendant_error(client):
    class TestException(Exception):
        pass

    @weave.op
    def child_op(val: int):
        if val == 0:
            raise TestException("Error")
        return val

    @weave.op
    def parent_op(val: int):
        if val == 1:
            raise TestException("Error")
        try:
            return child_op(val)
        except TestException as e:
            return val

    try:
        parent_op(0)
    except TestException as e:
        pass

    try:
        parent_op(1)
    except TestException as e:
        pass

    try:
        parent_op(2)
    except TestException as e:
        pass

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[{"field": "started_at", "direction": "asc"}],
            )
        )
    )

    assert len(calls) == 5
    assert "parent_op" in calls[0].op_name
    assert calls[0].inputs["val"] == 0
    assert calls[0].summary["weave"]["status"] == tsi.TraceStatus.DESCENDANT_ERROR

    assert "child_op" in calls[1].op_name
    assert calls[1].inputs["val"] == 0
    assert calls[1].summary["weave"]["status"] == tsi.TraceStatus.ERROR

    assert "parent_op" in calls[2].op_name
    assert calls[2].inputs["val"] == 1
    assert calls[2].summary["weave"]["status"] == tsi.TraceStatus.ERROR

    assert "parent_op" in calls[3].op_name
    assert calls[3].inputs["val"] == 2
    assert calls[3].summary["weave"]["status"] == tsi.TraceStatus.SUCCESS

    assert "child_op" in calls[4].op_name
    assert calls[4].inputs["val"] == 2
    assert calls[4].summary["weave"]["status"] == tsi.TraceStatus.SUCCESS

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[{"field": "summary.weave.status", "direction": "asc"}],
            )
        )
    )

    assert len(calls) == 5
    assert [c.summary["weave"]["status"] for c in calls] == [
        tsi.TraceStatus.DESCENDANT_ERROR,
        tsi.TraceStatus.ERROR,
        tsi.TraceStatus.ERROR,
        tsi.TraceStatus.SUCCESS,
        tsi.TraceStatus.SUCCESS,
    ]

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[{"field": "summary.weave.status", "direction": "desc"}],
            )
        )
    )

    assert len(calls) == 5
    assert [c.summary["weave"]["status"] for c in calls] == [
        tsi.TraceStatus.SUCCESS,
        tsi.TraceStatus.SUCCESS,
        tsi.TraceStatus.ERROR,
        tsi.TraceStatus.ERROR,
        tsi.TraceStatus.DESCENDANT_ERROR,
    ]

    for status, count in [
        (tsi.TraceStatus.DESCENDANT_ERROR, 1),
        (tsi.TraceStatus.ERROR, 2),
        (tsi.TraceStatus.SUCCESS, 2),
    ]:
        calls = list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=get_client_project_id(client),
                    query={
                        "$expr": {
                            "$eq": [
                                {"$getField": "summary.weave.status"},
                                {"$literal": status},
                            ]
                        }
                    },
                )
            )
        )

        assert len(calls) == count


def test_thread_context_with_weave_api(client):
    """Test thread context using the weave.thread() API with ThreadContext."""
    import weave
    from weave.trace.context import call_context

    # Test default thread_id is None (using internal context for verification)
    assert call_context.get_thread_id() is None

    # Test using weave.thread context manager with ThreadContext
    with weave.thread("api_thread_1") as t:
        # Use ThreadContext object to access thread_id
        assert t.thread_id == "api_thread_1"
        assert (
            call_context.get_thread_id() == "api_thread_1"
        )  # Verify internal consistency

        # Test nested context with ThreadContext
        with weave.thread("api_thread_2") as inner_t:
            assert inner_t.thread_id == "api_thread_2"
            assert t.thread_id == "api_thread_1"  # Outer context unchanged
            assert call_context.get_thread_id() == "api_thread_2"

        # Should revert to parent context
        assert t.thread_id == "api_thread_1"
        assert call_context.get_thread_id() == "api_thread_1"

    # Should revert to None
    assert call_context.get_thread_id() is None


def test_thread_id_in_calls(client):
    """Test that thread_id is properly captured in call records, including auto-generation."""
    import weave

    @weave.op
    def test_op_with_thread(x: int) -> int:
        return x * 2

    @weave.op
    def test_op_without_thread(x: int) -> int:
        return x * 3

    @weave.op
    def test_op_auto_thread(x: int) -> int:
        return x * 4

    # Call without thread context
    result1 = test_op_without_thread(5)
    assert result1 == 15

    # Call with explicit thread context
    with weave.thread("test_thread_id") as t:
        assert t.thread_id == "test_thread_id"
        result2 = test_op_with_thread(5)
        assert result2 == 10

    # Call with auto-generated thread_id
    auto_thread_id = None
    with weave.thread() as t:
        auto_thread_id = t.thread_id
        assert auto_thread_id is not None
        assert isinstance(auto_thread_id, str)
        assert len(auto_thread_id) > 20  # Should be UUID v7
        result3 = test_op_auto_thread(5)
        assert result3 == 20

    # Get the calls to verify thread_id
    calls = client.get_calls()

    # Find our calls (most recent first)
    auto_call = None
    thread_call = None
    no_thread_call = None

    for call in calls:
        if "test_op_auto_thread" in call.op_name:
            auto_call = call
        elif "test_op_with_thread" in call.op_name:
            thread_call = call
        elif "test_op_without_thread" in call.op_name:
            no_thread_call = call

    assert auto_call is not None
    assert thread_call is not None
    assert no_thread_call is not None

    # Verify thread_id values
    assert auto_call.thread_id == auto_thread_id  # Should match auto-generated ID
    assert thread_call.thread_id == "test_thread_id"
    assert no_thread_call.thread_id is None


def test_thread_id_inheritance(client):
    """Test that thread_id is inherited by child calls, demonstrated via ThreadContext."""
    import weave

    @weave.op
    def child_op(x: int) -> int:
        return x + 1

    @weave.op
    def parent_op(x: int) -> int:
        return child_op(x) * 2

    # Call with thread context, using ThreadContext to demonstrate inheritance
    inherited_thread_id = None
    with weave.thread("inherited_thread") as t:
        inherited_thread_id = t.thread_id
        assert inherited_thread_id == "inherited_thread"

        # Both parent and child calls should inherit this thread_id
        result = parent_op(10)
        assert result == 22  # (10 + 1) * 2

        # ThreadContext shows the current thread_id throughout execution
        assert t.thread_id == "inherited_thread"

    # Get the calls to verify thread_id inheritance
    calls = client.get_calls()

    # Find our calls
    parent_call = None
    child_call = None

    for call in calls:
        if "parent_op" in call.op_name:
            parent_call = call
        elif "child_op" in call.op_name:
            child_call = call

    assert parent_call is not None
    assert child_call is not None

    # Both should have the same thread_id that was shown in ThreadContext
    assert parent_call.thread_id == inherited_thread_id
    assert child_call.thread_id == inherited_thread_id
    assert parent_call.thread_id == "inherited_thread"
    assert child_call.thread_id == "inherited_thread"


def test_thread_id_query_filtering(client):
    """Test that calls can be filtered by thread_id."""
    import weave

    @weave.op
    def query_test_op(value: str) -> str:
        return f"processed_{value}"

    # Create calls with different thread_ids
    with weave.thread("filter_thread_1"):
        query_test_op("value1")

    with weave.thread("filter_thread_2"):
        query_test_op("value2")

    query_test_op("value3")  # No thread context

    # Query calls by thread_id using the server interface
    if hasattr(client.server, "calls_query"):
        # Test filtering by thread_id
        res1 = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                query={
                    "$expr": {
                        "$eq": [
                            {"$getField": "thread_id"},
                            {"$literal": "filter_thread_1"},
                        ]
                    }
                },
            )
        )

        # Should find the call with filter_thread_1
        thread1_calls = [
            call for call in res1.calls if call.thread_id == "filter_thread_1"
        ]
        assert len(thread1_calls) >= 1

        # Query all calls and verify thread_id values
        all_calls_res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
            )
        )

        # Find our test calls by op_name pattern
        our_test_calls = [
            call for call in all_calls_res.calls if "query_test_op" in call.op_name
        ]

        # Verify we have calls with both thread_ids and None
        thread_ids_found = {call.thread_id for call in our_test_calls}
        assert "filter_thread_1" in thread_ids_found, (
            f"Should find filter_thread_1, got: {thread_ids_found}"
        )
        assert "filter_thread_2" in thread_ids_found, (
            f"Should find filter_thread_2, got: {thread_ids_found}"
        )
        assert None in thread_ids_found, (
            f"Should find None thread_id, got: {thread_ids_found}"
        )


def test_get_calls_filter_by_thread_ids_only(client):
    """Test that get_calls with only CallsFilter(thread_ids=[...]) returns just that thread's calls.

    This exercises the path where thread_ids is the sole filter (HardCodedFilter.is_useful()
    """
    unique = uuid.uuid4().hex

    @weave.op
    def thread_filter_op(value: str) -> str:
        return f"out_{value}"

    with weave.thread(f"thread_a_{unique}"):
        thread_filter_op("a1")
        thread_filter_op("a2")

    with weave.thread(f"thread_b_{unique}"):
        thread_filter_op("b1")

    # Filter using only thread_ids (no op_names, trace_ids, etc.)
    calls_thread_a = list(
        client.get_calls(
            filter=tsi.CallsFilter(thread_ids=[f"thread_a_{unique}"]),
            limit=100,
        )
    )

    assert len(calls_thread_a) == 2
    assert all(call.thread_id == f"thread_a_{unique}" for call in calls_thread_a)


def test_thread_context_error_handling(client):
    """Test that ThreadContext is properly managed even when exceptions occur."""
    import weave
    from weave.trace.context import call_context

    @weave.op
    def failing_op(should_fail: bool) -> str:
        if should_fail:
            raise ValueError("Test exception")
        return "success"

    # Test that thread context is properly restored after exception
    assert call_context.get_thread_id() is None

    # Test ThreadContext behavior during exception
    exception_thread_context = None
    try:
        with weave.thread("exception_thread") as t:
            exception_thread_context = t
            assert t.thread_id == "exception_thread"
            assert call_context.get_thread_id() == "exception_thread"
            failing_op(True)  # This will raise an exception
    except ValueError:
        pass  # Expected

    # Verify ThreadContext maintained its state even after exception
    assert exception_thread_context.thread_id == "exception_thread"

    # Thread context should be restored to None after exiting context
    assert call_context.get_thread_id() is None

    # Test successful call after exception with auto-generated thread
    recovery_thread_id = None
    with weave.thread() as t:  # Use auto-generation
        recovery_thread_id = t.thread_id
        assert recovery_thread_id is not None
        assert len(recovery_thread_id) > 20  # Should be auto-generated UUID v7

        result = failing_op(False)
        assert result == "success"
        assert t.thread_id == recovery_thread_id  # ThreadContext consistent

    assert call_context.get_thread_id() is None


def test_threads_query_endpoint(client):
    """Test the threads_query endpoint (/threads/query) functionality."""
    import datetime

    import weave
    from weave.trace_server import trace_server_interface as tsi

    # Create some test operations
    @weave.op
    def thread_test_op(value: str) -> str:
        return f"processed_{value}"

    @weave.op
    def multi_call_op(thread_name: str) -> list[str]:
        results = []
        for i in range(3):
            results.append(thread_test_op(f"{thread_name}_call_{i}"))
        return results

    # Test that we start with no threads (if this is a fresh client)
    initial_threads = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(project_id=get_client_project_id(client))
        )
    )
    initial_count = len(initial_threads)

    assert initial_count == 0, f"Expected 0 threads, got {initial_count}"

    # Create calls with different thread_ids
    thread_ids = ["analytics_thread", "processing_thread", "validation_thread"]

    for i, thread_id in enumerate(thread_ids):
        with weave.thread(thread_id):
            # Create multiple calls per thread to test turn_count
            multi_call_op(f"thread_{i}")
            thread_test_op(f"single_call_{i}")

    # Create some calls without thread_ids
    thread_test_op("no_thread_1")
    thread_test_op("no_thread_2")

    # Test basic threads query
    threads_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(project_id=get_client_project_id(client))
        )
    )

    # Should have found our new threads
    assert len(threads_res) >= 3  # At least our 3 threads

    # Find our specific threads
    our_threads = {
        thread.thread_id: thread
        for thread in threads_res
        if thread.thread_id in thread_ids
    }
    assert len(our_threads) == 3, f"Expected 3 threads, got {len(our_threads)}"

    # Test that each thread has the correct turn_count
    # Each thread should have 2 distinct turns:
    # 1) multi_call_op() turn (with 3 nested calls)
    # 2) thread_test_op("single_call_i") turn
    for thread_id, thread in our_threads.items():
        assert thread.thread_id == thread_id
        assert thread.turn_count >= 2, (
            f"Thread {thread_id} should have at least 2 turns, got {thread.turn_count}"
        )
        assert thread.start_time is not None
        assert thread.last_updated is not None
        assert isinstance(thread.start_time, datetime.datetime)
        assert isinstance(thread.last_updated, datetime.datetime)

    # Test limit parameter
    limited_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(project_id=get_client_project_id(client), limit=2)
        )
    )
    assert len(limited_res) == 2

    # Test offset parameter
    offset_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client), limit=1, offset=1
            )
        )
    )
    assert len(offset_res) == 1

    # Test sorting by thread_id
    sorted_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[SortBy(field="thread_id", direction="asc")],
            )
        )
    )
    thread_ids_sorted = [t.thread_id for t in sorted_res]
    assert thread_ids_sorted == sorted(thread_ids_sorted)

    # Test sorting by turn_count descending
    count_sorted_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[SortBy(field="turn_count", direction="desc")],
            )
        )
    )
    turn_counts = [t.turn_count for t in count_sorted_res]
    assert turn_counts == sorted(turn_counts, reverse=True)

    # Test sorting by last_updated descending (most recent first)
    time_sorted_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[SortBy(field="last_updated", direction="desc")],
            )
        )
    )
    last_updated_times = [t.last_updated for t in time_sorted_res]
    # Verify times are in descending order
    for i in range(len(last_updated_times) - 1):
        assert last_updated_times[i] >= last_updated_times[i + 1]

    # Test datetime filtering
    # Get a timestamp from the middle of our test
    middle_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        seconds=5
    )

    after_filter_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.ThreadsQueryFilter(after_datetime=middle_time),
            )
        )
    )
    # Should still include our recent threads
    recent_thread_ids = {t.thread_id for t in after_filter_res}
    assert any(tid in recent_thread_ids for tid in thread_ids)

    # Test filtering for very recent data (should include our threads)
    very_recent_time = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(minutes=1)
    before_filter_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.ThreadsQueryFilter(before_datetime=very_recent_time),
            )
        )
    )
    # Should include our threads since they're before this future time
    assert len(before_filter_res) >= 3

    # Test thread_ids filtering
    # Test filtering by specific thread_ids (single thread)
    for test_thread_id in thread_ids:
        thread_ids_filter_res = list(
            client.server.threads_query_stream(
                tsi.ThreadsQueryReq(
                    project_id=get_client_project_id(client),
                    filter=tsi.ThreadsQueryFilter(thread_ids=[test_thread_id]),
                )
            )
        )
        # Should find exactly one thread with the specified thread_id
        assert len(thread_ids_filter_res) == 1
        assert thread_ids_filter_res[0].thread_id == test_thread_id

    # Test filtering by multiple thread_ids
    multiple_thread_ids_filter_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.ThreadsQueryFilter(thread_ids=thread_ids[:2]),
            )
        )
    )
    # Should find exactly two threads
    assert len(multiple_thread_ids_filter_res) == 2
    found_thread_ids = {t.thread_id for t in multiple_thread_ids_filter_res}
    assert found_thread_ids == set(thread_ids[:2])

    # Test filtering by non-existent thread_ids
    nonexistent_filter_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                filter=tsi.ThreadsQueryFilter(thread_ids=["nonexistent_thread_id"]),
            )
        )
    )
    assert len(nonexistent_filter_res) == 0

    # Test combining thread_ids filter with other filters
    combo_thread_filter_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                limit=1,
                sort_by=[SortBy(field="turn_count", direction="desc")],
                filter=tsi.ThreadsQueryFilter(
                    thread_ids=["analytics_thread"],
                    after_datetime=middle_time,
                ),
            )
        )
    )
    # Should find at most 1 thread matching the specific thread_ids and time filter
    assert len(combo_thread_filter_res) <= 1
    if len(combo_thread_filter_res) == 1:
        assert combo_thread_filter_res[0].thread_id == "analytics_thread"

    # Test combination of parameters
    combo_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                limit=5,
                offset=0,
                sort_by=[SortBy(field="turn_count", direction="desc")],
                filter=tsi.ThreadsQueryFilter(after_datetime=middle_time),
            )
        )
    )
    assert len(combo_res) <= 5

    # Verify that the ThreadSchema fields are properly populated
    for thread in combo_res:
        assert isinstance(thread.thread_id, str)
        assert isinstance(thread.turn_count, int)
        assert thread.turn_count > 0
        assert isinstance(thread.start_time, datetime.datetime)
        assert isinstance(thread.last_updated, datetime.datetime)
        assert thread.start_time <= thread.last_updated


def test_threads_query_aggregation_fields(client):
    """Test the new aggregation fields in threads query: first_turn_id, last_turn_id, and duration percentiles."""
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # SQLite does not support sorting over mixed types in a column, so we skip this test
        return

    import time

    import weave
    from weave.trace_server import trace_server_interface as tsi

    @weave.op
    def quick_op(value: str) -> str:
        """Fast operation for testing timing."""
        time.sleep(0.01)  # 10ms
        return f"quick_{value}"

    @weave.op
    def medium_op(value: str) -> str:
        """Medium speed operation for testing timing."""
        time.sleep(0.05)  # 50ms
        return f"medium_{value}"

    @weave.op
    def slow_op(value: str) -> str:
        """Slow operation for testing timing."""
        time.sleep(0.1)  # 100ms
        return f"slow_{value}"

    # Create a thread with multiple calls having different durations
    # This will give us a good distribution for percentile testing
    test_thread_id = "timing_test_thread"
    call_results = []

    with weave.thread(test_thread_id):
        # Create calls with varying durations to test percentiles
        # Order: quick, medium, slow, quick, medium to create a distribution
        call_results.append(quick_op("1"))  # ~10ms - first chronologically
        time.sleep(0.01)  # Small gap between calls to ensure different timestamps
        call_results.append(medium_op("2"))  # ~50ms
        time.sleep(0.01)
        call_results.append(slow_op("3"))  # ~100ms
        time.sleep(0.01)
        call_results.append(quick_op("4"))  # ~10ms
        time.sleep(0.01)
        call_results.append(medium_op("5"))  # ~50ms - last chronologically

    # Verify our operations executed correctly
    assert call_results == ["quick_1", "medium_2", "slow_3", "quick_4", "medium_5"]

    # Query threads to get the aggregation data
    threads_res = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(project_id=get_client_project_id(client))
        )
    )

    # Find our test thread
    test_thread = None
    for thread in threads_res:
        if thread.thread_id == test_thread_id:
            test_thread = thread
            break

    assert test_thread is not None, f"Could not find thread {test_thread_id}"

    # Test basic aggregation fields exist
    assert hasattr(test_thread, "first_turn_id")
    assert hasattr(test_thread, "last_turn_id")
    assert hasattr(test_thread, "p50_turn_duration_ms")
    assert hasattr(test_thread, "p99_turn_duration_ms")

    # Test that aggregation fields have valid values
    assert test_thread.first_turn_id is not None
    assert test_thread.last_turn_id is not None
    assert isinstance(test_thread.first_turn_id, str)
    assert isinstance(test_thread.last_turn_id, str)

    # Duration percentiles should be numeric and reasonable
    assert test_thread.p50_turn_duration_ms is not None
    assert test_thread.p99_turn_duration_ms is not None
    assert isinstance(test_thread.p50_turn_duration_ms, (int, float))
    assert isinstance(test_thread.p99_turn_duration_ms, (int, float))

    # Test duration percentile ranges (should be between our min and max expected durations)
    assert 0 <= test_thread.p50_turn_duration_ms
    assert 0 <= test_thread.p99_turn_duration_ms
    assert (
        test_thread.p50_turn_duration_ms <= test_thread.p99_turn_duration_ms
    )  # P99 >= P50

    # Verify first_turn_id and last_turn_id point to actual calls
    all_calls = client.get_calls()

    first_call = None
    latest_call = None
    thread_calls = []

    for call in all_calls:
        if call.thread_id == test_thread_id:
            thread_calls.append(call)
            if call.id == test_thread.first_turn_id:
                first_call = call
            if call.id == test_thread.last_turn_id:
                latest_call = call

    assert first_call is not None, (
        f"Could not find first_turn_id {test_thread.first_turn_id}"
    )
    assert latest_call is not None, (
        f"Could not find last_turn_id {test_thread.last_turn_id}"
    )

    # Test that first_turn_id has the earliest start_time
    earliest_start = min(call.started_at for call in thread_calls)
    assert first_call.started_at == earliest_start

    # Test that last_turn_id has the latest end_time (last_updated)
    latest_end = max(call.ended_at for call in thread_calls if call.ended_at)
    assert latest_call.ended_at == latest_end

    # Test that we have the expected number of turn calls (5 operations)
    assert test_thread.turn_count == 5, (
        f"Expected 5 turns, got {test_thread.turn_count}"
    )

    # Test sorting by the new duration percentile fields
    # Test sorting by p50_turn_duration_ms
    sorted_by_p50 = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[SortBy(field="p50_turn_duration_ms", direction="desc")],
            )
        )
    )
    assert len(sorted_by_p50) >= 1

    # Test sorting by p99_turn_duration_ms
    sorted_by_p99 = list(
        client.server.threads_query_stream(
            tsi.ThreadsQueryReq(
                project_id=get_client_project_id(client),
                sort_by=[SortBy(field="p99_turn_duration_ms", direction="asc")],
            )
        )
    )
    assert len(sorted_by_p99) >= 1

    # Verify our test thread appears in sorting results
    def find_test_thread_in_results(results):
        for thread in results:
            if thread.thread_id == test_thread_id:
                return thread
        return None

    assert find_test_thread_in_results(sorted_by_p50) is not None
    assert find_test_thread_in_results(sorted_by_p99) is not None


def test_turn_id_functionality(client):
    """Test that turn_id is properly assigned for turn calls and descendants."""
    import weave

    @weave.op
    def child_op(x: int) -> int:
        return x + 1

    @weave.op
    def turn_op_a(x: int) -> int:
        return child_op(x) * 2

    @weave.op
    def turn_op_b(x: int) -> int:
        return x * 3

    @weave.op
    def turn_op_c(x: int) -> int:
        return child_op(x) * 4

    # Test with thread context - sibling turns
    with weave.thread("test_turns"):
        result_a = turn_op_a(10)  # Should be a turn
        result_b = turn_op_b(5)  # Should be a turn
        result_c = turn_op_c(3)  # Should be a turn

    assert result_a == 22  # (10 + 1) * 2
    assert result_b == 15  # 5 * 3
    assert result_c == 16  # (3 + 1) * 4

    # Get calls and verify turn_id assignments
    calls = client.get_calls()

    turn_a_call = None
    turn_b_call = None
    turn_c_call = None
    child_calls = []

    for call in calls:
        if "turn_op_a" in call.op_name:
            turn_a_call = call
        elif "turn_op_b" in call.op_name:
            turn_b_call = call
        elif "turn_op_c" in call.op_name:
            turn_c_call = call
        elif "child_op" in call.op_name:
            child_calls.append(call)

    # Verify turn calls have their own ID as turn_id
    assert turn_a_call.turn_id == turn_a_call.id
    assert turn_b_call.turn_id == turn_b_call.id
    assert turn_c_call.turn_id == turn_c_call.id

    # Verify all have the same thread_id
    assert turn_a_call.thread_id == "test_turns"
    assert turn_b_call.thread_id == "test_turns"
    assert turn_c_call.thread_id == "test_turns"

    # Verify child calls inherit turn_id from their parents
    for child_call in child_calls:
        assert child_call.thread_id == "test_turns"
        # Child should inherit turn_id from its parent turn
        parent_turn_id = None
        for call in calls:
            if call.id == child_call.parent_id:
                parent_turn_id = call.turn_id
                break
        assert child_call.turn_id == parent_turn_id


def test_nested_thread_contexts_turn_lineage(client):
    """Test that nested thread contexts properly cut off turn lineage."""
    import weave

    @weave.op
    def child_op(x: int) -> int:
        return x + 1

    @weave.op
    def outer_turn_a(x: int) -> int:
        return child_op(x) * 2

    @weave.op
    def inner_turn_b(x: int) -> int:
        return x * 3

    @weave.op
    def inner_turn_c(x: int) -> int:
        return child_op(x) * 4

    @weave.op
    def outer_turn_d(x: int) -> int:
        return x * 5

    # Test nested thread contexts
    with weave.thread("outer_thread"):
        result_a = outer_turn_a(10)  # Should be turn in outer_thread

        with weave.thread("inner_thread"):
            result_b = inner_turn_b(5)  # Should be turn in inner_thread
            result_c = inner_turn_c(3)  # Should be turn in inner_thread

        result_d = outer_turn_d(2)  # Should be turn in outer_thread again

    assert result_a == 22  # (10 + 1) * 2
    assert result_b == 15  # 5 * 3
    assert result_c == 16  # (3 + 1) * 4
    assert result_d == 10  # 2 * 5

    # Get calls and verify turn_id assignments
    calls = client.get_calls()

    outer_a_call = None
    inner_b_call = None
    inner_c_call = None
    outer_d_call = None
    child_calls = []

    for call in calls:
        if "outer_turn_a" in call.op_name:
            outer_a_call = call
        elif "inner_turn_b" in call.op_name:
            inner_b_call = call
        elif "inner_turn_c" in call.op_name:
            inner_c_call = call
        elif "outer_turn_d" in call.op_name:
            outer_d_call = call
        elif "child_op" in call.op_name:
            child_calls.append(call)

    # Verify all turn calls have their own ID as turn_id
    assert outer_a_call.turn_id == outer_a_call.id
    assert inner_b_call.turn_id == inner_b_call.id
    assert inner_c_call.turn_id == inner_c_call.id
    assert outer_d_call.turn_id == outer_d_call.id

    # Verify thread_id assignments
    assert outer_a_call.thread_id == "outer_thread"
    assert inner_b_call.thread_id == "inner_thread"
    assert inner_c_call.thread_id == "inner_thread"
    assert outer_d_call.thread_id == "outer_thread"

    # Verify turn lineage is properly cut off - each thread creates new turns
    # outer_turn_A and outer_turn_D should have different turn_ids
    assert outer_a_call.turn_id != outer_d_call.turn_id
    # inner_turn_B and inner_turn_C should have different turn_ids
    assert inner_b_call.turn_id != inner_c_call.turn_id

    # Verify child calls inherit turn_id from their parent turns
    for child_call in child_calls:
        parent_turn_id = None
        for call in calls:
            if call.id == child_call.parent_id:
                parent_turn_id = call.turn_id
                break
        assert child_call.turn_id == parent_turn_id


def test_thread_id_none_turn_id_none(client):
    """Test that when thread_id is None, turn_id is also None."""
    import weave
    from weave.trace.context import call_context

    @weave.op
    def child_op(x: int) -> int:
        return x + 1

    @weave.op
    def turn_op_a(x: int) -> int:
        return child_op(x) * 2

    @weave.op
    def op_outside_thread(x: int) -> int:
        return x * 3

    # First, create a call within a thread context to set up turn context
    with weave.thread("test_thread"):
        result_a = turn_op_a(10)  # Should be a turn with turn_id

    # After exiting thread context, both thread_id and turn_id should be None
    assert call_context.get_thread_id() is None
    assert call_context.get_turn_id() is None

    # Now make a call outside any thread context
    # This should have thread_id = None and turn_id = None
    result_outside = op_outside_thread(5)

    assert result_a == 22  # (10 + 1) * 2
    assert result_outside == 15  # 5 * 3

    # Get calls and verify turn_id/thread_id assignments
    calls = client.get_calls()

    turn_a_call = None
    outside_call = None
    child_call = None

    for call in calls:
        if "turn_op_a" in call.op_name:
            turn_a_call = call
        elif "op_outside_thread" in call.op_name:
            outside_call = call
        elif "child_op" in call.op_name:
            child_call = call

    # Verify the turn call has proper thread_id and turn_id
    assert turn_a_call.thread_id == "test_thread"
    assert turn_a_call.turn_id == turn_a_call.id

    # Verify the child call inherits from its parent turn
    assert child_call.thread_id == "test_thread"
    assert child_call.turn_id == turn_a_call.turn_id

    # Verify the call outside thread context has both None
    assert outside_call.thread_id is None
    assert outside_call.turn_id is None


def test_nested_thread_disable_with_none(client):
    """Test that ThreadContext properly shows thread_id=None when threading is disabled."""
    import weave
    from weave.trace.context import call_context

    @weave.op
    def turn_a(x: int) -> int:
        return x * 2

    @weave.op
    def op_disabled_threading(x: int) -> int:
        return x * 3

    @weave.op
    def turn_c(x: int) -> int:
        return x * 4

    # Test the realistic edge case: nested thread with thread_id=None
    main_thread_context = None
    disabled_thread_context = None

    with weave.thread("main_thread") as t:
        main_thread_context = t
        assert t.thread_id == "main_thread"
        result_a = turn_a(10)  # Should be a turn with turn_id

        # Verify we're in thread context (turn_id is reset after call finishes)
        assert call_context.get_thread_id() == "main_thread"

        with weave.thread(None) as disabled_t:  # Explicitly disable thread tracking
            disabled_thread_context = disabled_t
            # ThreadContext shows None for disabled threading
            assert disabled_t.thread_id is None
            assert disabled_t.turn_id is None

            # Verify thread context is disabled
            assert call_context.get_thread_id() is None
            assert call_context.get_turn_id() is None

            result_b = op_disabled_threading(5)  # Should have no thread_id or turn_id

        # Back in main thread - should create a new turn
        # ThreadContext shows we're back in main thread
        assert t.thread_id == "main_thread"
        result_c = turn_c(3)  # Should be a new turn

    # Verify ThreadContext objects maintained correct state throughout
    assert main_thread_context.thread_id == "main_thread"
    assert disabled_thread_context.thread_id is None

    assert result_a == 20  # 10 * 2
    assert result_b == 15  # 5 * 3
    assert result_c == 12  # 3 * 4

    # Get calls and verify assignments
    calls = client.get_calls()

    turn_a_call = None
    disabled_call = None
    turn_c_call = None

    for call in calls:
        if "turn_a" in call.op_name:
            turn_a_call = call
        elif "op_disabled_threading" in call.op_name:
            disabled_call = call
        elif "turn_c" in call.op_name:
            turn_c_call = call

    # Verify first turn has proper thread_id and turn_id
    assert turn_a_call.thread_id == "main_thread"
    assert turn_a_call.turn_id == turn_a_call.id

    # Verify disabled call has both None (the edge case shown via ThreadContext)
    assert disabled_call.thread_id is None
    assert disabled_call.turn_id is None

    # Verify third turn is a new turn in the main thread
    assert turn_c_call.thread_id == "main_thread"
    assert turn_c_call.turn_id == turn_c_call.id

    # Verify the two turns in main_thread have different turn_ids
    assert turn_a_call.turn_id != turn_c_call.turn_id


def test_thread_api_with_auto_generation(client):
    """Test the thread API with ThreadContext and auto-generation."""
    import weave

    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    # Test 1: Auto-generated thread_id
    with weave.thread() as t:
        assert t.thread_id is not None
        assert isinstance(t.thread_id, str)
        # Should be a valid UUID v7 format (starts with time-based prefix)
        assert len(t.thread_id) > 20  # UUID v7 should be longer than 20 chars

        result1 = test_op(10)
        # turn_id is reset after turn call finishes, so it will be None here
        # We'll verify turn assignment by checking the call data later

    # Test 2: Explicit thread_id
    with weave.thread("custom_thread_123") as t:
        assert t.thread_id == "custom_thread_123"
        result2 = test_op(20)
        # turn_id is reset after turn call finishes

    # Test 3: Disabled threading (explicit None)
    with weave.thread(None) as t:
        assert t.thread_id is None
        result3 = test_op(30)
        assert t.turn_id is None  # Should always be None when threading disabled

    # Verify results
    assert result1 == 20
    assert result2 == 40
    assert result3 == 60

    # Get calls and verify thread assignments
    calls = client.get_calls()

    auto_call = None
    custom_call = None
    disabled_call = None

    for call in calls:
        if call.inputs.get("x") == 10:
            auto_call = call
        elif call.inputs.get("x") == 20:
            custom_call = call
        elif call.inputs.get("x") == 30:
            disabled_call = call

    # Verify auto-generated thread call
    assert auto_call.thread_id is not None
    assert len(auto_call.thread_id) > 20  # Should be UUID v7
    assert auto_call.turn_id == auto_call.id  # Should be a turn

    # Verify custom thread call
    assert custom_call.thread_id == "custom_thread_123"
    assert custom_call.turn_id == custom_call.id  # Should be a turn

    # Verify disabled thread call
    assert disabled_call.thread_id is None
    assert disabled_call.turn_id is None


def test_calls_query_filter_contains_in_message_array(client):
    @weave.op
    def op1(extra_message: str | None = None):
        messages = ["hello", "world"]
        if extra_message:
            messages.append(extra_message)
        return {"messages": messages}

    op1()
    op1("extra")
    op1("extra2")

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(project_id=get_client_project_id(client))
        )
    )
    assert len(calls) == 3

    # Test $contains with substring search in the JSON-serialized output
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                query={
                    "$expr": {
                        "$contains": {
                            "input": {"$getField": "output.messages"},
                            "substr": {"$literal": "hello"},
                        }
                    }
                },
            )
        )
    )
    assert len(calls) == 3

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=get_client_project_id(client),
                query={
                    "$expr": {
                        "$contains": {
                            "input": {"$getField": "output.messages"},
                            "substr": {"$literal": "extra2"},
                        }
                    }
                },
            )
        )
    )
    assert len(calls) == 1

    # Test exact match with $eq
    # TODO: this test breaks due to string optimization and how JSON is stored
    # on disk with spaces after items in a list. When we remove pre-where string
    # optimization, this test should be able to pass!
    # calls = list(
    #     client.server.calls_query_stream(
    #         tsi.CallsQueryReq(
    #             project_id=get_client_project_id(client),
    #             query={
    #                 "$expr": {
    #                     "$eq": [
    #                         {"$getField": "output.messages"},
    #                         {"$literal": '["hello","world"]'},
    #                     ]
    #                 }
    #             },
    #         )
    #     )
    # )
    # assert len(calls) == 1


def test_calls_query_sort_by_deselected_heavy_field(client):
    @weave.op
    def op1(x: int) -> int:
        return x * 2

    @weave.op
    def op2(x: int) -> int:
        return x * 3

    op1(1)
    op2(2)

    # get call ids
    calls = list(client.get_calls(columns=["id"]))
    call_ids = [call.id for call in calls]

    sort_by = [{"field": "inputs.x", "direction": "asc"}]
    calls = client.get_calls(sort_by=sort_by, columns=["id"], include_costs=False)
    assert len(calls) == 2
    assert calls[0].id == call_ids[0]
    assert calls[1].id == call_ids[1]

    calls = client.get_calls(sort_by=sort_by, columns=["id"], include_costs=True)
    assert len(calls) == 2
    assert calls[0].id == call_ids[0]
    assert calls[1].id == call_ids[1]


def test_calls_query_sort_by_nested_attributes_field_with_costs(client):
    """Test sorting by nested attributes field with cost query and minimal columns."""

    @weave.op
    def op1(x: int) -> int:
        return x * 2

    @weave.op
    def op2(x: int) -> int:
        return x * 3

    # Create calls with attributes
    call1 = client.create_call(op1, {"x": 1}, attributes={"metadata": {"priority": 2}})
    client.finish_call(call1, 2)

    call2 = client.create_call(op2, {"x": 2}, attributes={"metadata": {"priority": 1}})
    client.finish_call(call2, 6)

    # Get call ids in order of creation
    calls = list(client.get_calls(columns=["id"]))
    call_ids = [call.id for call in calls]

    # Sort by nested attribute field (ascending: 1, 2)
    sort_by = [{"field": "attributes.metadata.priority", "direction": "asc"}]
    calls = client.get_calls(sort_by=sort_by, columns=["id"], include_costs=False)
    assert len(calls) == 2
    assert calls[0].id == call_ids[1]  # call2 has priority 1
    assert calls[1].id == call_ids[0]  # call1 has priority 2

    # Test with include_costs=True
    calls = client.get_calls(sort_by=sort_by, columns=["id"], include_costs=True)
    assert len(calls) == 2
    assert calls[0].id == call_ids[1]  # call2 has priority 1
    assert calls[1].id == call_ids[0]  # call1 has priority 2


@pytest.mark.asyncio
async def test_calls_query_sort_by_feedback_field_with_costs(client):
    """Test sorting by feedback field with cost query and minimal columns."""
    if client_is_sqlite(client):
        # Not implemented in sqlite - skip
        pytest.skip("Sorting by feedback fields not implemented in SQLite")

    @weave.op
    def my_scorer(x: int, output: int) -> dict:
        return {"score": x + output}

    @weave.op
    def op1(x: int) -> int:
        return x * 2

    @weave.op
    def op2(x: int) -> int:
        return x * 3

    # Create and finish calls, then apply scorer
    _, call1 = op1.call(1)
    await call1.apply_scorer(my_scorer)

    _, call2 = op2.call(2)
    await call2.apply_scorer(my_scorer)

    filter = tsi.CallsFilter(op_names=[call1.op_name, call2.op_name])

    # Get call ids in order of creation
    calls = list(client.get_calls(columns=["id"], filter=filter))
    call_ids = [call.id for call in calls]

    # Sort by feedback field (ascending: score of 3 for call1, 8 for call2)
    sort_by = [
        {
            "field": "feedback.[wandb.runnable.my_scorer].payload.output.score",
            "direction": "asc",
        }
    ]
    calls = client.get_calls(
        sort_by=sort_by, columns=["id"], filter=filter, include_costs=False
    )
    assert len(calls) == 2
    assert calls[0].id == call_ids[0]  # call1 has score 3 (1+2)
    assert calls[1].id == call_ids[1]  # call2 has score 8 (2+6)

    # Test with include_costs=True
    calls = client.get_calls(
        sort_by=sort_by, columns=["id"], filter=filter, include_costs=True
    )
    assert len(calls) == 2
    assert calls[0].id == call_ids[0]  # call1 has score 3
    assert calls[1].id == call_ids[1]  # call2 has score 8


def test_calls_query_ordering_with_costs_comprehensive(client):
    @weave.op
    def my_op(x: int) -> int:
        return x

    # Calls with multiple sortable attributes
    call1 = client.create_call(
        my_op, {"x": 1}, attributes={"category": "A", "priority": 2}
    )
    client.finish_call(call1, 1)
    time.sleep(0.01)

    call2 = client.create_call(
        my_op, {"x": 2}, attributes={"category": "A", "priority": 1}
    )
    client.finish_call(call2, 2)
    time.sleep(0.01)

    call3 = client.create_call(
        my_op, {"x": 3}, attributes={"category": "B", "priority": 1}
    )
    client.finish_call(call3, 3)
    time.sleep(0.01)

    # Calls with deeply nested attributes
    call4 = client.create_call(
        my_op,
        {"x": 4},
        attributes={"metadata": {"config": {"model": {"temperature": 0.1}}}},
    )
    client.finish_call(call4, 4)
    time.sleep(0.01)

    call5 = client.create_call(
        my_op,
        {"x": 5},
        attributes={"metadata": {"config": {"model": {"temperature": 0.9}}}},
    )
    client.finish_call(call5, 5)
    time.sleep(0.01)

    # Call with missing/NULL attributes
    call6 = client.create_call(my_op, {"x": 6}, attributes={})
    client.finish_call(call6, 6)

    # Test Case 1: Multiple order fields with costs
    sort_by = [
        {"field": "attributes.category", "direction": "asc"},
        {"field": "attributes.priority", "direction": "asc"},
    ]
    calls = list(
        client.get_calls(
            sort_by=sort_by,
            columns=["id"],
            include_costs=True,
            filter=tsi.CallsFilter(call_ids=[call1.id, call2.id, call3.id]),
        )
    )
    assert len(calls) == 3
    assert calls[0].id == call2.id  # Category A, priority 1
    assert calls[1].id == call1.id  # Category A, priority 2
    assert calls[2].id == call3.id  # Category B, priority 1

    # Test Case 2: Deeply nested attributes (4 levels) with costs
    sort_by = [
        {"field": "attributes.metadata.config.model.temperature", "direction": "asc"}
    ]
    calls = list(
        client.get_calls(
            sort_by=sort_by,
            columns=["id"],
            include_costs=True,
            filter=tsi.CallsFilter(call_ids=[call4.id, call5.id]),
        )
    )
    assert len(calls) == 2
    assert calls[0].id == call4.id  # temperature 0.1
    assert calls[1].id == call5.id  # temperature 0.9

    # Test Case 3: NULL/missing attributes with costs
    sort_by = [{"field": "attributes.priority", "direction": "asc"}]
    calls = list(
        client.get_calls(
            sort_by=sort_by,
            columns=["id"],
            include_costs=True,
            filter=tsi.CallsFilter(call_ids=[call1.id, call2.id, call6.id]),
        )
    )
    assert len(calls) == 3
    # Calls with values come first, then NULLs
    calls_with_priority = [c for c in calls if c.id in [call1.id, call2.id]]
    assert calls_with_priority[0].id == call2.id  # priority 1
    assert calls_with_priority[1].id == call1.id  # priority 2

    # Test Case 4: Regular field (started_at) with costs
    sort_by = [{"field": "started_at", "direction": "desc"}]
    calls = list(
        client.get_calls(sort_by=sort_by, columns=["id"], include_costs=True, limit=3)
    )
    assert len(calls) == 3
    # Should be ordered by most recent first
    assert calls[0].id == call6.id
    assert calls[1].id == call5.id
    assert calls[2].id == call4.id
