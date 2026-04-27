import importlib

from weave.trace_server import clickhouse_trace_server_settings as ch_settings


def test_clickhouse_default_query_settings_include_estimated_runtime_guards(
    monkeypatch,
):
    keys = [
        "WF_CLICKHOUSE_MAX_EXECUTION_TIME",
        "WF_CLICKHOUSE_MAX_ESTIMATED_EXECUTION_TIME",
        "WF_CLICKHOUSE_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED",
        "WF_CLICKHOUSE_DISABLE_QUERY_FAILURE_PREDICTION",
    ]

    try:
        # Defaults stop queries projected to exceed the normal execution limit.
        for key in keys:
            monkeypatch.delenv(key, raising=False)
        settings_module = importlib.reload(ch_settings)
        settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
        assert (
            settings["max_execution_time"] == settings_module.DEFAULT_MAX_EXECUTION_TIME
        )
        assert (
            settings["max_estimated_execution_time"]
            == settings_module.DEFAULT_MAX_ESTIMATED_EXECUTION_TIME
        )
        assert (
            settings["timeout_before_checking_execution_speed"]
            == settings_module.DEFAULT_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED
        )
        assert settings["timeout_overflow_mode"] == "throw"

        # Estimated-time defaults track explicit execution-time overrides.
        monkeypatch.setenv("WF_CLICKHOUSE_MAX_EXECUTION_TIME", "30")
        settings_module = importlib.reload(ch_settings)
        settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
        assert settings["max_execution_time"] == 30
        assert settings["max_estimated_execution_time"] == 30

        # Operators can tune prediction separately from the hard timeout.
        monkeypatch.setenv("WF_CLICKHOUSE_MAX_ESTIMATED_EXECUTION_TIME", "12")
        monkeypatch.setenv("WF_CLICKHOUSE_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED", "3")
        settings_module = importlib.reload(ch_settings)
        settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
        assert settings["max_execution_time"] == 30
        assert settings["max_estimated_execution_time"] == 12
        assert settings["timeout_before_checking_execution_speed"] == 3

        # Command paths keep the base defaults without read-query prediction.
        command_settings = settings_module.merge_default_command_settings(
            {"allow_experimental_lightweight_update": 1}
        )
        assert command_settings["max_execution_time"] == 30
        assert command_settings["allow_experimental_lightweight_update"] == 1
        assert "max_estimated_execution_time" not in command_settings
        assert "timeout_before_checking_execution_speed" not in command_settings
        assert "timeout_overflow_mode" not in command_settings

        # Operators can disable the estimated-time guard entirely.
        monkeypatch.setenv("WF_CLICKHOUSE_DISABLE_QUERY_FAILURE_PREDICTION", "true")
        settings_module = importlib.reload(ch_settings)
        settings = settings_module.CLICKHOUSE_DEFAULT_QUERY_SETTINGS
        assert settings["max_execution_time"] == 30
        assert "max_estimated_execution_time" not in settings
        assert "timeout_before_checking_execution_speed" not in settings
        assert "timeout_overflow_mode" not in settings
    finally:
        for key in keys:
            monkeypatch.delenv(key, raising=False)
        importlib.reload(ch_settings)
