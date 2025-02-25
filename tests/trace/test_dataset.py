import pytest

import weave
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
