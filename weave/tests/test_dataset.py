import weave

# TODO: This is not ideal because the user must reach into Dataset and
# operate on `rows`, which is an implementation detail.

# Ideally, the user can do `Dataset.append` and it will dispatch to
# rows transparently, but this is incompatible with ref-get-Datasets because:
# 1. If `Dataset.append` is not an Op, then it won't be available on the
#    ref-get-Dataset; and
# 2. If `Dataset.append` is an Op, each append will be traced (noisy), and
#    it also breaks our rule that Ops should be pure.


# I think the ideal state is for `append` to track, but only at the end
# when the object is published -- if you call `Dataset.append` 3 times,
# only 1 call is traced which contains the 3 appends.  This pattern is
# similar to "add" vs. "commit" in git.  This is also the pattern we'll
# want for server-side mutations, so we should revisit this when we add that.


def test_dataset_append(client):
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}])
    ds.rows.append({"a": 3, "b": 4})
    ref = weave.publish(ds)

    ds2 = ref.get()
    assert ds2.rows == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
    ]
    ds2.rows.append({"a": 5, "b": 6})
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3.rows == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]


def test_dataset_pop(client):
    ds = weave.Dataset(
        rows=[
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
            {"a": 5, "b": 6},
        ]
    )
    ds.rows.pop(0)
    ref = weave.publish(ds)

    ds2 = ref.get()
    assert ds2.rows == [
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]
    ds2.rows.pop(0)
    ref2 = weave.publish(ds2)

    ds3 = ref2.get()
    assert ds3.rows == [{"a": 5, "b": 6}]
