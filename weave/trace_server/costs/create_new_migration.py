# This script creates a new migration for the llm_token_prices table
# It pulls existing costs from costs.json and updates them with the latest costs from the litellm model_prices_and_context_window.json file
# It then updates costs.json with the new costs
# costs.json is a file that contains the most updated costs in the db from the migrations
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


def load_costs_from_json(file_name: str = COST_FILE) -> Dict[str, CostDetails]:
    if not os.path.isabs(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
    else:
        file_path = file_name

    data = {}
    with open(file_path, "r") as file:
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
            or not math.isclose(existing_cost["output"], cost["output"], rel_tol=1e-7)
        ):
            filtered_costs[llm_id] = cost
    return filtered_costs


# This function was mostly lifted from clickhouse_trace_server_migrator._get_migrations
def get_migrations(
    migrations_dir: str = "migrations",
) -> Dict[int, Dict[str, Optional[str]]]:
    if not os.path.isabs(migrations_dir):
        migration_path = os.path.join(os.path.dirname(__file__), migrations_dir)
    else:
        migration_path = migrations_dir

    if not os.path.exists(migration_path):
        os.makedirs(migration_path)
    migration_files = os.listdir(migration_path)
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
        return {}

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


def create_new_migration(
    migration_number: str,
    new_costs: Dict[str, CostDetails],
    migrations_dir: str = "migrations",
) -> None:
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # create the up migration file
    up_migration_command = """
INSERT INTO llm_token_prices
    (id, pricing_level, pricing_level_id, provider_id, llm_id, effective_date, prompt_token_cost, prompt_token_cost_unit, completion_token_cost, completion_token_cost_unit, created_by, created_at)
VALUES"""

    for idx, (llm_id, details) in enumerate(new_costs.items()):
        comma = "," if idx != 0 else ""
        provider_id = details.get("provider", "default")
        input_token_cost = details.get("input", 0)
        output_token_cost = details.get("output", 0)
        up_migration_command += f"""{comma}
    (generateUUIDv4(), 'default', 'default', '{provider_id}', '{llm_id}', '{str(current_time)}', {input_token_cost}, 'USD', {output_token_cost}, 'USD', 'system', '{current_time}')"""

    # create the migration file
    migration_file = os.path.join(
        os.path.dirname(__file__),
        migrations_dir,
        f"{migration_number}_seed_costs.up.sql",
    )
    with open(migration_file, "w") as file:
        file.write(up_migration_command)

    # create the down migration file
    down_migration_command = f"""
ALTER TABLE llm_token_prices DELETE WHERE
    created_at = '{current_time}';
    """

    # create the migration file
    migration_file = os.path.join(
        os.path.dirname(__file__),
        migrations_dir,
        f"{migration_number}_seed_costs.down.sql",
    )
    with open(migration_file, "w") as file:
        file.write(down_migration_command)


def update_costs_in_json(
    new_costs: Dict[str, CostDetails], file_name: str = COST_FILE
) -> None:
    if not os.path.isabs(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
    else:
        file_path = file_name

    with open(file_path, "w") as f:
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
        migration_number = str(len(migrations) + 1).zfill(3)
        create_new_migration(migration_number, filtered_costs)
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
