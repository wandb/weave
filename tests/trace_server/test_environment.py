import os

import pytest

from weave.trace_server.environment import (
    DEFAULT_REMOTE_SCORER_HTTP_TIMEOUT_SECONDS,
    REMOTE_SCORER_ALLOW_INSECURE_HTTP_ENV,
    REMOTE_SCORER_ALLOWED_HOSTS_ENV,
    REMOTE_SCORER_REQUIRE_STRUCTURED_RESULT_SCHEMA_ENV,
    REMOTE_SCORER_VALIDATE_HOSTS_ENV,
    VALID_CALLS_SHARD_KEYS,
    kafka_producer_max_buffer_size,
    wf_clickhouse_calls_shard_key,
    wf_kafka_project_id_bucket_count,
    wf_scoring_worker_check_cancellation,
    wf_scoring_worker_debounced_scoring_max_call_history,
    wf_scoring_worker_debounced_scoring_max_sampling_rate,
    wf_scoring_worker_kafka_consumer_group_id_override,
    wf_scoring_worker_remote_scorer_allow_insecure_http,
    wf_scoring_worker_remote_scorer_allowed_hosts,
    wf_scoring_worker_remote_scorer_bearer_token,
    wf_scoring_worker_remote_scorer_enabled,
    wf_scoring_worker_remote_scorer_http_timeout_seconds,
    wf_scoring_worker_remote_scorer_require_structured_result_schema,
    wf_scoring_worker_remote_scorer_validate_hosts,
)


@pytest.mark.disable_logging_error_check
def test_kafka_producer_max_buffer_size():
    assert kafka_producer_max_buffer_size() is None
    os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"] = "10000"
    assert kafka_producer_max_buffer_size() == 10000
    os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"] = ""
    assert kafka_producer_max_buffer_size() is None
    os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"] = "10"
    assert kafka_producer_max_buffer_size() == 10
    os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"] = "10.5"
    assert kafka_producer_max_buffer_size() is None
    os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"] = "invalid"
    assert kafka_producer_max_buffer_size() is None
    del os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"]


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_check_cancellation():
    assert wf_scoring_worker_check_cancellation() is False
    os.environ["SCORING_WORKER_CHECK_CANCELLATION"] = "true"
    assert wf_scoring_worker_check_cancellation() is True
    os.environ["SCORING_WORKER_CHECK_CANCELLATION"] = "True"
    assert wf_scoring_worker_check_cancellation() is True
    os.environ["SCORING_WORKER_CHECK_CANCELLATION"] = "false"
    assert wf_scoring_worker_check_cancellation() is False
    os.environ["SCORING_WORKER_CHECK_CANCELLATION"] = ""
    assert wf_scoring_worker_check_cancellation() is False
    os.environ["SCORING_WORKER_CHECK_CANCELLATION"] = "invalid"
    assert wf_scoring_worker_check_cancellation() is False
    del os.environ["SCORING_WORKER_CHECK_CANCELLATION"]


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_debounced_scoring_max_sampling_rate(monkeypatch):
    """Max sampling rate defaults to 0.0, parses floats, clamps to [0, 1], invalid -> 0.0."""
    key = "WF_SCORING_WORKER_DEBOUNCED_SCORING_MAX_SAMPLING_RATE"
    monkeypatch.delenv(key, raising=False)

    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 0.0

    monkeypatch.setenv(key, "0")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 0.0
    monkeypatch.setenv(key, "0.5")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 0.5
    monkeypatch.setenv(key, "1")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 1.0
    monkeypatch.setenv(key, "1.0")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 1.0

    monkeypatch.setenv(key, "-0.1")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 0.0
    monkeypatch.setenv(key, "1.5")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 1.0

    monkeypatch.setenv(key, "invalid")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 0.0
    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_debounced_scoring_max_sampling_rate() == 0.0


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_debounced_scoring_max_call_history(monkeypatch):
    """Max call history defaults to 0, parses ints, clamps to >= 0, invalid -> 0."""
    key = "WF_SCORING_WORKER_DEBOUNCED_SCORING_MAX_CALL_HISTORY"
    monkeypatch.delenv(key, raising=False)

    assert wf_scoring_worker_debounced_scoring_max_call_history() == 0

    monkeypatch.setenv(key, "0")
    assert wf_scoring_worker_debounced_scoring_max_call_history() == 0
    monkeypatch.setenv(key, "500")
    assert wf_scoring_worker_debounced_scoring_max_call_history() == 500
    monkeypatch.setenv(key, "1000")
    assert wf_scoring_worker_debounced_scoring_max_call_history() == 1000

    monkeypatch.setenv(key, "-1")
    assert wf_scoring_worker_debounced_scoring_max_call_history() == 0

    monkeypatch.setenv(key, "invalid")
    assert wf_scoring_worker_debounced_scoring_max_call_history() == 0
    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_debounced_scoring_max_call_history() == 0


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_kafka_consumer_group_id_override():
    assert wf_scoring_worker_kafka_consumer_group_id_override() is None
    os.environ["SCORING_WORKER_KAFKA_CONSUMER_GROUP_ID"] = "test-group-id"
    assert wf_scoring_worker_kafka_consumer_group_id_override() == "test-group-id"
    os.environ["SCORING_WORKER_KAFKA_CONSUMER_GROUP_ID"] = ""
    assert wf_scoring_worker_kafka_consumer_group_id_override() == ""
    os.environ["SCORING_WORKER_KAFKA_CONSUMER_GROUP_ID"] = "another-group"
    assert wf_scoring_worker_kafka_consumer_group_id_override() == "another-group"
    del os.environ["SCORING_WORKER_KAFKA_CONSUMER_GROUP_ID"]


