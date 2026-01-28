import datetime
import uuid
from typing import Any

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server import usage_utils

_REQUIRED_COST_FIELDS = (
    "prompt_tokens",
    "input_tokens",
    "completion_tokens",
    "output_tokens",
    "requests",
    "total_tokens",
    "prompt_tokens_total_cost",
    "completion_tokens_total_cost",
    "prompt_token_cost",
    "completion_token_cost",
    "prompt_token_cost_unit",
    "completion_token_cost_unit",
    "effective_date",
    "provider_id",
    "pricing_level",
    "pricing_level_id",
    "created_at",
    "created_by",
)


def skip_if_sqlite(client: weave_client.WeaveClient) -> None:
    if client_is_sqlite(client):
        pytest.skip("trace_usage is only implemented in ClickHouse")


def _usage_summary(
    usage: dict[str, dict[str, Any]],
    costs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {"usage": usage}
    if costs is not None:
        summary["weave"] = {"costs": _normalize_costs(costs)}
    return summary


def _normalize_costs(costs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for model_name, cost_entry in costs.items():
        entry = dict(cost_entry) if isinstance(cost_entry, dict) else {}
        merged = dict.fromkeys(_REQUIRED_COST_FIELDS)
        merged.update(entry)
        normalized[model_name] = merged
    return normalized


def _make_call(
    call_id: str,
    parent_id: str | None,
    summary: dict[str, Any] | None,
    validate: bool = True,
) -> tsi.CallSchema:
    call_data = {
        "id": call_id,
        "project_id": "entity/project",
        "op_name": "weave:///entity/project/op/test_op:v1",
        "trace_id": "trace-id",
        "parent_id": parent_id,
        "started_at": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        "attributes": {},
        "inputs": {},
        "summary": summary,
    }
    if validate:
        return tsi.CallSchema(**call_data)
    return tsi.CallSchema.model_construct(**call_data)


def _create_call(
    client: weave_client.WeaveClient,
    call_id: str,
    trace_id: str,
    parent_id: str | None,
    started_at: datetime.datetime,
    usage: dict[str, dict[str, Any]],
) -> None:
    project_id = client._project_id()
    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                started_at=started_at,
                op_name=f"weave:///{project_id}/op/test_op:v1",
                parent_id=parent_id,
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=started_at + datetime.timedelta(seconds=1),
                summary={"usage": usage},
            )
        )
    )


def test_aggregate_usage_with_descendants_rolls_up() -> None:
    root_id = "root"
    child_a_id = "child-a"
    child_b_id = "child-b"
    grandchild_id = "grandchild"

    calls = [
        _make_call(
            root_id,
            None,
            _usage_summary(
                {
                    "gpt-4": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                        "requests": 1,
                    }
                }
            ),
        ),
        _make_call(
            child_a_id,
            root_id,
            _usage_summary({"gpt-4": {"input_tokens": 2, "output_tokens": 3}}),
        ),
        _make_call(
            child_b_id,
            root_id,
            _usage_summary(
                {
                    "gpt-3": {
                        "prompt_tokens": 7,
                        "completion_tokens": 0,
                        "total_tokens": 7,
                        "requests": 1,
                    }
                }
            ),
        ),
        _make_call(
            grandchild_id,
            child_a_id,
            _usage_summary(
                {
                    "gpt-4": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                        "requests": 1,
                    }
                }
            ),
        ),
        _make_call("invalid", None, {"usage": {"gpt-bad": "oops"}}, validate=False),
    ]

    result = usage_utils.aggregate_usage_with_descendants(calls, include_costs=False)

    root_usage = result[root_id]
    assert root_usage["gpt-4"].prompt_tokens == 13
    assert root_usage["gpt-4"].completion_tokens == 9
    assert root_usage["gpt-4"].total_tokens == 22
    assert root_usage["gpt-4"].requests == 2
    assert root_usage["gpt-3"].prompt_tokens == 7
    assert root_usage["gpt-3"].total_tokens == 7

    child_usage = result[child_a_id]["gpt-4"]
    assert child_usage.prompt_tokens == 3
    assert child_usage.completion_tokens == 4
    assert child_usage.total_tokens == 7
    assert child_usage.requests == 1

    assert result["invalid"] == {}


