import weave


def test_dataset(client):
    d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.ref(ref.uri()).get()

    # This might seem redundant, but it is useful to ensure that the
    # dataset can be re-iterated over multiple times and equality is preserved.
    assert list(d2.rows) == list(d2.rows)
    assert list(d.rows) == list(d2.rows)
    assert list(d.rows) == list(d.rows)
