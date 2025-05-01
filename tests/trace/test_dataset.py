import pytest

import weave
from tests.trace.test_evaluate import Dataset
from weave.trace.context.tests_context import raise_on_captured_errors


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


def test_dataset_caching(client):
    ds = weave.Dataset(rows=[{"a": i} for i in range(200)])
    ref = weave.publish(ds)

    ds2 = ref.get()

    with raise_on_captured_errors():
        assert len(ds2) == 200


def test_dataset_select(client):
    original_rows = [{"id": i, "val": i * 2} for i in range(10)]
    ds = weave.Dataset(rows=original_rows)

    # Select first 3 using range
    selected_ds_range = ds.select(range(3))
    assert len(selected_ds_range) == 3
    assert list(selected_ds_range) == [
        {"id": 0, "val": 0},
        {"id": 1, "val": 2},
        {"id": 2, "val": 4},
    ]

    # Select specific indices using a list
    indices = [5, 2, 8]
    selected_ds_list = ds.select(indices)
    assert len(selected_ds_list) == 3
    assert list(selected_ds_list) == [
        {"id": 5, "val": 10},
        {"id": 2, "val": 4},
        {"id": 8, "val": 16},
    ]

    # Select with an empty list - should raise ValueError
    with pytest.raises(
        ValueError, match="Cannot select rows with an empty set of indices."
    ):
        ds.select([])

    # Select with indices that are out of order
    indices_unordered = [7, 1, 4, 1]
    selected_ds_unordered = ds.select(indices_unordered)
    assert len(selected_ds_unordered) == 4
    assert list(selected_ds_unordered) == [
        {"id": 7, "val": 14},
        {"id": 1, "val": 2},
        {"id": 4, "val": 8},
        {"id": 1, "val": 2},  # Duplicate index is allowed
    ]

    # Ensure original dataset is unchanged
    assert len(ds) == 10
    assert list(ds) == original_rows

    # Test index out of bounds
    with pytest.raises(IndexError):
        ds.select([0, 10])  # 10 is out of bounds

    # Test negative index (should fail in __getitem__)
    with pytest.raises(IndexError):
        ds.select([-1])


def test_add_rows(client):
    ds = weave.Dataset(name="test", rows=[{"a": i} for i in range(10)])
    ref = weave.publish(ds)

    ds = ref.get()
    ds2 = ds.add_rows([{"a": 10}])

    assert len(ds2) == 11
    assert ds2.rows[10]["a"] == 10

    ds3 = ds2.add_rows([{"a": 11}, {"a": 12}, {"a": 13}])
    assert len(ds3) == 14
    assert ds3.rows[12]["a"] == 12
    assert ds3.rows[11]["a"] == 11
    assert ds3.rows[10]["a"] == 10

    # Verify that publishing an already published dataset doesn't
    # do anything.
    ds4 = weave.publish(ds3).get()
    assert ds3.rows == ds4.rows


def test_add_rows_to_unsaved_dataset(client):
    ds = weave.Dataset(rows=[{"a": i} for i in range(10)])
    with pytest.raises(TypeError):
        ds.add_rows([{"a": 10}])
