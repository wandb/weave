# This script populates the llm_token_prices table with the costs for the models that we support from costs.json
# It pulls existing costs from the table and filters out the ones that have no changes
# It then inserts the remaining costs into the table
# It is intended to run on service startup
import json
import math
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, TypedDict

import requests

COST_FILE = "costs.json"


class CostDetails(TypedDict):
    input: float
    output: float
    provider: str


def load_costs_from_json() -> Dict[str, CostDetails]:
    data = {}
    with open(COST_FILE, "r") as file:
        data = json.load(file)
    return data


def filter_out_current_costs(
    current_costs: dict[str, CostDetails],
    new_costs: dict[str, CostDetails],
) -> dict[str, CostDetails]:
    filtered_costs = {}
    for llm_id, cost in new_costs.items():
        existing_cost = current_costs.get(llm_id)
        if (not existing_cost) or (
            not math.isclose(existing_cost["input"], cost["input"], rel_tol=1e-7)
            and not math.isclose(existing_cost["output"], cost["output"], rel_tol=1e-7)
        ):
            filtered_costs[llm_id] = cost
    return filtered_costs


# This function was lifted from clickhouse_trace_server_migrator.py
def get_migrations() -> Dict[int, Dict[str, Optional[str]]]:
    migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
    migration_files = os.listdir(migration_dir)
    migration_map: Dict[int, Dict[str, Optional[str]]] = {}
    max_version = 0
    for file in migration_files:
        if not file.endswith(".up.sql") and not file.endswith(".down.sql"):
            raise Exception(f"Invalid migration file: {file}")
        file_name_parts = file.split("_", 1)
        if len(file_name_parts) <= 1:
            raise Exception(f"Invalid migration file: {file}")
        version = int(file_name_parts[0], 10)
        if version < 1:
            raise Exception(f"Invalid migration file: {file}")

        is_up = file.endswith(".up.sql")

        if version not in migration_map:
            migration_map[version] = {"up": None, "down": None}

        if is_up:
            if migration_map[version]["up"] is not None:
                raise Exception(f"Duplicate migration file for version {version}")
            migration_map[version]["up"] = file
        else:
            if migration_map[version]["down"] is not None:
                raise Exception(f"Duplicate migration file for version {version}")
            migration_map[version]["down"] = file

        if version > max_version:
            max_version = version

    if len(migration_map) == 0:
        raise Exception("No migrations found")

    if max_version != len(migration_map):
        raise Exception(
            f"Invalid migration versioning. Expected {max_version} migrations but found {len(migration_map)}"
        )

    for version in range(1, max_version + 1):
        if version not in migration_map:
            raise Exception(f"Missing migration file for version {version}")
        if migration_map[version]["up"] is None:
            raise Exception(f"Missing up migration file for version {version}")
        if migration_map[version]["down"] is None:
            raise Exception(f"Missing down migration file for version {version}")

    return migration_map


def get_updated_costs() -> Dict[str, CostDetails]:
    url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

    req = requests.get(url)

    if req.status_code != requests.codes.ok:
        print("Token cost file was not found.")
        exit()

    # We expect the fetched json to be a dict with the following structure:
    # TypedDict:
    #   input_cost_per_token: float
    #   output_cost_per_token: float
    #   litellm_provider: str
    raw_costs = req.json()
    costs: Dict[str, CostDetails] = {}
    for k in raw_costs:
        if (
            "input_cost_per_token" not in raw_costs[k]
            or "output_cost_per_token" not in raw_costs[k]
            or k == "sample_spec"
        ):
            pass
        else:
            costs[k] = CostDetails(
                provider=raw_costs[k]["litellm_provider"] or "default",
                input=float(Decimal(raw_costs[k]["input_cost_per_token"])),
                output=float(Decimal(raw_costs[k]["output_cost_per_token"])),
            )
    return costs


def create_new_migration(
    migrations: Dict[int, Dict[str, Optional[str]]],
    new_costs: Dict[str, CostDetails],
) -> str:
    current_time = datetime.now()
    migration_number = str(len(migrations) + 1).zfill(3)

    up_migration_command = """
INSERT INTO llm_token_prices
    (id, pricing_level, pricing_level_id, provider_id, llm_id, effective_date, prompt_token_cost, prompt_token_cost_unit, completion_token_cost, completion_token_cost_unit, created_by, created_at)
VALUES"""

    for llm_id, details in new_costs.items():
        comma = "," if llm_id != list(new_costs.keys())[0] else ""
        provider_id = details.get("provider", "default")
        input_token_cost = details.get("input", 0)
        output_token_cost = details.get("output", 0)
        up_migration_command += f"""{comma}
    (generateUUIDv4(), 'default', 'default', '{provider_id}', '{llm_id}', '{str(current_time)}', {input_token_cost}, 'USD', {output_token_cost}, 'USD', 'system', '{str(current_time)}')"""

    # create the migration file
    migration_file = os.path.join(
        os.path.dirname(__file__), "migrations", f"{migration_number}_seed_costs.up.sql"
    )
    with open(migration_file, "w") as file:
        file.write(up_migration_command)

    down_migration_command = f"""
ALTER TABLE llm_token_prices DELETE WHERE
    created_at = '{str(current_time)}';
    """

    # create the migration file
    migration_file = os.path.join(
        os.path.dirname(__file__),
        "migrations",
        f"{migration_number}_seed_costs.down.sql",
    )
    with open(migration_file, "w") as file:
        file.write(down_migration_command)

    return migration_number


def update_costs_in_json(new_costs: Dict[str, CostDetails]) -> None:
    with open(COST_FILE, "w") as f:
        json.dump(new_costs, f, indent=2)


def main() -> None:
    try:
        new_costs = get_updated_costs()
    except Exception as e:
        print("Failed to get updated costs, ", e)
        return
    print(len(new_costs), "costs fetched")

    try:
        migrations = get_migrations()
    except Exception as e:
        print("Failed to get migrations, ", e)
        return
    print(len(migrations), "migrations found")

    try:
        current_costs = load_costs_from_json()
    except Exception as e:
        print("Failed to load costs from json, ", e)
        return
    print("Loaded", len(current_costs), "costs from json")

    try:
        filtered_costs = filter_out_current_costs(current_costs, new_costs)
    except Exception as e:
        print("Failed to filter out current costs, ", e)
        return
    print(
        "There are",
        len(filtered_costs),
        "costs to insert, after filtering out existing costs",
    )

    if len(filtered_costs) == 0:
        return

    # Create a new migration
    try:
        migration_number = create_new_migration(migrations, filtered_costs)
    except Exception as e:
        print("Failed to create a new migration, ", e)
        return
    print("Created a new migration", migration_number)

    try:
        update_costs_in_json(new_costs)
    except Exception as e:
        print("Failed to update costs in json, ", e)
        return
    print(len(new_costs), "costs written to", COST_FILE)


if __name__ == "__main__":
    main()
