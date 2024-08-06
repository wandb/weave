import weave


def test_dataset_add():
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}])
    ds.add({"a": 3, "b": 4})
    assert ds.rows == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_dataset_remove():
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    ds.remove(0)
    assert ds.rows == [{"a": 3, "b": 4}]


def test_gotten_dataset_add(client):
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    ref = weave.publish(ds)

    ds2 = ref.get()
    ds2.add({"a": 5, "b": 6})
    assert ds2.rows == [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]


def test_gotten_dataset_remove(client):
    # TODO: sqlite server path is broken
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    ref = weave.publish(ds)

    ds2 = ref.get()
    ds2.remove(0)
    assert ds2.rows == [{"a": 3, "b": 4}]
