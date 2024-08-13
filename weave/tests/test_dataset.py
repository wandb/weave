import pytest

import weave


def test_dataset_append_basic(client):
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}])
    ds.append({"a": 3, "b": 4})
    ref = weave.publish(ds)

    ds2 = ref.get()
    assert ds2 == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
    ]
    ds2.append({"a": 5, "b": 6})
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3 == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]


@pytest.mark.xfail(reason="Table API does not properly handle objects yet")
def test_dataset_append_objects(client):
    class Thing(weave.Object):
        val: int

    ds = weave.Dataset(rows=[{"a": Thing(val=1), "b": Thing(val=2)}])
    ds.append({"a": Thing(val=3), "b": Thing(val=4)})
    ref = weave.publish(ds)

    ds2 = ref.get()
    assert ds2 == [
        {"a": Thing(val=1), "b": Thing(val=2)},
        {"a": Thing(val=3), "b": Thing(val=4)},
    ]

    ds2.append({"a": Thing(val=5), "b": Thing(val=6)})
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3 == [
        {"a": Thing(val=1), "b": Thing(val=2)},
        {"a": Thing(val=3), "b": Thing(val=4)},
        {"a": Thing(val=5), "b": Thing(val=6)},
    ]


def test_dataset_append_nested(client):
    ds = weave.Dataset(rows=[{"a": {"b": 1}, "c": 2, "d": None}])
    ds.append({"a": {"b": 3}, "c": 4, "d": None})
    ref = weave.publish(ds)

    ds2 = ref.get()
    assert ds2 == [
        {"a": {"b": 1}, "c": 2, "d": None},
        {"a": {"b": 3}, "c": 4, "d": None},
    ]

    ds2.append({"a": {"b": 5}, "c": 6, "d": None})
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3 == [
        {"a": {"b": 1}, "c": 2, "d": None},
        {"a": {"b": 3}, "c": 4, "d": None},
        {"a": {"b": 5}, "c": 6, "d": None},
    ]


def test_dataset_pop(client):
    ds = weave.Dataset(
        rows=[
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
            {"a": 5, "b": 6},
        ]
    )
    ds.pop(0)
    ref = weave.publish(ds)

    ds2 = ref.get()
    assert ds2 == [
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]
    ds2.pop(0)
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3 == [{"a": 5, "b": 6}]


def test_dataset_assignment(client):
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}])
    ds.rows = [{"a": 3, "b": 4}]
    ref = weave.publish(ds)

    print(f"{ref=}")

    ds2 = ref.get()
    assert ds2 == [{"a": 3, "b": 4}]

    ds2.rows = [{"a": 5, "b": 6}]
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3 == [{"a": 5, "b": 6}]


def test_dataset_iadd(client):
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}])
    ds += [{"a": 3, "b": 4}]
    ref = weave.publish(ds)

    ds2 = ref.get()
    print(f"{ds2=}")
    print(f"{list(ds2.rows)=}")
    assert ds2 == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

    ds2 += [{"a": 5, "b": 6}]
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    print(f"{ds3=}")
    print(f"{list(ds3.rows)=}")
    assert ds3 == [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
