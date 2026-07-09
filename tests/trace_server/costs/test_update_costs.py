import json
import unittest
from datetime import datetime
from unittest.mock import ANY, MagicMock, mock_open, patch

import httpx
import pytest

from weave.trace_server.costs.update_costs import (
    COST_FILE,
    fetch_manual_costs,
    fetch_models_begin_costs,
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
        assert costs == {}

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
        assert costs == expected_costs

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid json")
    def test_get_current_costs_invalid_json(self, mock_file, mock_exists):
        """Test get_current_costs when the costs file contains invalid JSON."""
        mock_exists.return_value = True
        with pytest.raises(json.JSONDecodeError):
            get_current_costs()

    @patch("httpx.Client.get")
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
        frozen_time = datetime(2025, 1, 1, 12, 0, 0)
        with patch("weave.trace_server.costs.update_costs.datetime") as mock_datetime:
            mock_datetime.now.return_value = frozen_time
            mock_datetime.side_effect = datetime
            costs = fetch_new_costs()
        assert "model1" in costs
        assert costs["model1"]["input"] == 0.01
        assert costs["model1"]["output"] == 0.02
        assert costs["model1"]["provider"] == "test_provider"
        assert costs["model1"]["created_at"] == "2025-01-01 12:00:00"

    @patch("httpx.Client.get")
    def test_fetch_new_costs_request_exception(self, mock_get):
        """Test fetch_new_costs when a RequestException occurs."""
        mock_get.side_effect = httpx.RequestError("Test exception")
        with pytest.raises(httpx.RequestError):
            fetch_new_costs()

    @patch("httpx.Client.get")
    def test_fetch_new_costs_invalid_json(self, mock_get):
        """Test fetch_new_costs when the response contains invalid JSON."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Test", "doc", 0)
        mock_get.return_value = mock_response
        with pytest.raises(json.JSONDecodeError):
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
        assert total == 3

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_manual_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_models_begin_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main(
        self,
        mock_get_current_costs,
        mock_fetch_new_costs,
        mock_fetch_models_begin_costs,
        mock_fetch_manual_costs,
        mock_exists,
        mock_file,
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
        mock_fetch_models_begin_costs.return_value = {}
        mock_fetch_manual_costs.return_value = {}
        main()
        mock_file.assert_called_with(ANY, "w")
        args, kwargs = mock_file.call_args
        opened_file_path = args[0]
        assert opened_file_path.endswith(COST_FILE)
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
        assert written_costs == expected_costs

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_manual_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_models_begin_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main_cost_change(
        self,
        mock_get_current_costs,
        mock_fetch_new_costs,
        mock_fetch_models_begin_costs,
        mock_fetch_manual_costs,
        mock_exists,
        mock_file,
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
        mock_fetch_models_begin_costs.return_value = {}
        mock_fetch_manual_costs.return_value = {}
        main()
        mock_file.assert_called_with(ANY, "w")
        args, kwargs = mock_file.call_args
        opened_file_path = args[0]
        assert opened_file_path.endswith(COST_FILE)
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
        assert written_costs == expected_costs

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_manual_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_models_begin_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main_historical_costs_limit(
        self,
        mock_get_current_costs,
        mock_fetch_new_costs,
        mock_fetch_models_begin_costs,
        mock_fetch_manual_costs,
        mock_exists,
        mock_file,
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
        mock_fetch_models_begin_costs.return_value = {}
        mock_fetch_manual_costs.return_value = {}
        main()
        mock_file.assert_called_with(ANY, "w")
        args, kwargs = mock_file.call_args
        opened_file_path = args[0]
        assert opened_file_path.endswith(COST_FILE)
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
        assert written_costs == expected_costs


class TestFetchManualCosts(unittest.TestCase):
    @patch("weave.trace_server.costs.update_costs.os.path.exists")
    def test_missing_file_returns_empty(self, mock_exists):
        """Missing manual_costs.json is fine — returns empty dict, no crash."""
        mock_exists.return_value = False
        assert fetch_manual_costs() == {}

    @patch("weave.trace_server.costs.update_costs.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="not valid json")
    def test_malformed_json_returns_empty(self, mock_file, mock_exists):
        """Malformed JSON is tolerated — returns empty dict, prints warning."""
        mock_exists.return_value = True
        assert fetch_manual_costs() == {}

    @patch("weave.trace_server.costs.update_costs.os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=json.dumps(
            {
                "good-model": [
                    {
                        "provider": "manual",
                        "input": 1.5e-06,
                        "output": 6e-06,
                        "cache_read_input": 2.5e-08,
                        "cache_creation_input": 0.0,
                        "created_at": "2026-05-19 10:13:20",
                    }
                ],
                "bad-non-list": {"input": 1, "output": 2},
                "bad-empty-list": [],
                "bad-missing-fields": [{"provider": "x"}],
            }
        ),
    )
    def test_loads_well_formed_skips_malformed(self, mock_file, mock_exists):
        """Well-formed entries load; malformed entries are skipped, not fatal."""
        mock_exists.return_value = True
        costs = fetch_manual_costs()
        assert set(costs.keys()) == {"good-model"}
        assert costs["good-model"]["provider"] == "manual"
        assert costs["good-model"]["input"] == 1.5e-06
        assert costs["good-model"]["output"] == 6e-06
        assert costs["good-model"]["cache_read_input"] == 2.5e-08
        assert costs["good-model"]["cache_creation_input"] == 0.0
        assert costs["good-model"]["created_at"] == "2026-05-19 10:13:20"

    @patch("weave.trace_server.costs.update_costs.os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=json.dumps(
            {
                "model-with-history": [
                    {
                        "provider": "manual",
                        "input": 1e-06,
                        "output": 2e-06,
                        "cache_read_input": 0,
                        "cache_creation_input": 0,
                        "created_at": "2026-01-01 00:00:00",
                    },
                    {
                        "provider": "manual",
                        "input": 3e-06,
                        "output": 4e-06,
                        "cache_read_input": 0,
                        "cache_creation_input": 0,
                        "created_at": "2026-05-19 00:00:00",
                    },
                ]
            }
        ),
    )
    def test_uses_most_recent_entry_from_history_list(self, mock_file, mock_exists):
        """When an entry has multiple historical costs, the last one wins."""
        mock_exists.return_value = True
        costs = fetch_manual_costs()
        assert costs["model-with-history"]["input"] == 3e-06
        assert costs["model-with-history"]["output"] == 4e-06
        assert costs["model-with-history"]["created_at"] == "2026-05-19 00:00:00"

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("weave.trace_server.costs.update_costs.fetch_manual_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_models_begin_costs")
    @patch("weave.trace_server.costs.update_costs.fetch_new_costs")
    @patch("weave.trace_server.costs.update_costs.get_current_costs")
    def test_main_litellm_overrides_manual(
        self,
        mock_get_current_costs,
        mock_fetch_new_costs,
        mock_fetch_models_begin_costs,
        mock_fetch_manual_costs,
        mock_exists,
        mock_file,
    ):
        """Litellm takes precedence over manual for the same llm_id.

        Manual entries are stopgaps for models litellm hasn't published yet;
        once litellm has authoritative numbers for the same id, those win.
        Manual-only models still flow through when litellm doesn't cover them.
        """
        mock_exists.return_value = True
        mock_get_current_costs.return_value = {}
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mock_fetch_new_costs.return_value = {
            "shared-model": {
                "input": 0.01,
                "output": 0.02,
                "provider": "litellm_provider",
                "created_at": current_time,
            }
        }
        mock_fetch_models_begin_costs.return_value = {}
        mock_fetch_manual_costs.return_value = {
            "shared-model": {
                "input": 0.99,
                "output": 0.99,
                "provider": "manual",
                "cache_read_input": 0,
                "cache_creation_input": 0,
                "created_at": current_time,
            },
            "manual-only-model": {
                "input": 1.5e-06,
                "output": 6e-06,
                "provider": "manual",
                "cache_read_input": 0,
                "cache_creation_input": 0,
                "created_at": current_time,
            },
        }
        main()
        handle = mock_file()
        written_data = "".join(args[0] for args, kwargs in handle.write.call_args_list)
        written_costs = json.loads(written_data)
        # litellm wins for shared-model — manual is silently superseded
        assert written_costs["shared-model"][-1]["input"] == 0.01
        assert written_costs["shared-model"][-1]["provider"] == "litellm_provider"
        # Manual-only model still lands in the checkpoint (no collision)
        assert written_costs["manual-only-model"][-1]["input"] == 1.5e-06
        assert written_costs["manual-only-model"][-1]["provider"] == "manual"


@patch("weave.trace_server.costs.update_costs.os.path.exists")
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data=json.dumps(
        [
            {
                "idPlayground": "openai/gpt-oss-20b",
                "provider": "coreweave",
                "priceCentsPerBillionTokensInput": 5000,
                "priceCentsPerBillionTokensOutput": 20000,
            },
            {"provider": "coreweave", "priceCentsPerBillionTokensInput": 1},
        ]
    ),
)
def test_fetch_models_begin_costs_keys_on_bare_playground_id(mock_file, mock_exists):
    """W&B Inference prices are keyed on the bare idPlayground.

    The inference service echoes the playground id back (e.g. "openai/gpt-oss-20b"),
    so that is the id call usage records and what the cost join matches on. Keying
    under a "coreweave/" prefix would never match, leaving every inference call unpriced.
    A model missing idPlayground is skipped. Cents-per-billion-tokens converts to
    dollars-per-token (divide by 1e11).
    """
    mock_exists.return_value = True
    costs = fetch_models_begin_costs()

    assert set(costs.keys()) == {"openai/gpt-oss-20b"}
    assert "coreweave/openai/gpt-oss-20b" not in costs
    entry = costs["openai/gpt-oss-20b"]
    assert entry["input"] == 5e-08
    assert entry["output"] == 2e-07
    assert entry["provider"] == "coreweave"


if __name__ == "__main__":
    unittest.main()
