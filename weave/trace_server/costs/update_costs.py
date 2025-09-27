# This script populates costs.json with the latest costs from litellm and modelsBegin.json
# We store up to 3 historical costs for each model
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

import httpx

# The file that stores the costs
COST_FILE = "cost_checkpoint.json"
# The file that stores the latest costs from litellm
url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
# The file that stores costs from modelsBegin.json
MODELS_BEGIN_FILE = "../model_providers/modelsBegin.json"
CW_PREFIX = "coreweave/"
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
        with httpx.Client() as client:
            req = client.get(url)
            req.raise_for_status()
    except httpx.RequestError as e:
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


def fetch_models_begin_costs() -> dict[str, CostDetails]:
    """Fetches costs from modelsBegin.json and converts them to the expected format.

    Converts from cents per billion tokens to dollars per token:
    - priceCentsPerBillionTokensInput / 100,000,000,000 = input cost per token
    - priceCentsPerBillionTokensOutput / 100,000,000,000 = output cost per token

    Returns:
        dict[str, CostDetails]: Dictionary of model costs keyed by model ID.

    Examples:
        >>> costs = fetch_models_begin_costs()
        >>> len(costs) > 0
        True
    """
    models_begin_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), MODELS_BEGIN_FILE)
    )

    if not os.path.exists(models_begin_path):
        print(f"modelsBegin.json not found at {models_begin_path}, skipping")
        sys.exit(1)

    try:
        with open(models_begin_path) as f:
            models_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to read modelsBegin.json: {e}")
        sys.exit(1)

    costs: dict[str, CostDetails] = {}
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for model in models_data:
        if not isinstance(model, dict):
            print(
                f"Warning: Skipping non-dict entry in modelsBegin.json: {type(model)}"
            )
            continue

        model_id_playground = model.get("idPlayground")
        provider = model.get("provider", "unknown")
        input_cents_per_billion = model.get("priceCentsPerBillionTokensInput")
        output_cents_per_billion = model.get("priceCentsPerBillionTokensOutput")

        if not model_id_playground:
            print(
                f"Warning: Skipping model with missing idPlayground: {model.get('id', 'unknown')}"
            )
            continue
        if input_cents_per_billion is None:
            print(
                f"Warning: Skipping model {model_id_playground} with missing priceCentsPerBillionTokensInput"
            )
            continue
        if output_cents_per_billion is None:
            print(
                f"Warning: Skipping model {model_id_playground} with missing priceCentsPerBillionTokensOutput"
            )
            continue

        # Convert from cents per billion tokens to cost per token
        # Divide by 100 (cents to dollars) and by 1,000,000,000 (billion to 1)
        input_cost_per_token = float(
            Decimal(input_cents_per_billion) / Decimal("100000000000")
        )
        output_cost_per_token = float(
            Decimal(output_cents_per_billion) / Decimal("100000000000")
        )

        costs[CW_PREFIX + model_id_playground] = CostDetails(
            provider=provider,
            input=input_cost_per_token,
            output=output_cost_per_token,
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

    try:
        models_begin_costs = fetch_models_begin_costs()
        print(f"Fetched {len(models_begin_costs)} costs from modelsBegin.json")
    except Exception as e:
        print("Failed to fetch modelsBegin costs:", e)
        models_begin_costs = {}

    # Merge litellm costs and modelsBegin costs
    all_new_costs = {**new_costs, **models_begin_costs}
    print(
        f"Total costs: {len(all_new_costs)} ({len(new_costs)} from litellm, {len(models_begin_costs)} from modelsBegin.json)"
    )

    new_costs_count = 0

    for k, v in all_new_costs.items():
        if k not in costs:
            costs[k] = [v]
        elif costs[k] and (
            # If the new cost is different from the last cost, we store it
            costs[k][-1]["input"] != v["input"] or costs[k][-1]["output"] != v["output"]
        ):
            new_costs_count += 1
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

    print(
        f"{new_costs_count} new costs written to {file_path} ({sum_costs(costs)} total costs)"
    )


if __name__ == "__main__":
    main()
