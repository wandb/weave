import pytest


def pytest_collection_modifyitems(items):
    # These are SQL-generation unit tests; keep them in the SQLite trace_server run
    # and exclude only this directory from the ClickHouse CI shard.
    for item in items:
        if "query_builder" in item.path.parts:
            item.add_marker(pytest.mark.skip_clickhouse_client)
