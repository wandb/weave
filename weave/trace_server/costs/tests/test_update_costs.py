import json
import unittest
from datetime import datetime
from unittest.mock import ANY, MagicMock, mock_open, patch

import requests

from weave.trace_server.costs.update_costs import (
    COST_FILE,
    fetch_new_costs,
    get_current_costs,
    main,
    sum_costs,
)


class TestUpdateCosts(unittest.TestCase):
    @patch("os.path.exists")
    def test_get_current_costs_no_file(self, mock_exists):
        """Test get_current_costs when the costs file does not exist."""
        mock_exists.return_value = False
        costs = get_current_costs()
        self.assertEqual(costs, {})

    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"model1": [{"input": 0.01, "output": 0.02, "provider": "test", "created_at": "2021-01-01 00:00:00"}]}',
    )
    def test_get_current_costs_with_file(self, mock_file, mock_exists):
        """Test get_current_costs when the costs file exists and contains valid JSON."""
        mock_exists.return_value = True
        costs = get_current_costs()
        expected_costs = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test",
                    "created_at": "2021-01-01 00:00:00",
                }
            ]
        }
        self.assertEqual(costs, expected_costs)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid json")
    def test_get_current_costs_invalid_json(self, mock_file, mock_exists):
        """Test get_current_costs when the costs file contains invalid JSON."""
        mock_exists.return_value = True
        with self.assertRaises(json.JSONDecodeError):
            get_current_costs()

    @patch("requests.get")
    def test_fetch_new_costs_success(self, mock_get):
        """Test fetch_new_costs with a successful response."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "model1": {
                "input_cost_per_token": "0.01",
                "output_cost_per_token": "0.02",
                "litellm_provider": "test_provider",
            }
        }
        mock_get.return_value = mock_response
        costs = fetch_new_costs()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.assertIn("model1", costs)
        self.assertEqual(costs["model1"]["input"], 0.01)
        self.assertEqual(costs["model1"]["output"], 0.02)
        self.assertEqual(costs["model1"]["provider"], "test_provider")
        self.assertEqual(costs["model1"]["created_at"], current_time)

    @patch("requests.get")
    def test_fetch_new_costs_request_exception(self, mock_get):
        """Test fetch_new_costs when a RequestException occurs."""
        mock_get.side_effect = requests.exceptions.RequestException("Test exception")
        with self.assertRaises(requests.exceptions.RequestException):
            fetch_new_costs()

    @patch("requests.get")
    def test_fetch_new_costs_invalid_json(self, mock_get):
        """Test fetch_new_costs when the response contains invalid JSON."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Test", "doc", 0)
        mock_get.return_value = mock_response
        with self.assertRaises(json.JSONDecodeError):
            fetch_new_costs()

    def test_sum_costs(self):
        """Test sum_costs function."""
        data = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test",
                    "created_at": "2021-01-01 00:00:00",
                }
            ],
            "model2": [
                {
                    "input": 0.02,
                    "output": 0.03,
                    "provider": "test",
                    "created_at": "2021-01-01 00:00:00",
                },
                {
                    "input": 0.025,
                    "output": 0.035,
                    "provider": "test",
                    "created_at": "2021-01-02 00:00:00",
                },
            ],
        }
        total = sum_costs(data)
        self.assertEqual(total, 3)

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main(
        self, mock_get_current_costs, mock_fetch_new_costs, mock_exists, mock_file
    ):
        """Test main function with no cost changes."""
        mock_exists.return_value = True
        mock_get_current_costs.return_value = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test_provider",
                    "created_at": "2021-01-01 00:00:00",
                }
            ]
        }
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mock_fetch_new_costs.return_value = {
            "model1": {
                "input": 0.01,
                "output": 0.02,
                "provider": "test_provider",
                "created_at": current_time,
            },
            "model2": {
                "input": 0.015,
                "output": 0.025,
                "provider": "test_provider",
                "created_at": current_time,
            },
        }
        main()
        mock_file.assert_called_with(ANY, "w")
        args, kwargs = mock_file.call_args
        opened_file_path = args[0]
        self.assertTrue(opened_file_path.endswith(COST_FILE))
        handle = mock_file()
        handle.write.assert_called()
        written_data = "".join(args[0] for args, kwargs in handle.write.call_args_list)
        written_costs = json.loads(written_data)
        expected_costs = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test_provider",
                    "created_at": "2021-01-01 00:00:00",
                }
            ],
            "model2": [
                {
                    "input": 0.015,
                    "output": 0.025,
                    "provider": "test_provider",
                    "created_at": current_time,
                }
            ],
        }
        self.assertEqual(written_costs, expected_costs)

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main_cost_change(
        self, mock_get_current_costs, mock_fetch_new_costs, mock_exists, mock_file
    ):
        """Test main function when cost changes for a model."""
        mock_exists.return_value = True
        mock_get_current_costs.return_value = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test_provider",
                    "created_at": "2021-01-01 00:00:00",
                }
            ]
        }
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mock_fetch_new_costs.return_value = {
            "model1": {
                "input": 0.015,
                "output": 0.02,
                "provider": "test_provider",
                "created_at": current_time,
            }
        }
        main()
        mock_file.assert_called_with(ANY, "w")
        args, kwargs = mock_file.call_args
        opened_file_path = args[0]
        self.assertTrue(opened_file_path.endswith(COST_FILE))
        handle = mock_file()
        handle.write.assert_called()
        written_data = "".join(args[0] for args, kwargs in handle.write.call_args_list)
        written_costs = json.loads(written_data)
        expected_costs = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test_provider",
                    "created_at": "2021-01-01 00:00:00",
                },
                {
                    "input": 0.015,
                    "output": 0.02,
                    "provider": "test_provider",
                    "created_at": current_time,
                },
            ]
        }
        self.assertEqual(written_costs, expected_costs)

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main_historical_costs_limit(
        self, mock_get_current_costs, mock_fetch_new_costs, mock_exists, mock_file
    ):
        """Test main function when historical cost limit is reached."""
        mock_exists.return_value = True
        mock_get_current_costs.return_value = {
            "model1": [
                {
                    "input": 0.01,
                    "output": 0.02,
                    "provider": "test_provider",
                    "created_at": "2021-01-01 00:00:00",
                },
                {
                    "input": 0.015,
                    "output": 0.025,
                    "provider": "test_provider",
                    "created_at": "2021-02-01 00:00:00",
                },
                {
                    "input": 0.02,
                    "output": 0.03,
                    "provider": "test_provider",
                    "created_at": "2021-03-01 00:00:00",
                },
            ]
        }
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mock_fetch_new_costs.return_value = {
            "model1": {
                "input": 0.025,
                "output": 0.035,
                "provider": "test_provider",
                "created_at": current_time,
            }
        }
        main()
        mock_file.assert_called_with(ANY, "w")
        args, kwargs = mock_file.call_args
        opened_file_path = args[0]
        self.assertTrue(opened_file_path.endswith(COST_FILE))
        handle = mock_file()
        handle.write.assert_called()
        written_data = "".join(args[0] for args, kwargs in handle.write.call_args_list)
        written_costs = json.loads(written_data)
        expected_costs = {
            "model1": [
                {
                    "input": 0.015,
                    "output": 0.025,
                    "provider": "test_provider",
                    "created_at": "2021-02-01 00:00:00",
                },
                {
                    "input": 0.02,
                    "output": 0.03,
                    "provider": "test_provider",
                    "created_at": "2021-03-01 00:00:00",
                },
                {
                    "input": 0.025,
                    "output": 0.035,
                    "provider": "test_provider",
                    "created_at": current_time,
                },
            ]
        }
        self.assertEqual(written_costs, expected_costs)


if __name__ == "__main__":
    unittest.main()
