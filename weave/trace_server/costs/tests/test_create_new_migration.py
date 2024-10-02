import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import pytest

# Import the functions from your script
from weave.trace_server.costs.create_new_migration import (
    CostDetails,
    create_new_migration,
    filter_out_current_costs,
    get_migrations,
    get_updated_costs,
    load_costs_from_json,
    update_costs_in_json,
)

# Constants for testing
TEST_COSTS_JSON = "test_costs.json"
TEST_MIGRATIONS_DIR = "test_migrations"


# Helper function to clean up test files/directories
def cleanup_test_environment() -> None:
    if os.path.exists(TEST_COSTS_JSON):
        os.remove(TEST_COSTS_JSON)
    if os.path.exists(TEST_MIGRATIONS_DIR):
        for f in os.listdir(TEST_MIGRATIONS_DIR):
            os.remove(os.path.join(TEST_MIGRATIONS_DIR, f))
        os.rmdir(TEST_MIGRATIONS_DIR)


@pytest.fixture(autouse=True)
def run_around_tests() -> Iterator[None]:
    # Code that will run before each test
    cleanup_test_environment()
    yield
    # Code that will run after each test
    cleanup_test_environment()


def test_get_updated_costs() -> None:
    # Mock the requests.get call
    sample_response = {
        "model1": {
            "input_cost_per_token": "0.001",
            "output_cost_per_token": "0.002",
            "litellm_provider": "provider1",
        },
        "model2": {
            "input_cost_per_token": "0.003",
            "output_cost_per_token": "0.004",
            "litellm_provider": "provider2",
        },
    }

    def mock_get(*args: Any, **kwargs: Any) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_response
        return mock_resp

    with patch("requests.get", mock_get):
        costs = get_updated_costs()
        assert len(costs) == 2
        assert costs == {
            "model1": CostDetails(
                provider="provider1",
                input=float(Decimal("0.001")),
                output=float(Decimal("0.002")),
            ),
            "model2": CostDetails(
                provider="provider2",
                input=float(Decimal("0.003")),
                output=float(Decimal("0.004")),
            ),
        }


def test_load_costs_from_json() -> None:
    costs_file = os.path.join(os.getcwd(), TEST_COSTS_JSON)

    # Create a sample costs.json file
    sample_costs = {
        "model1": {
            "provider": "provider1",
            "input": 0.001,
            "output": 0.002,
        }
    }
    with open(costs_file, "w") as f:
        json.dump(sample_costs, f)

    # Call the function with the test file
    costs = load_costs_from_json(costs_file)
    assert costs == sample_costs


def test_filter_out_current_costs() -> None:
    current_costs = {
        "model1": CostDetails(provider="provider1", input=0.001, output=0.002),
        "model2": CostDetails(provider="provider2", input=0.003, output=0.004),
    }
    new_costs = {
        "model1": CostDetails(
            provider="provider1", input=0.001, output=0.002
        ),  # No change
        "model2": CostDetails(
            provider="provider2", input=0.0035, output=0.004
        ),  # Input changed
        "model3": CostDetails(
            provider="provider3", input=0.005, output=0.006
        ),  # New model
    }

    filtered_costs = filter_out_current_costs(current_costs, new_costs)
    assert len(filtered_costs) == 2
    assert "model2" in filtered_costs
    assert "model3" in filtered_costs
    assert "model1" not in filtered_costs


def test_get_migrations() -> None:
    migrations_dir = os.path.join(os.getcwd(), TEST_MIGRATIONS_DIR)
    migration_files = [
        "001_init.up.sql",
        "001_init.down.sql",
        "002_add_table.up.sql",
        "002_add_table.down.sql",
    ]

    # Create a test migrations directory with sample files
    os.makedirs(migrations_dir, exist_ok=True)

    for file in migration_files:
        open(os.path.join(migrations_dir, file), "a").close()

    # Call get_migrations with the test migrations directory
    migrations = get_migrations(migrations_dir=migrations_dir)
    assert len(migrations) == 2
    assert migrations[1]["up"] == "001_init.up.sql"
    assert migrations[1]["down"] == "001_init.down.sql"
    assert migrations[2]["up"] == "002_add_table.up.sql"
    assert migrations[2]["down"] == "002_add_table.down.sql"


def test_create_new_migration() -> None:
    # Prepare test data
    migration_number = "003"
    new_costs = {
        "model1": CostDetails(provider="provider1", input=0.001, output=0.002),
        "model2": CostDetails(provider="provider2", input=0.003, output=0.004),
    }

    # Mock current time
    current_time_str = "2023-10-10 10:10:10"
    with patch(
        "weave.trace_server.costs.create_new_migration.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime.strptime(
            current_time_str, "%Y-%m-%d %H:%M:%S"
        )
        mock_datetime.now.strftime.return_value = current_time_str

        test_migrations_dir = os.path.join(os.getcwd(), "test_migrations")
        os.makedirs(test_migrations_dir, exist_ok=True)

        # Call the function with the test migrations directory
        create_new_migration(
            migration_number, new_costs, migrations_dir=test_migrations_dir
        )

        # Check that migration files are created
        up_migration_file = os.path.join(
            os.getcwd(), TEST_MIGRATIONS_DIR, f"{migration_number}_seed_costs.up.sql"
        )
        down_migration_file = os.path.join(
            os.getcwd(), TEST_MIGRATIONS_DIR, f"{migration_number}_seed_costs.down.sql"
        )

        assert os.path.exists(up_migration_file)
        assert os.path.exists(down_migration_file)

        # Verify the content of the up migration file
        with open(up_migration_file, "r") as f:
            content = f.read()
            assert "INSERT INTO llm_token_prices" in content
            assert (
                "(generateUUIDv4(), 'default', 'default', 'provider1', 'model1'"
                in content
            )
            assert (
                "(generateUUIDv4(), 'default', 'default', 'provider2', 'model2'"
                in content
            )

        # Verify the content of the down migration file
        with open(down_migration_file, "r") as f:
            content = f.read()
            assert "ALTER TABLE llm_token_prices DELETE WHERE" in content
            assert f"created_at = '{current_time_str}'" in content


def test_update_costs_in_json() -> None:
    costs_file = os.path.join(os.getcwd(), TEST_COSTS_JSON)

    # Create a sample costs.json file
    new_costs = {
        "model1": CostDetails(provider="provider1", input=0.001, output=0.002),
        "model2": CostDetails(provider="provider2", input=0.003, output=0.004),
    }

    # Mock COST_FILE to point to the test file
    update_costs_in_json(new_costs, costs_file)

    # Verify that the file is created and contains the correct data
    assert os.path.exists(costs_file)
    with open(costs_file, "r") as f:
        data = json.load(f)
        assert data == new_costs
