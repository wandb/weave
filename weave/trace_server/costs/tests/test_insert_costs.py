# weave/trace_server/costs/tests/test_insert_costs.py

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock, mock_open, patch

# Import the module to be tested
from weave.trace_server.costs import insert_costs


class TestInsertCosts(unittest.TestCase):
    def setUp(self):
        # Initialize common variables for the tests
        self.client = MagicMock()
        self.target_db = "default"
        self.sample_costs_json = {
            "llm_model_1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "provider_1",
                    "created_at": "2023-10-01 12:00:00",
                }
            ],
            "llm_model_2": [
                {
                    "input": 0.015,
                    "output": 0.025,
                    "provider": "provider_2",
                    "created_at": "2023-10-02 13:30:00",
                }
            ],
        }
        self.sample_current_costs = [
            (
                "llm_model_1",
                0.01,
                0.02,
                datetime.strptime("2023-10-01 12:00:00", "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                ),
            ),
            (
                "llm_model_3",
                0.02,
                0.03,
                datetime.strptime("2023-10-02 13:30:00", "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                ),
            ),
        ]
        self.mock_uuid = str(uuid.uuid4())
        self.mock_now = datetime.now()

    @patch("weave.trace_server.costs.insert_costs.open", new_callable=mock_open)
    @patch("weave.trace_server.costs.insert_costs.json.load")
    def test_load_costs_from_json(self, mock_json_load, mock_file_open):
        # Mock json.load to return sample_costs_json
        mock_json_load.return_value = self.sample_costs_json

        # Call the function
        result = insert_costs.load_costs_from_json()

        # Assertions
        mock_file_open.assert_called_once_with(ANY, "r")
        args, kwargs = mock_file_open.call_args
        opened_file_path = args[0]
        self.assertTrue(opened_file_path.endswith(insert_costs.COST_FILE))
        mock_json_load.assert_called_once()
        self.assertEqual(result, self.sample_costs_json)

    @patch("weave.trace_server.costs.insert_costs.get_current_costs")
    def test_filter_out_current_costs(self, mock_get_current_costs):
        # Mock current costs
        mock_get_current_costs.return_value = self.sample_current_costs

        # Call the function
        filtered_costs = insert_costs.filter_out_current_costs(
            self.client, self.sample_costs_json
        )

        # Expected result after filtering out 'llm_model_1' which already exists
        expected_filtered_costs = {"llm_model_2": self.sample_costs_json["llm_model_2"]}

        # Assertions
        mock_get_current_costs.assert_called_once_with(self.client)
        self.assertEqual(filtered_costs, expected_filtered_costs)

    @patch("weave.trace_server.costs.insert_costs.uuid.uuid4")
    @patch("weave.trace_server.costs.insert_costs.datetime")
    def test_insert_costs_into_db(self, mock_datetime, mock_uuid4):
        # Mock uuid4 and datetime
        mock_uuid4.return_value = self.mock_uuid
        mock_datetime.strptime.side_effect = datetime.strptime
        mock_datetime.now.return_value = self.mock_now

        # Data to insert
        data_to_insert = {"llm_model_2": self.sample_costs_json["llm_model_2"]}

        # Call the function
        insert_costs.insert_costs_into_db(self.client, data_to_insert)

        # Prepare expected rows
        expected_rows = []
        for cost in data_to_insert["llm_model_2"]:
            date_str = cost.get(
                "created_at", self.mock_now.strftime("%Y-%m-%d %H:%M:%S")
            )
            created_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            expected_rows.append(
                (
                    self.mock_uuid,
                    "default",
                    "default",
                    cost.get("provider", "default"),
                    "llm_model_2",
                    created_at,
                    cost.get("input", 0),
                    "USD",
                    cost.get("output", 0),
                    "USD",
                    "system",
                    created_at,
                )
            )

        # Assertions
        self.client.insert.assert_called_once_with(
            "llm_token_prices",
            expected_rows,
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

    @patch("weave.trace_server.costs.insert_costs.logger")
    @patch("weave.trace_server.costs.insert_costs.insert_costs_into_db")
    @patch("weave.trace_server.costs.insert_costs.filter_out_current_costs")
    @patch("weave.trace_server.costs.insert_costs.load_costs_from_json")
    def test_insert_costs(
        self, mock_load_json, mock_filter_costs, mock_insert_db, mock_logger
    ):
        # Mock the methods
        mock_load_json.return_value = self.sample_costs_json
        mock_filter_costs.return_value = {
            "llm_model_2": self.sample_costs_json["llm_model_2"]
        }

        # Call the function
        insert_costs.insert_costs(self.client, self.target_db)

        # Assertions
        mock_load_json.assert_called_once()
        mock_filter_costs.assert_called_once_with(self.client, self.sample_costs_json)
        mock_insert_db.assert_called_once_with(
            self.client, mock_filter_costs.return_value
        )
        mock_logger.info.assert_any_call("Loaded %d costs from json", 2)
        mock_logger.info.assert_any_call(
            "There are %d costs to insert, after filtering out existing costs", 1
        )
        mock_logger.info.assert_any_call("Inserted %d costs", 1)

    @patch("weave.trace_server.costs.insert_costs.logger")
    @patch("weave.trace_server.costs.insert_costs.load_costs_from_json")
    def test_insert_costs_load_exception(self, mock_load_json, mock_logger):
        # Simulate an exception during JSON loading
        e = Exception("Load error")
        mock_load_json.side_effect = e

        # Call the function
        insert_costs.insert_costs(self.client, self.target_db)

        # Assertions
        mock_load_json.assert_called_once()
        mock_logger.error.assert_called_once_with(
            "Failed to load costs from json, %s", e
        )

    @patch("weave.trace_server.costs.insert_costs.logger")
    @patch("weave.trace_server.costs.insert_costs.filter_out_current_costs")
    @patch("weave.trace_server.costs.insert_costs.load_costs_from_json")
    def test_insert_costs_filter_exception(
        self, mock_load_json, mock_filter_costs, mock_logger
    ):
        # Mock the methods
        mock_load_json.return_value = self.sample_costs_json
        e = Exception("Filter error")
        mock_filter_costs.side_effect = e

        # Call the function
        insert_costs.insert_costs(self.client, self.target_db)

        # Assertions
        mock_load_json.assert_called_once()
        mock_filter_costs.assert_called_once_with(self.client, self.sample_costs_json)
        mock_logger.error.assert_called_once_with(
            "Failed to filter out current costs, %s", e
        )

    @patch("weave.trace_server.costs.insert_costs.logger")
    @patch("weave.trace_server.costs.insert_costs.insert_costs_into_db")
    @patch("weave.trace_server.costs.insert_costs.filter_out_current_costs")
    @patch("weave.trace_server.costs.insert_costs.load_costs_from_json")
    def test_insert_costs_insert_exception(
        self, mock_load_json, mock_filter_costs, mock_insert_db, mock_logger
    ):
        # Mock the methods
        mock_load_json.return_value = self.sample_costs_json
        mock_filter_costs.return_value = self.sample_costs_json
        e = Exception("Insert error")
        mock_insert_db.side_effect = e

        # Call the function
        insert_costs.insert_costs(self.client, self.target_db)

        # Assertions
        mock_load_json.assert_called_once()
        mock_filter_costs.assert_called_once_with(self.client, self.sample_costs_json)
        mock_insert_db.assert_called_once_with(self.client, self.sample_costs_json)
        mock_logger.error.assert_called_once_with(
            "Failed to insert costs into db, %s", e
        )

    @patch("weave.trace_server.costs.insert_costs.logger")
    @patch("weave.trace_server.costs.insert_costs.insert_costs_into_db")
    @patch("weave.trace_server.costs.insert_costs.filter_out_current_costs")
    @patch("weave.trace_server.costs.insert_costs.load_costs_from_json")
    def test_insert_costs_no_new_costs(
        self, mock_load_json, mock_filter_costs, mock_insert_db, mock_logger
    ):
        # Mock the methods
        mock_load_json.return_value = self.sample_costs_json
        mock_filter_costs.return_value = {}

        # Call the function
        insert_costs.insert_costs(self.client, self.target_db)

        # Assertions
        mock_load_json.assert_called_once()
        mock_filter_costs.assert_called_once_with(self.client, self.sample_costs_json)
        mock_insert_db.assert_not_called()
        mock_logger.info.assert_any_call("Loaded %d costs from json", 2)
        mock_logger.info.assert_any_call(
            "There are %d costs to insert, after filtering out existing costs", 0
        )


if __name__ == "__main__":
    unittest.main()
