import gc

import pytest

from weave.trace.custom_weave_type_serialization_cache import (
    CustomWeaveTypeSerializationCache,
)


class CustomWeaveType:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, CustomWeaveType) and self.value == other.value


@pytest.fixture
def cache():
    return CustomWeaveTypeSerializationCache()


def test_store_and_retrieve(cache):
    obj = CustomWeaveType(1)
    serialized_dict = {"value": 1}
    cache.store(obj, serialized_dict)

    assert cache.get_serialized_dict(obj) == serialized_dict
    assert cache.get_deserialized_obj(serialized_dict) == obj


def test_store_multiple_objects(cache):
    obj1 = CustomWeaveType(1)
    obj2 = CustomWeaveType(2)
    serialized_dict1 = {"value": 1}
    serialized_dict2 = {"value": 2}

    cache.store(obj1, serialized_dict1)
    cache.store(obj2, serialized_dict2)

    assert cache.get_serialized_dict(obj1) == serialized_dict1
    assert cache.get_serialized_dict(obj2) == serialized_dict2
    assert cache.get_deserialized_obj(serialized_dict1) == obj1
    assert cache.get_deserialized_obj(serialized_dict2) == obj2


def test_reset(cache):
    obj = CustomWeaveType(1)
    serialized_dict = {"value": 1}
    cache.store(obj, serialized_dict)

    cache.reset()

    assert cache.get_serialized_dict(obj) is None
    assert cache.get_deserialized_obj(serialized_dict) is None


def test_weak_reference_behavior(cache):
    obj = CustomWeaveType(1)
    serialized_dict = {"value": 1}
    cache.store(obj, serialized_dict)

    del obj
    gc.collect()

    assert cache.get_deserialized_obj(serialized_dict) is None


def test_non_existent_object(cache):
    obj = CustomWeaveType(1)
    serialized_dict = {"value": 1}

    assert cache.get_serialized_dict(obj) is None
    assert cache.get_deserialized_obj(serialized_dict) is None


def test_update_existing_object(cache):
    obj = CustomWeaveType(1)
    serialized_dict1 = {"value": 1}
    serialized_dict2 = {"value": "one"}

    cache.store(obj, serialized_dict1)
    cache.store(obj, serialized_dict2)

    assert cache.get_serialized_dict(obj) == serialized_dict2
    assert cache.get_deserialized_obj(serialized_dict2) == obj
    assert cache.get_deserialized_obj(serialized_dict1) is None


def test_unhashable_object(cache):
    class UnhashableObject:
        def __hash__(self):
            raise TypeError("unhashable type")

    obj = UnhashableObject()
    serialized_dict = {"type": "unhashable"}

    cache.store(obj, serialized_dict)

    assert cache.get_serialized_dict(obj) == serialized_dict
    assert cache.get_deserialized_obj(serialized_dict) == obj


def test_exception_handling(cache):
    obj = CustomWeaveType(1)
    bad_dict = {"key": object()}  # object() is not JSON serializable

    # This should not raise an exception
    cache.store(obj, bad_dict)

    assert cache.get_serialized_dict(obj) == bad_dict

    # We are unable lookup unserializable objects
    assert cache.get_deserialized_obj(bad_dict) is None


def test_multiple_objects_same_serialization(cache):
    obj1 = CustomWeaveType(1)
    obj2 = CustomWeaveType(1)
    serialized_dict = {"value": 1}

    cache.store(obj1, serialized_dict)
    cache.store(obj2, serialized_dict)

    assert cache.get_serialized_dict(obj1) == serialized_dict
    assert cache.get_serialized_dict(obj2) == serialized_dict
    # The last stored object should be returned
    assert cache.get_deserialized_obj(serialized_dict) == obj2
