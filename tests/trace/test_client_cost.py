from datetime import datetime

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.tsi.query import Query


def test_cost_apis(client):
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    project_id = client._project_id()

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
            "effective_date": datetime(2021, 4, 22),
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
        effective_date=datetime(1998, 10, 3),
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
    if client_is_sqlite(client):
        # dont run this test for sqlite
        return

    project_id = client._project_id()
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
