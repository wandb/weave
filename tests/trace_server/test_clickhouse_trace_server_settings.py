import importlib

import pytest

from weave.trace_server import clickhouse_trace_server_settings as ch_settings

ENV_KEYS = [
    "WF_CLICKHOUSE_MAX_EXECUTION_TIME",
    "WF_CLICKHOUSE_MAX_ESTIMATED_EXECUTION_TIME",
    "WF_CLICKHOUSE_DISABLE_QUERY_FAILURE_PREDICTION",
    "WF_CLICKHOUSE_MAX_ROWS_TO_READ",
    "WF_CLICKHOUSE_MAX_BYTES_TO_READ",
]


@pytest.fixture
def reload_settings(monkeypatch):
    """Reload the settings module with a clean env, restore on teardown."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    def _reload():
        return importlib.reload(ch_settings)

    yield _reload

    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    importlib.reload(ch_settings)


def test_query_settings_apply_prediction_guards(monkeypatch, reload_settings):
    # Defaults stop queries projected to exceed the normal execution limit.
    settings_module = reload_settings()
    settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    assert settings["max_execution_time"] == settings_module.DEFAULT_MAX_EXECUTION_TIME
    assert (
        settings["max_estimated_execution_time"]
        == settings_module.DEFAULT_MAX_ESTIMATED_EXECUTION_TIME
    )
    assert (
        settings["timeout_before_checking_execution_speed"]
        == settings_module.DEFAULT_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED
    )
    assert settings["timeout_overflow_mode"] == "throw"

    # Estimated-time tracks the configured execution-time override.
    monkeypatch.setenv("WF_CLICKHOUSE_MAX_EXECUTION_TIME", "30")
    settings_module = reload_settings()
    settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    assert settings["max_execution_time"] == 30
    assert settings["max_estimated_execution_time"] == 30
    assert (
        settings["timeout_before_checking_execution_speed"]
        == settings_module.DEFAULT_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED
    )

    # A dedicated override decouples the projection guard from the hard cap.
    monkeypatch.setenv("WF_CLICKHOUSE_MAX_ESTIMATED_EXECUTION_TIME", "5")
    settings_module = reload_settings()
    settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    assert settings["max_execution_time"] == 30
    assert settings["max_estimated_execution_time"] == 5

    # Operators can disable the estimated-time guard entirely.
    monkeypatch.setenv("WF_CLICKHOUSE_DISABLE_QUERY_FAILURE_PREDICTION", "true")
    settings_module = reload_settings()
    settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    assert settings["max_execution_time"] == 30
    assert "max_estimated_execution_time" not in settings
    assert "timeout_before_checking_execution_speed" not in settings
    assert "timeout_overflow_mode" not in settings


def test_command_settings_skip_prediction_guards(monkeypatch, reload_settings):
    # Command paths use base settings — the prediction guard is for read-query
    # scans, not mutations.
    monkeypatch.setenv("WF_CLICKHOUSE_MAX_EXECUTION_TIME", "30")
    settings_module = reload_settings()
    command_settings = settings_module.merge_default_command_settings(
        {"allow_experimental_lightweight_update": 1}
    )
    assert command_settings["max_execution_time"] == 30
    assert command_settings["allow_experimental_lightweight_update"] == 1
    assert "max_estimated_execution_time" not in command_settings
    assert "timeout_before_checking_execution_speed" not in command_settings
    assert "timeout_overflow_mode" not in command_settings


def test_read_scan_caps_apply_to_reads_not_commands(monkeypatch, reload_settings):
    # Unset by default: no read-scan caps.
    settings_module = reload_settings()
    settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    assert "max_rows_to_read" not in settings
    assert "max_bytes_to_read" not in settings
    assert "read_overflow_mode" not in settings

    # Configured caps apply to read queries and throw (not truncate) on overflow.
    monkeypatch.setenv("WF_CLICKHOUSE_MAX_ROWS_TO_READ", "1000000")
    monkeypatch.setenv("WF_CLICKHOUSE_MAX_BYTES_TO_READ", "2000000")
    settings_module = reload_settings()
    settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    assert settings["max_rows_to_read"] == 1000000
    assert settings["max_bytes_to_read"] == 2000000
    assert settings["read_overflow_mode"] == "throw"

    # The caps are for read-query scans, not mutations.
    command_settings = settings_module.CLICKHOUSE_DEFAULT_COMMAND_SETTINGS
    assert "max_rows_to_read" not in command_settings
    assert "max_bytes_to_read" not in command_settings
    assert "read_overflow_mode" not in command_settings