@pytest.mark.parametrize(
    ("env_value", "expected", "raises"),
    [
        (None, "trace_id", None),
        *[(key, key, None) for key in sorted(VALID_CALLS_SHARD_KEYS)],
        *[
            (bad_key, None, ValueError)
            for bad_key in ["random_col", "", "TRACE_ID", "proj_id"]
        ],
    ],
)
def test_wf_clickhouse_calls_shard_key(env_value, expected, raises, monkeypatch):
    """Valid shard keys are accepted; invalid values raise; unset defaults to trace_id."""
    if env_value is None:
        monkeypatch.delenv("WF_CLICKHOUSE_CALLS_SHARD_KEY", raising=False)
    else:
        monkeypatch.setenv("WF_CLICKHOUSE_CALLS_SHARD_KEY", env_value)

    if raises is None:
        assert wf_clickhouse_calls_shard_key() == expected
    else:
        with pytest.raises(raises, match="Invalid WF_CLICKHOUSE_CALLS_SHARD_KEY"):
            wf_clickhouse_calls_shard_key()


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_bearer_token(monkeypatch):
    """Unset, empty, and whitespace-only env values yield None; non-empty values are stripped."""
    key = "WF_SCORING_WORKER_REMOTE_SCORER_BEARER_TOKEN"
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_bearer_token() is None

    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_remote_scorer_bearer_token() is None

    monkeypatch.setenv(key, "   \t  ")
    assert wf_scoring_worker_remote_scorer_bearer_token() is None

    monkeypatch.setenv(key, "static-api-key")
    assert wf_scoring_worker_remote_scorer_bearer_token() == "static-api-key"

    monkeypatch.setenv(key, "  padded-token  ")
    assert wf_scoring_worker_remote_scorer_bearer_token() == "padded-token"


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_enabled(monkeypatch):
    """Remote scoring is off by default; only a case-insensitive ``true`` enables it."""
    key = "WF_SCORING_WORKER_REMOTE_SCORING_ENABLED"
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_enabled() is False

    monkeypatch.setenv(key, "true")
    assert wf_scoring_worker_remote_scorer_enabled() is True
    monkeypatch.setenv(key, "True")
    assert wf_scoring_worker_remote_scorer_enabled() is True

    monkeypatch.setenv(key, "false")
    assert wf_scoring_worker_remote_scorer_enabled() is False
    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_remote_scorer_enabled() is False
    monkeypatch.setenv(key, "1")
    assert wf_scoring_worker_remote_scorer_enabled() is False


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_http_timeout_seconds(monkeypatch):
    """Timeout defaults to 30s; parses positive floats; invalid or non-positive -> default."""
    key = "WF_SCORING_WORKER_REMOTE_HTTP_TIMEOUT_SECONDS"
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_http_timeout_seconds() == (
        DEFAULT_REMOTE_SCORER_HTTP_TIMEOUT_SECONDS
    )

    monkeypatch.setenv(key, "60")
    assert wf_scoring_worker_remote_scorer_http_timeout_seconds() == 60.0
    monkeypatch.setenv(key, "45.5")
    assert wf_scoring_worker_remote_scorer_http_timeout_seconds() == 45.5

    monkeypatch.setenv(key, "0")
    assert wf_scoring_worker_remote_scorer_http_timeout_seconds() == (
        DEFAULT_REMOTE_SCORER_HTTP_TIMEOUT_SECONDS
    )
    monkeypatch.setenv(key, "-1")
    assert wf_scoring_worker_remote_scorer_http_timeout_seconds() == (
        DEFAULT_REMOTE_SCORER_HTTP_TIMEOUT_SECONDS
    )

    monkeypatch.setenv(key, "not-a-number")
    assert wf_scoring_worker_remote_scorer_http_timeout_seconds() == (
        DEFAULT_REMOTE_SCORER_HTTP_TIMEOUT_SECONDS
    )


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_allowed_hosts(monkeypatch):
    """Allowed hosts are comma-separated exact host or host:port strings."""
    key = REMOTE_SCORER_ALLOWED_HOSTS_ENV
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_allowed_hosts() == []

    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_remote_scorer_allowed_hosts() == []

    monkeypatch.setenv(key, "scoring.example.com, api.example.com:8443 ,, localhost ")
    assert wf_scoring_worker_remote_scorer_allowed_hosts() == [
        "scoring.example.com",
        "api.example.com:8443",
        "localhost",
    ]


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_validate_hosts(monkeypatch):
    """Host validation is enabled by default; only case-insensitive false disables it."""
    key = REMOTE_SCORER_VALIDATE_HOSTS_ENV
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_validate_hosts() is True

    monkeypatch.setenv(key, "false")
    assert wf_scoring_worker_remote_scorer_validate_hosts() is False
    monkeypatch.setenv(key, "False")
    assert wf_scoring_worker_remote_scorer_validate_hosts() is False

    monkeypatch.setenv(key, "true")
    assert wf_scoring_worker_remote_scorer_validate_hosts() is True
    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_remote_scorer_validate_hosts() is True
    monkeypatch.setenv(key, "0")
    assert wf_scoring_worker_remote_scorer_validate_hosts() is True


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_allow_insecure_http(monkeypatch):
    """Insecure HTTP is disabled by default; only case-insensitive true enables it."""
    key = REMOTE_SCORER_ALLOW_INSECURE_HTTP_ENV
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_allow_insecure_http() is False

    monkeypatch.setenv(key, "true")
    assert wf_scoring_worker_remote_scorer_allow_insecure_http() is True
    monkeypatch.setenv(key, "True")
    assert wf_scoring_worker_remote_scorer_allow_insecure_http() is True

    monkeypatch.setenv(key, "false")
    assert wf_scoring_worker_remote_scorer_allow_insecure_http() is False
    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_remote_scorer_allow_insecure_http() is False
    monkeypatch.setenv(key, "1")
    assert wf_scoring_worker_remote_scorer_allow_insecure_http() is False


