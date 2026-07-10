import datetime
import uuid

import pytest

from tests.trace.util import client_is_clickhouse
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.interface.query import Query


def test_cost_apis(client):
    project_id = client.project_id

    costs = {
        "my_model_to_delete": {
            "prompt_token_cost": 5,
            "completion_token_cost": 10,
        },
        "my_model_to_delete2": {
            "prompt_token_cost": 15,
            "completion_token_cost": 20,
            "provider_id": "josiah",
        },
        "my_model_to_delete3": {
            "prompt_token_cost": 25,
            "completion_token_cost": 30,
            "effective_date": datetime.datetime(2021, 4, 22),
        },
        "my_model_to_delete4": {
            "prompt_token_cost": 35,
            "completion_token_cost": 40,
            "completion_token_cost_unit": "doubleoons",
        },
    }
    # Create some costs
    res = client.server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs=costs,
            wb_user_id="VXNlcjo0NTI1NDQ=",
        )
    )

    cost_ids = res.ids
    assert len(cost_ids) == 4

    # query costs by project
    req = tsi.CostQueryReq(
        project_id=project_id,
    )
    res = client.server.cost_query(req)
    assert len(res.results) == 4

    res = client.query_costs()
    assert len(res) == 4

    # query costs by id
    res = client.query_costs(cost_ids[2][0])
    assert len(res) == 1
    assert res[0].llm_id == "my_model_to_delete3"

    # query costs by llm_id
    res = client.query_costs(llm_ids=["my_model_to_delete2"])
    assert len(res) == 1
    assert res[0].llm_id == "my_model_to_delete2"
    assert res[0].provider_id == "josiah"

    # query costs by llm_id
    res = client.query_costs(llm_ids=["my_model_to_delete", "my_model_to_delete4"])
    assert len(res) == 2
    if res[0].llm_id == "my_model_to_delete":
        assert res[0].completion_token_cost_unit == "USD"
        assert res[1].completion_token_cost_unit == "doubleoons"
    else:
        assert res[0].completion_token_cost_unit == "doubleoons"
        assert res[1].completion_token_cost_unit == "USD"

    # Add another cost of the same llm_id
    res = client.add_cost(
        llm_id="my_model_to_delete3",
        prompt_token_cost=500,
        completion_token_cost=1000,
        effective_date=datetime.datetime(1998, 10, 3),
    )

    assert len(res.ids) == 1
    last_id = res.ids[0][0]

    # query multiple costs by llm_id
    res = client.query_costs(llm_ids=["my_model_to_delete3"])
    assert len(res) == 2
    if res[0].effective_date.year == 2021:
        assert res[1].effective_date.year == 1998
    else:
        assert res[1].effective_date.year == 2021
        assert res[0].effective_date.year == 1998

    # query with limit and offset
    res = client.query_costs(llm_ids=["my_model_to_delete3"], limit=1)
    assert len(res) == 1

    res = client.query_costs(llm_ids=["my_model_to_delete3"], offset=1)
    assert len(res) == 1

    # query with query
    res = client.query_costs(
        query=Query(
            **{
                "$expr": {
                    "$gt": [
                        {"$getField": "completion_token_cost"},
                        {"$literal": 25},
                    ],
                }
            }
        )
    )
    assert len(res) == 3

    # purge costs
    client.purge_costs(cost_ids[0][0])
    res = client.query_costs()
    assert len(res) == 4

    client.purge_costs(cost_ids[0][0])
    res = client.query_costs()
    assert len(res) == 4

    client.purge_costs([id[0] for id in cost_ids])
    res = client.query_costs()
    assert len(res) == 1
    assert res[0].id == last_id

    # purge last cost
    client.purge_costs(last_id)
    res = client.query_costs()
    assert len(res) == 0


def test_purge_only_ids(client):
    project_id = client.project_id
    costs = {
        "my_model_to_delete": {
            "prompt_token_cost": 5,
            "completion_token_cost": 10,
        },
    }
    # Create some costs
    res = client.server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs=costs,
            wb_user_id="VXNlcjo0NTI1NDQ=",
        )
    )

    cost_ids = res.ids
    assert len(cost_ids) == 1

    with pytest.raises(InvalidRequest):
        client.server.cost_purge(
            tsi.CostPurgeReq(
                project_id=project_id,
                query=Query(
                    **{
                        "$expr": {
                            "$eq": [
                                {"$getField": "llm_id"},
                                {"$literal": "my_model_to_delete"},
                            ],
                        }
                    }
                ),
            )
        )

    client.server.cost_purge(
        tsi.CostPurgeReq(
            project_id=project_id,
            query=Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "id"},
                            {"$literal": cost_ids[0][0]},
                        ],
                    }
                }
            ),
        )
    )


