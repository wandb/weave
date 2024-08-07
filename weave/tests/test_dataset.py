import weave


def test_dataset_append(client):
    ds = weave.Dataset(rows=[{"a": 1, "b": 2}])
    print("Before append")
    # ds.append({"a": 3, "b": 4})
    ds.rows.append({"a": 3, "b": 4})
    print("Before publish 1")
    ref = weave.publish(ds)
    print("After publish 1")

    ds2 = ref.get()
    assert ds2.rows == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
    ]
    # ds2.append({"a": 5, "b": 6})
    print("****************************************")
    print("****************************************")
    print(f"{ds2=}")
    print(f"{ds2.ref=}")
    print(f"{ds2.parent=}")
    print(f"{ds2.rows=}")
    print(f"{ds2.rows.table_ref=}")
    print(f"{ds2.rows.ref=}")
    print(f"{ds2.rows.parent=}")
    print(f"{ds2.rows.rows=}")
    print("****************************************")
    print("****************************************")
    ds2.rows.append({"a": 5, "b": 6})
    print(f"{ds2=}")
    print(f"{ds2.ref=}")  # This should be zero'd with append, but it's not
    print(f"{ds2.parent=}")
    assert ds2.ref is None
    assert ds2.rows.ref is None
    assert ds2.rows.table_ref is None
    print(f"{ds2.rows=}")
    print(f"{ds2.rows.table_ref=}")
    print(f"{ds2.rows.ref=}")
    print(f"{ds2.rows.parent=}")
    print(f"{ds2.rows.rows=}")
    print("****************************************")
    print("****************************************")

    print("Before publish 2")
    ref2 = weave.publish(ds2)
    print("After publish 2")

    ds3 = ref2.get()
    print("****************************************")
    print("****************************************")
    print(f"{ds3=}")
    print(f"{ds3.rows=}")
    print(f"{ds3.rows.rows=}")
    print("****************************************")
    print("****************************************")
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
