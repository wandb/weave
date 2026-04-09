"""Cost management operations for the ClickHouse trace server."""

import datetime
from typing import Any
from zoneinfo import ZoneInfo

from weave.shared.trace_server_interface_util import assert_non_null_wb_user_id
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.protocol import CHInfraProtocol
from weave.trace_server.ids import generate_id
from weave.trace_server.orm import Row
from weave.trace_server.token_costs import (
    LLM_TOKEN_PRICES_TABLE,
    build_model_prices_query,
    validate_cost_purge_req,
)


class CostsMixin(CHInfraProtocol):
    # ------------------------------------------------------------------
    # Cost computation helpers (used by call_stats in main file)
    # ------------------------------------------------------------------

    def _get_prices_for_models(
        self, models: set[str], project_id: str
    ) -> dict[str, dict[str, float]]:
        """Query llm_token_prices for the given models and return best prices.

        Returns a dict mapping model -> {prompt_token_cost, completion_token_cost}.
        Uses pricing level priority: project > default, newest effective_date.
        """
        if not models:
            return {}

        try:
            sql, params = build_model_prices_query(project_id, list(models))
            settings = None
            if self.use_distributed_mode:
                # Use patched settings for distributed bug (more info in ch_settings)
                settings = ch_settings.CLICKHOUSE_DISTRIBUTED_COST_QUERY_SETTINGS
            result = self._query(sql, params, settings=settings)
        except Exception:
            # If price query fails, return empty prices (costs will be 0)
            return {}

        prices: dict[str, dict[str, float]] = {}
        for row in result.result_rows:
            llm_id, prompt_cost, completion_cost = row
            prices[llm_id] = {
                "prompt_token_cost": float(prompt_cost) if prompt_cost else 0.0,
                "completion_token_cost": float(completion_cost)
                if completion_cost
                else 0.0,
            }
        return prices

    def _compute_costs_for_buckets(
        self,
        usage_buckets: list[dict[str, Any]],
        project_id: str,
        requested_cost_metrics: set[str],
    ) -> None:
        """Compute cost metrics for usage buckets by multiplying tokens by prices.

        Args:
            usage_buckets: Buckets with token counts (modified in place).
            project_id: Project ID for pricing lookup.
            requested_cost_metrics: Set of cost metrics to compute (input_cost, output_cost, total_cost).
        """
        if not requested_cost_metrics or not usage_buckets:
            return

        # Get unique models from buckets
        models = {b.get("model", "") for b in usage_buckets if b.get("model")}

        # Query prices for those models
        prices = self._get_prices_for_models(models, project_id)

        # Compute costs for each bucket
        for bucket in usage_buckets:
            model = bucket.get("model", "")
            model_prices = prices.get(model, {})
            prompt_cost = model_prices.get("prompt_token_cost", 0.0)
            completion_cost = model_prices.get("completion_token_cost", 0.0)

            input_tokens = bucket.get("sum_input_tokens", 0) or 0
            output_tokens = bucket.get("sum_output_tokens", 0) or 0

            if "input_cost" in requested_cost_metrics:
                bucket["sum_input_cost"] = input_tokens * prompt_cost

            if "output_cost" in requested_cost_metrics:
                bucket["sum_output_cost"] = output_tokens * completion_cost

            if "total_cost" in requested_cost_metrics:
                input_cost = bucket.get("sum_input_cost", input_tokens * prompt_cost)
                output_cost = bucket.get(
                    "sum_output_cost", output_tokens * completion_cost
                )
                bucket["sum_total_cost"] = input_cost + output_cost

    # ------------------------------------------------------------------
    # Cost CRUD
    # ------------------------------------------------------------------

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        assert_non_null_wb_user_id(req)
        created_at = datetime.datetime.now(ZoneInfo("UTC"))

        costs = []
        for llm_id, cost in req.costs.items():
            cost_id = generate_id()

            row: Row = {
                "id": cost_id,
                "created_by": req.wb_user_id,
                "created_at": created_at,
                "pricing_level": "project",
                "pricing_level_id": req.project_id,
                "provider_id": cost.provider_id if cost.provider_id else "default",
                "llm_id": llm_id,
                "effective_date": (
                    cost.effective_date if cost.effective_date else created_at
                ),
                "prompt_token_cost": cost.prompt_token_cost,
                "completion_token_cost": cost.completion_token_cost,
                "prompt_token_cost_unit": cost.prompt_token_cost_unit,
                "completion_token_cost_unit": cost.completion_token_cost_unit,
            }

            costs.append((cost_id, llm_id))

            prepared = LLM_TOKEN_PRICES_TABLE.insert(row).prepare(
                database_type="clickhouse"
            )
            self._insert(
                LLM_TOKEN_PRICES_TABLE.name, prepared.data, prepared.column_names
            )

        return tsi.CostCreateRes(ids=costs)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
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
        query_result = self.ch_client.query(prepared.sql, prepared.parameters)
        results = LLM_TOKEN_PRICES_TABLE.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.CostQueryRes(results=results)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
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
        self.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.CostPurgeRes()
