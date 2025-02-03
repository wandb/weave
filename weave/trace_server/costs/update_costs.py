# This script populates costs.json with the latest costs from litellm
# We store up to 3 historical costs for each model
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

import requests

# The file that stores the costs
COST_FILE = "cost_checkpoint.json"
# The file that stores the latest costs from litellm
url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
# Amount of historical costs to store for each model
HISTORICAL_COSTS = 3


class CostDetails(TypedDict):
    input: float
    output: float
    provider: str
    created_at: str


# Grabs the current costs from the file(costs.json)
def get_current_costs(file_name: str = COST_FILE) -> dict[str, list[CostDetails]]:
    if not os.path.isabs(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
    else:
        file_path = file_name

    if not os.path.exists(file_path):
        print("No costs file found, will create it")
        return {}

    try:
        with open(file_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print("Failed to parse existing costs file:", e)
        raise


# Fetches the latest costs from the file(litellm)
def fetch_new_costs() -> dict[str, CostDetails]:
    try:
        req = requests.get(url)
        req.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to fetch new costs:", e)
        raise

    try:
        raw_costs = req.json()
    except json.JSONDecodeError as e:
        print("Failed to parse JSON:", e)
        raise

    costs: dict[str, CostDetails] = {}
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for k in raw_costs:
        if (
            "input_cost_per_token" not in raw_costs[k]
            or "output_cost_per_token" not in raw_costs[k]
            or k == "sample_spec"
        ):
            continue

        costs[k] = CostDetails(
            provider=raw_costs[k].get("litellm_provider", "default"),
            input=float(Decimal(raw_costs[k].get("input_cost_per_token", 0))),
            output=float(Decimal(raw_costs[k].get("output_cost_per_token", 0))),
            created_at=current_time,
        )

    return costs


def sum_costs(data: dict[str, list[CostDetails]]) -> int:
    total_costs = 0
    for costs in data.values():
        if isinstance(costs, list):
            total_costs += len(costs)
    return total_costs


def main(file_name: str = COST_FILE) -> None:
    if not os.path.isabs(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
    else:
        file_path = file_name

    try:
        costs = get_current_costs(file_name)
    except Exception as e:
        print("Failed to get current costs:", e)
        return

    try:
        new_costs = fetch_new_costs()
    except Exception as e:
        print("Failed to fetch new costs:", e)
        return

    for k, v in new_costs.items():
        if k not in costs:
            costs[k] = [v]
        elif costs[k] and (
            # If the new cost is different from the last cost, we store it
            costs[k][-1]["input"] != v["input"] or costs[k][-1]["output"] != v["output"]
        ):
            # We store up to 3 historical costs for each model
            if len(costs[k]) < HISTORICAL_COSTS:
                costs[k].append(v)
            else:
                # remove oldest cost
                costs[k].pop(0)
                costs[k].append(v)

    # output costs to costs.json
    try:
        with open(file_path, "w") as f:
            json.dump(costs, f, indent=2)
    except Exception as e:
        print("Failed to write updated costs to file:", e)

    print(sum_costs(costs), "costs written to", file_path)


if __name__ == "__main__":
    main()
