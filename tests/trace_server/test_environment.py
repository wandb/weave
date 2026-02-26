import os

import pytest

from weave.trace_server.environment import (
    VALID_CALLS_SHARD_KEYS,
    kafka_producer_max_buffer_size,
    wf_clickhouse_calls_shard_key,
    wf_scoring_worker_check_cancellation,
    wf_scoring_worker_kafka_consumer_group_id_override,
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
