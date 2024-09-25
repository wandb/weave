import clickhouse_connect
import pytest

import weave
from weave.conftest import b64
from weave.tests.trace.util import client_is_sqlite
from weave.trace_server.calls_query_builder import CallsQuery
from weave.trace_server.orm import ParamBuilder


def test_clickhouse_driver_max_memory_usage(client):
    """Unit test for read-side clickhouse_connect settings."""
    if client_is_sqlite(client):
        return

    # make 10 1MB calls
    @weave.op
    def log_big():
        return "a" * 10_000

    for i in range(10):
        log_big()

    # confirm we logged calls
    calls = list(log_big.calls())
    assert len(calls) == 10

    # construct calls query:
    pb = ParamBuilder()
    cq = CallsQuery(project_id=b64(client._project_id()))
    cq.add_field("id")
    cq.add_field("output")

    # clickhouse test settings, with very small 1KB limit
    test_settings = {"max_memory_usage": 1024}

    with pytest.raises(clickhouse_connect.driver.exceptions.DatabaseError) as e:
        list(
            client.server._query_stream(
                cq.as_sql(pb),
                pb.get_params(),
                settings=test_settings,
            )
        )
    assert "DB::Exception: Memory limit (for query) exceeded" in str(e.value)

    # test that large memory usage doesn't crash (2GB)
    test_settings = {"max_memory_usage": 2 * 1024**3}
    raw_res = client.server._query_stream(
        cq.as_sql(pb),
        pb.get_params(),
        settings=test_settings,
    )
    assert len(list(raw_res)) == 10
