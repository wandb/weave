import pytest

import weave
from tests.trace.test_evaluate import Dataset


def test_basic_dataset_lifecycle(client):
    for i in range(2):
        dataset = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
        ref = weave.publish(dataset)
        dataset2 = weave.ref(ref.uri()).get()
        assert (
            list(dataset2.rows)
            == list(dataset.rows)
            == [{"a": 5, "b": 6}, {"a": 7, "b": 10}]
        )


def test_dataset_iteration(client):
    dataset = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    rows = list(dataset)
    assert rows == [{"a": 5, "b": 6}, {"a": 7, "b": 10}]

    # Test that we can iterate multiple times
    rows2 = list(dataset)
    assert rows2 == rows


def test_pythonic_access(client):
    rows = [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}, {"a": 5}]
    ds = weave.Dataset(rows=rows)
    assert len(ds) == 5
    assert ds[0] == {"a": 1}

    with pytest.raises(IndexError):
        ds[-1]


def _top_level_logs(log):
    """Strip out internal logs from the log list"""
    return [l for l in log if not l.startswith("_")]


def test_dataset_laziness(client):
    """
    The intention of this test is to show that local construction of
    a dataset does not trigger any remote operations.
    """
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["ensure_project_exists"]
    client.server.attribute_access_log = []

    length = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == []

    length2 = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == []

    assert length == length2

    for row in dataset:
        log = client.server.attribute_access_log
        assert _top_level_logs(log) == []


def test_published_dataset_laziness(client):
    """
    The intention of this test is to show that publishing a dataset,
    then iterating through the "gotten" version of the dataset has
    minimal remote operations - and importantly delays the fetching
    of the rows until they are actually needed.
    """
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["ensure_project_exists"]
    client.server.attribute_access_log = []

    ref = weave.publish(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["table_create", "obj_create"]
    client.server.attribute_access_log = []

    dataset = ref.get()
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["obj_read"]
    client.server.attribute_access_log = []

    length = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["table_query_stats"]
    client.server.attribute_access_log = []

    length2 = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == []

    assert length == length2

    for i, row in enumerate(dataset):
        log = client.server.attribute_access_log
        # This is the critical part of the test - ensuring that
        # the rows are only fetched when they are actually needed.
        #
        # In a future improvement, we might eagerly fetch the next
        # page of results, which would result in this assertion changing
        # in that there would always be one more "table_query" than
        # the number of pages.
        assert _top_level_logs(log) == ["table_query"] * ((i // 100) + 1)


def test_dataset_from_calls(client):
    @weave.op
    def greet(name: str, age: int) -> str:
        return f"Hello {name}, you are {age}!"

    greet("Alice", 30)
    greet("Bob", 25)

    calls = client.get_calls()
    dataset = weave.Dataset.from_calls(calls)
    rows = list(dataset.rows)

    assert len(rows) == 2
    assert rows[0]["inputs"]["name"] == "Alice"
    assert rows[0]["inputs"]["age"] == 30
    assert rows[0]["output"] == "Hello Alice, you are 30!"
    assert rows[1]["inputs"]["name"] == "Bob"
    assert rows[1]["inputs"]["age"] == 25
    assert rows[1]["output"] == "Hello Bob, you are 25!"
