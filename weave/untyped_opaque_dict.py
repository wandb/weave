import json
from dataclasses import field

from .decorator_type import type as weave_type


IMMUTABLE_ERROR_MESSAGE = "This object is immutable"


def freeze(data):
    if isinstance(data, UntypedOpaqueDict):
        return UntypedOpaqueDict.from_json_dict(
            {key: freeze(value) for key, value in data.items()}
        )
    if isinstance(data, dict):
        return ImmutableDict({key: freeze(value) for key, value in data.items()})
    elif isinstance(data, list):
        return ImmutableList([freeze(value) for value in data])
    else:
        return data


def unfreeze(data):
    if isinstance(data, (dict, UntypedOpaqueDict)):  # also covers ImmutableDict
        return {key: unfreeze(value) for key, value in data.items()}
    elif isinstance(data, list):  # also covers ImmutableList
        return [unfreeze(value) for value in data]
    else:
        return data


class ImmutableBase:
    def mutable_copy(self):
        return unfreeze(self)

    def __setitem__(self, key, value):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def __delitem__(self, key):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def clear(self):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)


class ImmutableDict(dict, ImmutableBase):
    def update(self, *args, **kwargs):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def popitem(self, *args, **kwargs):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def setdefault(self, *args, **kwargs):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def pop(self, *args):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def __repr__(self):
        return "ImmutableDict(" + super().__repr__() + ")"


class ImmutableList(list, ImmutableBase):
    def append(self, value):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def extend(self, values):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def insert(self, index, value):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def remove(self, value):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def sort(self, *args, **kwargs):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def reverse(self):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def pop(self, *args):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def __repr__(self):
        return "ImmutableList(" + super().__repr__() + ")"


@weave_type("UntypedOpaqueDict", True)
class UntypedOpaqueDict(ImmutableBase):
    """
    UntypedOpaqueDict is a Weave Type that is used to store arbitrary JSON data.
    Unlike `Dict` or `TypedDict`, this Type does not need to define the keys/fields.
    This is useful in particular for storing GQL responses where the response schema
    may change over time. Usage:

    # From JSON String
    d = UntypedOpaqueDict(json_str='{"a": 1, "b": 2}')
    d["a"]  # 1

    # From Dictionary
    d = UntypedOpaqueDict.from_json_dict({"a": 1, "b": 2})
    d["a"]  # 1

    Importantly, this will serialize the data as a JSON string, so it can be stored and
    loaded using the Weave Type system.
    """

    json_str: str = field(default="{}")

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        inst = cls(json_str=json.dumps(json_dict, separators=(",", ":")))
        inst._json_dict = freeze(json_dict)
        return inst

    def get(self, key, default=None):
        return self.json_dict.get(key, default)

    def __eq__(self, other):
        return self.json_dict == other.json_dict

    def __getitem__(self, key):
        return self.json_dict[key]

    def __iter__(self):
        return iter(self.json_dict)

    def __len__(self):
        return len(self.json_dict)

    def items(self):
        return self.json_dict.items()

    @property
    def json_dict(self):
        if not hasattr(self, "_json_dict"):
            self._json_dict = freeze(json.loads(self.json_str))
        return self._json_dict


UntypedOpaqueDictType = UntypedOpaqueDict.WeaveType  # type: ignore
