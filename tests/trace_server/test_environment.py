import os

import pytest

from weave.trace_server.environment import (
    kafka_producer_max_buffer_size,
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
