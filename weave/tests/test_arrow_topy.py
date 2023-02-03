from ..ops_arrow import list_


def test_topy2_int():
    v = [1, 2, 3]
    a = list_.to_arrow(v)
    assert a.to_pylist_tagged() == v


def test_topy2_typedict():
    v = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    a = list_.to_arrow(v)
    assert a.to_pylist_tagged() == v


def test_topy2_typedict_dictionary():
    v = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    a = list_.to_arrow(v)
    a2 = a.replace_column("a", lambda v: v.dictionary_encode())
    assert a2.to_pylist_tagged() == v


def test_topy2_typedict_list():
    v = [{"a": 1, "b": [8, 9, 10]}, {"a": 3, "b": [4, 5, 6]}]
    a = list_.to_arrow(v)
    assert a.to_pylist_tagged() == v


def test_topy2_typedict_list_struct():
    v = [{"a": 1, "b": [{"c": 5}, {"c": 7}]}, {"a": 3, "b": [{"c": -2}, {"c": 4}]}]
    a = list_.to_arrow(v)
    assert a.to_pylist_tagged() == v


def test_topy2_typedict_list_struct_dictionary():
    v = [{"a": 1, "b": [{"c": 5}, {"c": -2}]}, {"a": 3, "b": [{"c": -2}, {"c": 4}]}]
    a = list_.to_arrow(v)
    a2 = a.replace_column(
        ("b", list_.SpecialPathItem.PATH_LIST_ITEMS, "c"),
        lambda v: v.dictionary_encode(),
    )
    assert a2.to_pylist_tagged() == v


# TODO: test tags, unions