def test_aggregate_usage_includes_costs_when_requested() -> None:
    root_id = "root"
    child_id = "child"

    calls = [
        _make_call(
            root_id,
            None,
            _usage_summary(
                {
                    "gpt-4": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "requests": 0,
                    }
                },
                costs={
                    "gpt-4": {
                        "prompt_tokens_total_cost": 0.5,
                        "completion_tokens_total_cost": 0.2,
                    }
                },
            ),
        ),
        _make_call(
            child_id,
            root_id,
            _usage_summary(
                {
                    "gpt-4": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                        "requests": 1,
                    }
                },
                costs={
                    "gpt-4": {
                        "prompt_tokens_total_cost": 0.1,
                        "completion_tokens_total_cost": 0.05,
                    }
                },
            ),
        ),
    ]

    result = usage_utils.aggregate_usage_with_descendants(calls, include_costs=True)
    root_usage = result[root_id]["gpt-4"]
    assert root_usage.prompt_tokens == 1
    assert root_usage.completion_tokens == 1
    assert root_usage.total_tokens == 2
    assert root_usage.requests == 1
    assert root_usage.prompt_tokens_total_cost == pytest.approx(0.6)
    assert root_usage.completion_tokens_total_cost == pytest.approx(0.25)

    result_no_costs = usage_utils.aggregate_usage_with_descendants(
        calls, include_costs=False
    )
    root_no_costs = result_no_costs[root_id]["gpt-4"]
    assert root_no_costs.prompt_tokens_total_cost is None
    assert root_no_costs.completion_tokens_total_cost is None


@pytest.mark.parametrize(
    ("root_usage", "middle_usage", "leaf_usage"),
    [
        (
            None,
            {
                "gpt-4": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_tokens": 3,
                    "requests": 1,
                }
            },
            {
                "gpt-4": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                    "requests": 1,
                }
            },
        ),
        (
            {
                "gpt-4": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                    "requests": 1,
                }
            },
            None,
            {
                "gpt-4": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                    "requests": 1,
                }
            },
        ),
        (
            None,
            None,
            {
                "gpt-4": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                    "requests": 1,
                }
            },
        ),
        (None, None, None),
    ],
    ids=[
        "root_missing_usage",
        "middle_missing_usage",
        "root_and_middle_missing_usage",
        "no_usage_anywhere",
    ],
)
def test_aggregate_usage_handles_missing_summaries(
    root_usage: dict[str, dict[str, Any]] | None,
    middle_usage: dict[str, dict[str, Any]] | None,
    leaf_usage: dict[str, dict[str, Any]] | None,
) -> None:
    root_id = "root"
    middle_id = "middle"
    leaf_id = "leaf"

    calls = [
        _make_call(
            root_id,
            None,
            _usage_summary(root_usage) if root_usage is not None else None,
        ),
        _make_call(
            middle_id,
            root_id,
            _usage_summary(middle_usage) if middle_usage is not None else None,
        ),
        _make_call(
            leaf_id,
            middle_id,
            _usage_summary(leaf_usage) if leaf_usage is not None else None,
        ),
    ]

    result = usage_utils.aggregate_usage_with_descendants(calls, include_costs=False)

    def totals(usage: dict[str, dict[str, Any]] | None) -> tuple[int, int, int, int]:
        if not usage:
            return (0, 0, 0, 0)
        llm_usage = usage.get("gpt-4", {})
        return (
            int(llm_usage.get("prompt_tokens") or 0),
            int(llm_usage.get("completion_tokens") or 0),
            int(llm_usage.get("total_tokens") or 0),
            int(llm_usage.get("requests") or 0),
        )

    root_totals = totals(root_usage)
    middle_totals = totals(middle_usage)
    leaf_totals = totals(leaf_usage)

    expected_root = tuple(
        map(sum, zip(root_totals, middle_totals, leaf_totals, strict=False))
    )
    expected_middle = tuple(map(sum, zip(middle_totals, leaf_totals, strict=False)))
    expected_leaf = leaf_totals

    def assert_usage(call_id: str, expected: tuple[int, int, int, int]) -> None:
        if expected == (0, 0, 0, 0):
            assert result[call_id] == {}
            return
        usage = result[call_id]["gpt-4"]
        assert usage.prompt_tokens == expected[0]
        assert usage.completion_tokens == expected[1]
        assert usage.total_tokens == expected[2]
        assert usage.requests == expected[3]

    assert_usage(root_id, expected_root)
    assert_usage(middle_id, expected_middle)
    assert_usage(leaf_id, expected_leaf)


