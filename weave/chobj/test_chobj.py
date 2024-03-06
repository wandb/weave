from typing import Any, Generator
import pytest
import uuid
import chobj
import dataclasses


@pytest.fixture
def server() -> Generator[chobj.ObjectServer, None, None]:
    server = chobj.ObjectServer()
    server.drop_tables()
    server.create_tables()
    yield server


@pytest.fixture
def client() -> Generator[chobj.ObjectClient, None, None]:
    yield chobj.ObjectClient()


def test_table_create(server):
    table_ref = server.new_table([1, 2, 3])
    assert list(server.table_query(table_ref)) == [1, 2, 3]
    assert list(server.table_query(table_ref, offset=1)) == [2, 3]
    assert list(server.table_query(table_ref, offset=1, limit=1)) == [2]
    # TODO: This doesn't work
    # assert list(server._table_query(table_ref, filter={"": 2})) == [2]


def test_table_append(server):
    table_ref = server.new_table([1, 2, 3])
    new_table_ref, item_id = server.table_append(table_ref, 4)
    assert list(server.table_query(new_table_ref)) == [1, 2, 3, 4]


def test_table_remove(server):
    table_ref0 = server.new_table([1])
    table_ref1, item_id2 = server.table_append(table_ref0, 2)
    table_ref2, item_id3 = server.table_append(table_ref1, 3)
    table_ref3 = server.table_remove(table_ref2, item_id2)
    assert list(server.table_query(table_ref3)) == [1, 3]


def new_val_single(server):
    obj_id = server.new_val(42)
    assert server.get(obj_id) == 42


def test_new_val_with_list(server):
    ref = server.new_val({"a": [1, 2, 3]})
    server_val = server.get_val(ref)
    table_ref = server_val["a"]
    assert isinstance(table_ref, chobj.TableRef)
    table_val = server.table_query(table_ref)
    assert list(table_val) == [1, 2, 3]


def test_object(server):
    obj_ref = server.new_object({"a": 43}, "my-obj", "latest")
    val_ref = server._resolve_object("my-obj", "latest")
    assert obj_ref.val_id == val_ref.val_id
    assert server._resolve_object("my-obj", "latest2") is None


def test_save_load(client):
    saved_val = client.save({"a": [1, 2, 3]}, "my-obj")
    val = client.get(saved_val.ref)
    val_table = list(val["a"])
    assert val_table[0] == 1
    assert val_table[1] == 2
    assert val_table[2] == 3


def test_dataset_refs(client):
    ref = client.save(chobj.Dataset([1, 2, 3]), "my-dataset")
    new_table_rows = []
    for row in ref.rows:
        new_table_rows.append({"a_ref": row, "b": row + 42})
    ref2 = client.save(new_table_rows, "my-dataset2")
    ref2_list = list(ref2)

    # if we access a_ref values, we actually get values, but we
    # can also get correct references.
    # TODO: shit this is wrong... those should be the underlying
    # refs I think?

    row0 = ref2_list[0]
    ref0_aref = row0["a_ref"]
    assert ref0_aref == 1
    assert chobj.get_ref(ref0_aref) == chobj.ObjectRef(
        "my-dataset2", ref2.ref.val_id, ["id", 0, "key", "a_ref"]
    )

    row1 = ref2_list[1]
    ref1_aref = row1["a_ref"]
    assert ref1_aref == 2
    assert chobj.get_ref(ref1_aref) == chobj.ObjectRef(
        "my-dataset2", ref2.ref.val_id, ["id", 1, "key", "a_ref"]
    )

    row2 = ref2_list[2]
    ref2_aref = row2["a_ref"]
    assert ref2_aref == 3
    assert chobj.get_ref(ref2_aref) == chobj.ObjectRef(
        "my-dataset2", ref2.ref.val_id, ["id", 2, "key", "a_ref"]
    )


def test_call_create(client, server):
    call = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call, "hello")
    result = client.call(call.id)
    assert result == chobj.Call("x", {"a": 5, "b": 10}, output="hello")


def test_calls_query(client, server):
    client.create_call("x", {"a": 5, "b": 10})
    client.create_call("x", {"a": 6, "b": 11})
    client.create_call("y", {"a": 5, "b": 10})
    result = list(client.calls({"op_name": "x"}))
    assert len(result) == 2
    assert result[0] == chobj.Call("x", {"a": 5, "b": 10})
    assert result[1] == chobj.Call("x", {"a": 6, "b": 11})


def test_dataset_calls(client, server):
    ref = client.save(
        chobj.Dataset([{"doc": "xx", "label": "c"}, {"doc": "yy", "label": "d"}]),
        "my-dataset",
    )
    for row in ref.rows:
        client.create_call("x", {"a": row["doc"]})

    calls = list(client.calls({"op_name": "x"}))
    assert calls[0].inputs["a"] == "xx"
    assert calls[1].inputs["a"] == "yy"


def test_encode():
    call = chobj.Call("x", {"a": chobj.ObjectRef("my-dataset", uuid.uuid4()), "b": 10})
    encoded = chobj.json_dumps(call)
    call2 = chobj.json_loads(encoded)
    assert call == call2


# def test_mutations(client):
#     dataset = client.save(
#         chobj.Dataset([{"doc": "xx", "label": "c"}, {"doc": "yy", "label": "d"}]),
#         "my-dataset",
#     )
#     dataset.rows.append({"doc": "zz", "label": "e"})


# def test_publish_big_list(server):
#     import time

#     t = time.time()
#     big_list = list({"x": i, "y": i} for i in range(1000000))
#     print("create", time.time() - t)
#     t = time.time()
#     ref = server.new({"a": big_list})
#     print("insert", time.time() - t)
#     t = time.time()
#     res = server.get(ref)
#     print("get", time.time() - t)
#     assert res == {"a": big_list}
