import gc

import pytest

from weave.trace.data_structures.weak_unhashable_key_dictionary import (
    WeakKeyDictionarySupportingNonHashableKeys,
)


class UnhashableObject:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, UnhashableObject) and self.value == other.value

    def __hash__(self):
        raise NotImplementedError("Unhashable object")


@pytest.fixture
def weak_dict():
    return WeakKeyDictionarySupportingNonHashableKeys()


def test_set_and_get(weak_dict):
    key = UnhashableObject(1)
    weak_dict[key] = "value"
    assert weak_dict[key] == "value"


def test_delete_item(weak_dict):
    key = UnhashableObject(1)
    weak_dict[key] = "value"
    del weak_dict[key]
    assert key not in weak_dict


def test_len(weak_dict):
    objs = [UnhashableObject(i) for i in range(3)]
    for obj in objs:
        weak_dict[obj] = f"value{obj.value}"
    assert len(weak_dict) == 3
    del obj
    del objs
    gc.collect()
    assert len(weak_dict) == 0


def test_iter(weak_dict):
    keys = [UnhashableObject(i) for i in range(3)]
    for key in keys:
        weak_dict[key] = f"value{key.value}"
    assert set(key.value for key in weak_dict) == set(range(3))
    del key
    del keys
    gc.collect()
    assert len(weak_dict) == 0


def test_keys(weak_dict):
    keys = [UnhashableObject(i) for i in range(3)]
    for key in keys:
        weak_dict[key] = f"value{key.value}"
    assert set(key.value for key in weak_dict.keys()) == set(range(3))
    del key
    del keys
    gc.collect()
    assert len(list(weak_dict.keys())) == 0


def test_values(weak_dict):
    objs = [UnhashableObject(i) for i in range(3)]
    for obj in objs:
        weak_dict[obj] = f"value{obj.value}"
    assert set(weak_dict.values()) == set(f"value{i}" for i in range(3))
    del obj
    del objs
    gc.collect()
    assert len(weak_dict.values()) == 0


def test_items(weak_dict):
    objs = [UnhashableObject(i) for i in range(3)]
    for obj in objs:
        weak_dict[obj] = f"value{obj.value}"
    items = list(weak_dict.items())
    assert len(items) == 3
    assert all(isinstance(k, UnhashableObject) and isinstance(v, str) for k, v in items)
    assert set((k.value, v) for k, v in items) == set(
        (i, f"value{i}") for i in range(3)
    )
    del obj
    del objs
    gc.collect()
    assert len(list(weak_dict.items())) == 3
    del items
    gc.collect()
    assert len(list(weak_dict.items())) == 0


def test_weak_reference_behavior():
    weak_dict = WeakKeyDictionarySupportingNonHashableKeys()
    key = UnhashableObject(1)
    weak_dict[key] = "value"

    assert len(weak_dict) == 1
    del key
    # Force garbage collection
    gc.collect()
    assert len(weak_dict) == 0


def test_get_method(weak_dict):
    key = UnhashableObject(1)
    assert weak_dict.get(key) is None
    assert weak_dict.get(key, "default") == "default"
    weak_dict[key] = "value"
    assert weak_dict.get(key) == "value"
    assert weak_dict.get(key, "default") == "value"
    del key
    gc.collect()
    assert len(weak_dict) == 0


def test_clear_method(weak_dict):
    objs = [UnhashableObject(i) for i in range(3)]
    for obj in objs:
        weak_dict[obj] = f"value{obj.value}"
    assert len(weak_dict) == 3
    weak_dict.clear()
    assert len(weak_dict) == 0
    del objs
    gc.collect()
    assert len(weak_dict) == 0


def test_multiple_values_same_id():
    weak_dict = WeakKeyDictionarySupportingNonHashableKeys()
    key1 = UnhashableObject(1)
    key2 = UnhashableObject(1)
    weak_dict[key1] = "value1"
    weak_dict[key2] = "value2"
    assert weak_dict[key1] == "value1"
    assert weak_dict[key2] == "value2"
    assert len(weak_dict) == 2
    del key1
    gc.collect()
    assert len(weak_dict) == 1
    assert weak_dict[key2] == "value2"
    del key2
    gc.collect()
    assert len(weak_dict) == 0


def test_unhashable_key_error_handling():
    weak_dict = WeakKeyDictionarySupportingNonHashableKeys()
    key = UnhashableObject(1)
    weak_dict[key] = "value"

    with pytest.raises(KeyError):
        _ = weak_dict[UnhashableObject(2)]

    with pytest.raises(KeyError):
        del weak_dict[UnhashableObject(2)]