@pytest.mark.disable_logging_error_check
def test_wf_kafka_project_id_bucket_count(monkeypatch):
    """Bucket count defaults to 1, parses ints, floors at 1, falls back on garbage."""
    key = "WF_KAFKA_PROJECT_ID_BUCKET_COUNT"
    monkeypatch.delenv(key, raising=False)
    assert wf_kafka_project_id_bucket_count() == 1

    monkeypatch.setenv(key, "4")
    assert wf_kafka_project_id_bucket_count() == 4
    monkeypatch.setenv(key, "1")
    assert wf_kafka_project_id_bucket_count() == 1
    monkeypatch.setenv(key, "0")
    assert wf_kafka_project_id_bucket_count() == 1
    monkeypatch.setenv(key, "-3")
    assert wf_kafka_project_id_bucket_count() == 1
    monkeypatch.setenv(key, "not-a-number")
    assert wf_kafka_project_id_bucket_count() == 1
    monkeypatch.setenv(key, "")
    assert wf_kafka_project_id_bucket_count() == 1


@pytest.mark.disable_logging_error_check
def test_wf_scoring_worker_remote_scorer_require_structured_result_schema(
    monkeypatch,
):
    """Structured result schema enforcement is enabled by default; only false disables it."""
    key = REMOTE_SCORER_REQUIRE_STRUCTURED_RESULT_SCHEMA_ENV
    monkeypatch.delenv(key, raising=False)
    assert wf_scoring_worker_remote_scorer_require_structured_result_schema() is True

    monkeypatch.setenv(key, "false")
    assert wf_scoring_worker_remote_scorer_require_structured_result_schema() is False
    monkeypatch.setenv(key, "False")
    assert wf_scoring_worker_remote_scorer_require_structured_result_schema() is False

    monkeypatch.setenv(key, "true")
    assert wf_scoring_worker_remote_scorer_require_structured_result_schema() is True
    monkeypatch.setenv(key, "")
    assert wf_scoring_worker_remote_scorer_require_structured_result_schema() is True
    monkeypatch.setenv(key, "0")
    assert wf_scoring_worker_remote_scorer_require_structured_result_schema() is True