def test_costs_streamed_with_all_fields(client):
    """Costs returned by calls_query_stream include extra metadata fields
    (provider_id, effective_date, pricing_level, etc.) and must not fail
    Pydantic validation even when some of those fields are absent.
    """
    project_id = client.project_id

    # 1. Create cost entry with optional metadata fields populated
    client.server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs={
                "test-llm": {
                    "prompt_token_cost": 0.001,
                    "completion_token_cost": 0.002,
                    "provider_id": "test-provider",
                    "effective_date": datetime.datetime(
                        2024, 1, 1, tzinfo=datetime.timezone.utc
                    ),
                },
            },
            wb_user_id="VXNlcjo0NTI1NDQ=",
        )
    )

    # 2. Create a call with matching usage data
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                started_at=now,
                op_name=f"weave:///{project_id}/op/test_op:v1",
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
                ended_at=now + datetime.timedelta(seconds=1),
                summary={
                    "usage": {
                        "test-llm": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                            "total_tokens": 150,
                            "requests": 1,
                        }
                    }
                },
            )
        )
    )

    # 3. Stream calls back with include_costs — this is the read path that
    #    previously failed with Pydantic validation errors when LLMCostSchema
    #    required all fields.
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                include_costs=True,
            )
        )
    )
    assert len(calls) == 1

    call = calls[0]
    assert call.summary is not None
    costs = call.summary.get("weave", {}).get("costs", {})
    assert "test-llm" in costs

    cost_entry = costs["test-llm"]

    # Verify core cost calculations
    assert cost_entry["prompt_tokens"] == 100
    assert cost_entry["completion_tokens"] == 50
    assert cost_entry["prompt_token_cost"] == pytest.approx(0.001)
    assert cost_entry["completion_token_cost"] == pytest.approx(0.002)
    assert cost_entry["prompt_tokens_total_cost"] == pytest.approx(100 * 0.001)
    assert cost_entry["completion_tokens_total_cost"] == pytest.approx(50 * 0.002)

    # Verify the extra metadata fields that come from the llm_token_prices
    # table are present — these are the fields that caused the original
    # validation error when LLMCostSchema didn't have total=False.
    assert cost_entry["provider_id"] == "test-provider"
    assert cost_entry["pricing_level"] == "project"
    assert cost_entry["pricing_level_id"] is not None
    assert cost_entry["created_at"] is not None
    assert cost_entry["created_by"] is not None
    assert cost_entry["effective_date"] is not None
    assert cost_entry["prompt_token_cost_unit"] == "USD"
    assert cost_entry["completion_token_cost_unit"] == "USD"


def test_call_costs_prefer_marked_gross_input_and_preserve_legacy(client):
    project_id = client.project_id
    model = "claude-cache-cost-test"
    client.server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs={
                model: {
                    "prompt_token_cost": 1,
                    "completion_token_cost": 1,
                    "cache_read_input_token_cost": 0.1,
                    "cache_creation_input_token_cost": 0.2,
                }
            },
            wb_user_id="VXNlcjo0NTI1NDQ=",
        )
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    usage_by_call_id: dict[str, dict[str, int]] = {}
    for index, usage in enumerate(
        [
            {
                "input_tokens": 10,
                "gross_input_tokens": 130,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 20,
                "output_tokens": 2,
            },
            {
                "input_tokens": 5,
                "cache_read_input_tokens": 50,
                "cache_creation_input_tokens": 10,
                "output_tokens": 3,
            },
        ]
    ):
        call_id = str(uuid.uuid4())
        usage_by_call_id[call_id] = usage
        started_at = now + datetime.timedelta(seconds=index * 2)
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=str(uuid.uuid4()),
                    started_at=started_at,
                    op_name=f"weave:///{project_id}/op/cache_cost:v1",
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
                    summary={"usage": {model: usage}},
                )
            )
        )

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                filter=tsi.CallsFilter(call_ids=list(usage_by_call_id)),
                include_costs=True,
            )
        )
    )
    calls_by_id = {call.id: call for call in calls}

    marked_call_id = next(
        call_id
        for call_id, usage in usage_by_call_id.items()
        if "gross_input_tokens" in usage
    )
    marked_call = calls_by_id[marked_call_id]
    assert marked_call.summary["usage"][model] == usage_by_call_id[marked_call_id]
    marked_cost = marked_call.summary["weave"]["costs"][model]
    assert marked_cost["prompt_tokens"] == 130
    assert marked_cost["prompt_tokens_total_cost"] == pytest.approx(10)
    assert marked_cost["completion_tokens_total_cost"] == pytest.approx(2)

    legacy_call_id = next(
        call_id
        for call_id, usage in usage_by_call_id.items()
        if "gross_input_tokens" not in usage
    )
    legacy_call = calls_by_id[legacy_call_id]
    assert legacy_call.summary["usage"][model] == usage_by_call_id[legacy_call_id]
    legacy_cost = legacy_call.summary["weave"]["costs"][model]
    assert legacy_cost["prompt_tokens"] == 5
    assert legacy_cost["prompt_tokens_total_cost"] == pytest.approx(-55)
    assert legacy_cost["completion_tokens_total_cost"] == pytest.approx(3)

    if client_is_clickhouse(client):
        assert marked_cost["cache_read_input_tokens_total_cost"] == pytest.approx(10)
        assert marked_cost["cache_creation_input_tokens_total_cost"] == pytest.approx(4)
        assert legacy_cost["cache_read_input_tokens_total_cost"] == pytest.approx(5)
        assert legacy_cost["cache_creation_input_tokens_total_cost"] == pytest.approx(2)
