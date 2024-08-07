import weave


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


# def test_dataset_pop(client):
#     ds = weave.Dataset(
#         rows=[
#             {"a": 1, "b": 2},
#             {"a": 3, "b": 4},
#             {"a": 5, "b": 6},
#         ]
#     )
#     ds.pop(0)
#     ref = weave.publish(ds)

#     ds2 = ref.get()
#     assert ds2.rows == [
#         {"a": 3, "b": 4},
#         {"a": 5, "b": 6},
#     ]
#     ds2.pop(0)
#     ref2 = weave.publish(ds2)

#     ds3 = ref2.get()
#     assert ds3.rows == [{"a": 5, "b": 6}]
