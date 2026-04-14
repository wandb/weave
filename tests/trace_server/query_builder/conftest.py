import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip query_builder tests when running with ClickHouse client.

    pytest_collection_modifyitems is a pytest hook that receives ALL collected
    tests for the session, not just tests in this directory — so we filter by
    path. See: https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_collection_modifyitems
    """
    for item in items:
        if "query_builder" in item.path.parts:
            item.add_marker(pytest.mark.skip_clickhouse_client)
