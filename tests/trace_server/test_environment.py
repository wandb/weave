import os

import pytest

from weave.trace_server.environment import kafka_producer_max_buffer_size


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
    assert kafka_producer_max_buffer_size() == None
    os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"] = "invalid"
    assert kafka_producer_max_buffer_size() is None
    del os.environ["KAFKA_PRODUCER_MAX_BUFFER_SIZE"]