def test_trace_usage_rolls_up_descendants(client: weave_client.WeaveClient) -> None:
    skip_if_sqlite(client)

    project_id = client._project_id()
    trace_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    root_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    grandchild_id = str(uuid.uuid4())

    _create_call(
        client,
        root_id,
        trace_id,
        None,
        now,
        {"gpt-4": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}},
    )
    _create_call(
        client,
        child_id,
        trace_id,
        root_id,
        now + datetime.timedelta(seconds=2),
        {"gpt-4": {"input_tokens": 2, "output_tokens": 1}},
    )
    _create_call(
        client,
        grandchild_id,
        trace_id,
        child_id,
        now + datetime.timedelta(seconds=4),
        {"gpt-4": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}},
    )

    res = client.server.trace_usage(
        tsi.TraceUsageReq(
            project_id=project_id,
            filter=tsi.CallsFilter(trace_ids=[trace_id]),
        )
    )

    root_usage = res.call_usage[root_id]["gpt-4"]
    assert root_usage.prompt_tokens == 10
    assert root_usage.completion_tokens == 7
    assert root_usage.total_tokens == 17

    child_usage = res.call_usage[child_id]["gpt-4"]
    assert child_usage.prompt_tokens == 5
    assert child_usage.completion_tokens == 2
    assert child_usage.total_tokens == 7


def test_trace_usage_include_costs_flag(client: weave_client.WeaveClient) -> None:
    skip_if_sqlite(client)

    project_id = client._project_id()
    trace_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    call_id = str(uuid.uuid4())
    _create_call(
        client,
        call_id,
        trace_id,
        None,
        now,
        {"gpt-4": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}},
    )

    res_no_costs = client.server.trace_usage(
        tsi.TraceUsageReq(
            project_id=project_id,
            filter=tsi.CallsFilter(trace_ids=[trace_id]),
            include_costs=False,
        )
    )
    usage_no_costs = res_no_costs.call_usage[call_id]["gpt-4"]
    assert usage_no_costs.prompt_tokens_total_cost is None
    assert usage_no_costs.completion_tokens_total_cost is None

    res_with_costs = client.server.trace_usage(
        tsi.TraceUsageReq(
            project_id=project_id,
            filter=tsi.CallsFilter(trace_ids=[trace_id]),
            include_costs=True,
        )
    )
    usage_with_costs = res_with_costs.call_usage[call_id]["gpt-4"]
    assert usage_with_costs.prompt_tokens_total_cost is not None
    assert usage_with_costs.completion_tokens_total_cost is not None


def test_calls_usage_rolls_up_descendants(client: weave_client.WeaveClient) -> None:
    skip_if_sqlite(client)

    project_id = client._project_id()
    trace_id = str(uuid.uuid4())
    trace_id_two = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    root_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    grandchild_id = str(uuid.uuid4())
    root_id_two = str(uuid.uuid4())

    _create_call(
        client,
        root_id,
        trace_id,
        None,
        now,
        {"gpt-4": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}},
    )
    _create_call(
        client,
        child_id,
        trace_id,
        root_id,
        now + datetime.timedelta(seconds=2),
        {"gpt-4": {"input_tokens": 2, "output_tokens": 1}},
    )
    _create_call(
        client,
        grandchild_id,
        trace_id,
        child_id,
        now + datetime.timedelta(seconds=4),
        {"gpt-4": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}},
    )
    _create_call(
        client,
        root_id_two,
        trace_id_two,
        None,
        now + datetime.timedelta(seconds=6),
        {"gpt-4": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}},
    )

    res = client.server.calls_usage(
        tsi.CallsUsageReq(
            project_id=project_id,
            call_ids=[root_id, root_id_two],
        )
    )

    root_usage = res.call_usage[root_id]["gpt-4"]
    assert root_usage.prompt_tokens == 10
    assert root_usage.completion_tokens == 7
    assert root_usage.total_tokens == 17

    root_two_usage = res.call_usage[root_id_two]["gpt-4"]
    assert root_two_usage.prompt_tokens == 2
    assert root_two_usage.completion_tokens == 1
    assert root_two_usage.total_tokens == 3


def test_calls_usage_include_costs_flag(client: weave_client.WeaveClient) -> None:
    skip_if_sqlite(client)

    project_id = client._project_id()
    trace_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    call_id = str(uuid.uuid4())
    _create_call(
        client,
        call_id,
        trace_id,
        None,
        now,
        {"gpt-4": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}},
    )

    res_no_costs = client.server.calls_usage(
        tsi.CallsUsageReq(
            project_id=project_id,
            call_ids=[call_id],
            include_costs=False,
        )
    )
    usage_no_costs = res_no_costs.call_usage[call_id]["gpt-4"]
    assert usage_no_costs.prompt_tokens_total_cost is None
    assert usage_no_costs.completion_tokens_total_cost is None

    res_with_costs = client.server.calls_usage(
        tsi.CallsUsageReq(
            project_id=project_id,
            call_ids=[call_id],
            include_costs=True,
        )
    )
    usage_with_costs = res_with_costs.call_usage[call_id]["gpt-4"]
    assert usage_with_costs.prompt_tokens_total_cost is not None
    assert usage_with_costs.completion_tokens_total_cost is not None
