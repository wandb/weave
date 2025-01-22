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


def test_dataset_laziness(client):
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == ["ensure_project_exists"]
    client.server.attribute_access_log = []

    length = len(dataset)
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == []

    length2 = len(dataset)
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == []

    assert length == length2

    i = 0
    for row in dataset:
        log = client.server.attribute_access_log
        assert [l for l in log if not l.startswith("_")] == []
        i += 1


def test_published_dataset_laziness(client):
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == ["ensure_project_exists"]
    client.server.attribute_access_log = []

    ref = weave.publish(dataset)
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == ["table_create", "obj_create"]
    client.server.attribute_access_log = []

    dataset = ref.get()
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == ["obj_read"]
    client.server.attribute_access_log = []

    length = len(dataset)
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == ["table_query_stats"]
    client.server.attribute_access_log = []

    length2 = len(dataset)
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == []

    assert length == length2

    i = 0
    for row in dataset:
        log = client.server.attribute_access_log
        assert [l for l in log if not l.startswith("_")] == ["table_query"] * (
            (i // 100) + 1
        )
        i += 1
