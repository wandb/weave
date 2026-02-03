# ClickHouse Costs - Cost CRUD operations

import datetime

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.ids import generate_id
from weave.trace_server.token_costs import (
    LLM_TOKEN_PRICES_TABLE,
    validate_cost_purge_req,
)
from weave.trace_server.trace_server_interface_util import assert_non_null_wb_user_id


class CostsRepository:
    """Repository for cost CRUD operations."""

    def __init__(self, ch_client: ClickHouseClient):
        self._ch_client = ch_client

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost entries for LLM token pricing."""
        assert_non_null_wb_user_id(req)
        created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        costs = []
        for llm_id, cost in req.costs.items():
            cost_id = generate_id()
            row = {
                "id": cost_id,
                "created_at": created_at,
                "created_by": req.wb_user_id,
                "pricing_level": "project",
                "pricing_level_id": req.project_id,
                "provider_id": cost.provider_id or "default",
                "llm_id": llm_id,
                "effective_date": (
                    cost.effective_date if cost.effective_date else created_at
                ),
                "prompt_token_cost": cost.prompt_token_cost,
                "completion_token_cost": cost.completion_token_cost,
                "prompt_token_cost_unit": cost.prompt_token_cost_unit or "USD",
                "completion_token_cost_unit": cost.completion_token_cost_unit or "USD",
            }

            costs.append((cost_id, llm_id))

            prepared = LLM_TOKEN_PRICES_TABLE.insert(row).prepare(
                database_type="clickhouse"
            )
            self._ch_client.insert(
                LLM_TOKEN_PRICES_TABLE.name, prepared.data, prepared.column_names
            )

        return tsi.CostCreateRes(ids=costs)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """Query cost entries."""
        expr = {
            "$and": [
                (
                    req.query.expr_
                    if req.query
                    else {
                        "$eq": [
                            {"$getField": "pricing_level_id"},
                            {"$literal": req.project_id},
                        ],
                    }
                ),
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": "project"},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})
        query = LLM_TOKEN_PRICES_TABLE.select()
        query = query.fields(req.fields)
        query = query.where(query_with_pricing_level)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="clickhouse")
        query_result = self._ch_client.ch_client.query(
            prepared.sql, prepared.parameters
        )
        results = LLM_TOKEN_PRICES_TABLE.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.CostQueryRes(results=results)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """Purge (delete) cost entries matching a query."""
        validate_cost_purge_req(req)

        expr = {
            "$and": [
                req.query.expr_,
                {
                    "$eq": [
                        {"$getField": "pricing_level_id"},
                        {"$literal": req.project_id},
                    ],
                },
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": "project"},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})

        query = LLM_TOKEN_PRICES_TABLE.purge()
        query = query.where(query_with_pricing_level)
        prepared = query.prepare(database_type="clickhouse")
        self._ch_client.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.CostPurgeRes()
