import pytest
import chobj


@pytest.fixture
def client():
    client = chobj.CHClient()
    client.drop_tables()
    client.create_tables()
    yield client


def test_table_create(client):
    table_ref = client.new_table([1, 2, 3])
    assert list(client.get_table(table_ref)) == [1, 2, 3]


def test_table_append(client):
    table_ref = client.new_table([1, 2, 3])
    new_table_ref, item_id = client.table_append(table_ref, 4)
    assert list(client.get_table(new_table_ref)) == [1, 2, 3, 4]


def test_table_remove(client):
    table_ref0 = client.new_table([1])
    table_ref1, item_id2 = client.table_append(table_ref0, 2)
    table_ref2, item_id3 = client.table_append(table_ref1, 3)
    table_ref3 = client.table_remove(table_ref2, item_id2)
    assert list(client.get_table(table_ref3)) == [1, 3]


def test_publish(client):
    obj_id = client.new_val(42)
    assert client.get(obj_id) == 42


def test_publish_with_list(client):
    ref = client.new_val({"a": [1, 2, 3]})
    assert client.get(ref) == {"a": [1, 2, 3]}


def test_nested_list_append(client):
    ref = client.new_val({"a": [1, 2, 3]})
    ref = ref.with_path("a")
    ref = client.table_append(ref, [5, 6, 7])


# def test_publish_big_list(client):
#     import time

#     t = time.time()
#     big_list = list({"x": i, "y": i} for i in range(1000000))
#     print("create", time.time() - t)
#     t = time.time()
#     ref = client.new({"a": big_list})
#     print("insert", time.time() - t)
#     t = time.time()
#     res = client.get(ref)
#     print("get", time.time() - t)
#     assert res == {"a": big_list}
