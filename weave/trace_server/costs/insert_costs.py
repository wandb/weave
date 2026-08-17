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
from typing import TypedDict

from clickhouse_connect.driver.client import Client

COST_FILE = "cost_checkpoint.json"
MAX_DEFAULT_COST_ROWS = 10_000

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_current_costs(
    client: Client,
) -> list[tuple[str, float, float, float, float, datetime]]:
    current_costs = client.query(
        f"""
        SELECT
            llm_id,
            prompt_token_cost,
            completion_token_cost,
            cache_read_input_token_cost,
            cache_creation_input_token_cost,
            effective_date
        FROM {COSTS_TABLE}
        WHERE
        created_by = 'system'
        -- There should not ever be more than {MAX_DEFAULT_COST_ROWS} default rows in the table, but just in case we limit
        LIMIT {MAX_DEFAULT_COST_ROWS}
        """
    )
    return current_costs.result_rows


class CostDetails(TypedDict):
    input: float
    output: float
    cache_read_input: float
    cache_creation_input: float
    provider: str
    created_at: str


def load_costs_from_json(file_name: str = COST_FILE) -> dict[str, list[CostDetails]]:
    if not os.path.isabs(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
    else:
        file_path = file_name

    data = {}
    try:
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        logger.exception("JSON decode error")
        raise
    return data


def insert_costs_into_db(client: Client, data: dict[str, list[CostDetails]]) -> None:
    rows = []
    for llm_id, costs in data.items():
        for cost in costs:
            provider_id = cost.get("provider", "default")
            input_token_cost = cost.get("input", 0)
            output_token_cost = cost.get("output", 0)
            cache_read_input_token_cost = cost.get("cache_read_input", 0)
            cache_creation_input_token_cost = cost.get("cache_creation_input", 0)
            date_str = cost.get(
                "created_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
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
                    cache_read_input_token_cost,
                    cache_creation_input_token_cost,
                    "system",
                    created_at,
                ),
            )
    # `rows` above is built in `COST_COLUMNS` order.
    client.insert(COSTS_TABLE, rows, column_names=list(COST_COLUMNS))


def filter_out_current_costs(
    client: Client, new_costs: dict[str, list[CostDetails]]
) -> dict[str, list[CostDetails]]:
    current_costs = get_current_costs(client)
    for (
        llm_id,
        prompt_token_cost,
        completion_token_cost,
        cache_read_input_token_cost,
        cache_creation_input_token_cost,
        effective_date,
    ) in current_costs:
        if llm_id not in new_costs:
            continue
        effective_date_str = effective_date.strftime("%Y-%m-%d %H:%M:%S")
        filtered_costs = []
        for cost in new_costs[llm_id]:
            # Filter out costs that already exist in the database by comparing
            # the prompt, completion, and cache token costs with a relative tolerance
            if not (
                math.isclose(prompt_token_cost, cost["input"], rel_tol=1e-7)
                and math.isclose(completion_token_cost, cost["output"], rel_tol=1e-7)
                and math.isclose(
                    cache_read_input_token_cost,
                    cost.get("cache_read_input", 0),
                    rel_tol=1e-7,
                    abs_tol=1e-12,
                )
                and math.isclose(
                    cache_creation_input_token_cost,
                    cost.get("cache_creation_input", 0),
                    rel_tol=1e-7,
                    abs_tol=1e-12,
                )
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


def pending_costs(client: Client, target_db: str) -> dict[str, list[CostDetails]]:
    """Costs from `cost_checkpoint.json` not yet present in `target_db`.

    Defensive by design: a failure loading or diffing the checkpoint logs and
    returns no pending costs rather than raising, since both callers below
    (the migration hook and the lock-free pre-check) must never crash on it.
    Silent otherwise: this also runs from the read-only pre-check on every
    boot once the schema is caught up, so summary logging belongs to
    `insert_costs`, the one caller that actually inserts.
    """
    client.database = target_db
    try:
        new_costs = load_costs_from_json()
    except Exception as e:
        logger.exception("Failed to load costs from json")
        return {}

    try:
        return filter_out_current_costs(client, new_costs)
    except Exception as e:
        logger.exception("Failed to filter out current costs")
        return {}


def insert_costs(client: Client, target_db: str) -> None:
    new_costs = pending_costs(client, target_db)
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
        logger.exception("Failed to insert costs into db")
        return
    logger.info("Inserted %d costs", sum_costs(new_costs))


def has_pending_costs(client: Client, target_db: str) -> bool:
    """Read-only check for whether any checkpoint costs are missing from `target_db`.

    Runs on the shared migrator client outside the normal migration flow (the
    lock-free pre-check in apply_migrations), so it saves and restores the
    caller's `client.database` instead of leaving it pointed at `target_db`.
    Never raises: a broken check must not break server startup.
    """
    prev_database = client.database
    try:
        return len(pending_costs(client, target_db)) > 0
    except Exception:
        logger.exception("Failed to check for pending costs")
        return False
    finally:
        client.database = prev_database


def costs_schema_is_ready(client: Client, target_db: str) -> bool:
    """Whether `target_db` has a `COSTS_TABLE` carrying every `COST_COLUMNS` column.

    Asks the schema rather than comparing against a hardcoded migration version,
    so adding a cost column cannot leave this gate approving a database whose
    table predates it. Never raises, for the same reason as `has_pending_costs`.
    """
    try:
        result = client.query(
            """
            SELECT count()
            FROM system.columns
            WHERE database = %(database)s
                AND table = %(table)s
                AND name IN %(columns)s
            """,
            parameters={
                "database": target_db,
                "table": COSTS_TABLE,
                "columns": COST_COLUMNS,
            },
        )
    except Exception:
        logger.exception("Failed to check the costs table schema")
        return False
    return int(result.result_rows[0][0]) == len(COST_COLUMNS)


COSTS_TABLE = "llm_token_prices"

# Every column the cost code touches, in the order `insert_costs_into_db` builds
# rows. `get_current_costs` reads a subset, so gating on all of them covers both.
COST_COLUMNS = (
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
    "cache_read_input_token_cost",
    "cache_creation_input_token_cost",
    "created_by",
    "created_at",
)
