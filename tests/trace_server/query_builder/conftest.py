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


@pytest.fixture(autouse=True)
def enable_heavy_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default the heavy-LIKE candidate-CTE flag on for query_builder tests.

    The new bloom-eligible path is gated by `WF_CALLS_MERGED_HEAVY_INDEXES`;
    the SQL assertions in this directory pin the post-flag shape. Tests that
    need the off-path call
    `monkeypatch.delenv("WF_CALLS_MERGED_HEAVY_INDEXES", raising=False)`
    inside the test body.
    """
    monkeypatch.setenv("WF_CALLS_MERGED_HEAVY_INDEXES", "true")
