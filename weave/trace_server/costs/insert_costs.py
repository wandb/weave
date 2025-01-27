# This script populates the llm_token_prices table with the costs for the models that we support from costs.json
# It pulls existing costs from the table and filters out the ones that have no changes
# It then inserts the remaining costs into the table
# It is intended to run on migration
import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, TypedDict

from clickhouse_connect.driver.client import Client

COST_FILE = "cost_checkpoint.json"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_current_costs(
    client: Client,
) -> list[tuple[str, float, float, datetime]]:
    current_costs = client.query(
        """
        SELECT
            llm_id,
            prompt_token_cost,
            completion_token_cost,
            effective_date
        FROM llm_token_prices
        WHERE
        created_by = 'system'
        -- There should not ever be more than 10000 default rows in the table, but just in case we limit
        LIMIT 10000
        """
    )
    return current_costs.result_rows


class CostDetails(TypedDict):
    input: float
    output: float
    provider: str
    created_at: str


def load_costs_from_json(file_name: str = COST_FILE) -> dict[str, list[CostDetails]]:
    if not os.path.isabs(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
    else:
        file_path = file_name

    data = {}
    try:
        with open(file_path) as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        logger.exception("JSON decode error: %s", e)
        raise
    return data


def insert_costs_into_db(client: Client, data: dict[str, list[CostDetails]]) -> None:
    rows = []
    for llm_id, costs in data.items():
        for cost in costs:
            provider_id = cost.get("provider", "default")
            input_token_cost = cost.get("input", 0)
            output_token_cost = cost.get("output", 0)
            date_str = cost.get(
                "created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            created_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            rows.append(
                (
                    str(uuid.uuid4()),
                    "default",
                    "default",
                    provider_id,
                    llm_id,
                    created_at,
                    input_token_cost,
                    "USD",
                    output_token_cost,
                    "USD",
                    "system",
                    created_at,
                ),
            )
    # Insert the data into the table
    client.insert(
        "llm_token_prices",
        rows,
        column_names=[
            "id",
            "pricing_level",
            "pricing_level_id",
            "provider_id",
            "llm_id",
            "effective_date",
            "prompt_token_cost",
            "prompt_token_cost_unit",
            "completion_token_cost",
            "completion_token_cost_unit",
            "created_by",
            "created_at",
        ],
    )


def filter_out_current_costs(
    client: Client, new_costs: dict[str, list[CostDetails]]
) -> dict[str, list[CostDetails]]:
    current_costs = get_current_costs(client)
    for (
        llm_id,
        prompt_token_cost,
        completion_token_cost,
        effective_date,
    ) in current_costs:
        if llm_id not in new_costs:
            continue
        effective_date_str = effective_date.strftime("%Y-%m-%d %H:%M:%S")
        filtered_costs = []
        for cost in new_costs[llm_id]:
            # Filter out costs that already exist in the database by comparing
            # the prompt and completion token costs with a relative tolerance
            if not (
                math.isclose(prompt_token_cost, cost["input"], rel_tol=1e-7)
                and math.isclose(completion_token_cost, cost["output"], rel_tol=1e-7)
                and effective_date_str == cost["created_at"]
            ):
                filtered_costs.append(cost)
        if len(filtered_costs) == 0:
            del new_costs[llm_id]
        else:
            new_costs[llm_id] = filtered_costs
    return new_costs


def sum_costs(data: dict[str, list[CostDetails]]) -> float:
    total_costs = 0
    for costs in data.values():
        total_costs += len(costs)
    return total_costs


def insert_costs(client: Client, target_db: str) -> None:
    client.database = target_db
    # Get costs from json
    try:
        new_costs = load_costs_from_json()
    except Exception as e:
        logger.exception("Failed to load costs from json, %s", e)
        return
    logger.info("Loaded %d costs from json", sum_costs(new_costs))

    # filter out current costs
    try:
        new_costs = filter_out_current_costs(client, new_costs)
    except Exception as e:
        logger.exception("Failed to filter out current costs, %s", e)
        return

    logger.info(
        "There are %d costs to insert, after filtering out existing costs",
        sum_costs(new_costs),
    )

    if len(new_costs) == 0:
        return

    # Attempt to insert the costs into the table
    try:
        insert_costs_into_db(client, new_costs)
    except Exception as e:
        logger.exception("Failed to insert costs into db, %s", e)
        return
    logger.info("Inserted %d costs", sum_costs(new_costs))


# We only want to insert costs if the target db version is 5 or higher
# because the costs table was added in migration 5
def should_insert_costs(
    db_curr_version: int, db_target_version: Optional[int] = None
) -> bool:
    return db_target_version is None or (
        db_target_version >= 5 and db_curr_version < db_target_version
    )
