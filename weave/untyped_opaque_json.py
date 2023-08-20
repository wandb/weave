import json
import typing
from dataclasses import field
from collections import namedtuple


from .decorator_type import type as weave_type

IMMUTABLE_ERROR_MESSAGE = "This object is immutable."


class ImmutableBase:
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


def frozen(obj):
    if isinstance(obj, UntypedOpaqueJSON):
        return UntypedOpaqueJSON.from_json(frozen(obj.json))
    if isinstance(obj, dict):
        return ImmutableDict({key: frozen(value) for key, value in obj.items()})
    elif isinstance(obj, list):
        return ImmutableList(frozen(v) for v in obj)
    return obj


def unfrozen(data):
    if isinstance(data, UntypedOpaqueJSON):
        return unfrozen(data.json)
    if isinstance(data, dict):
        return {key: unfrozen(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [unfrozen(value) for value in data]
    else:
        return data


@weave_type("UntypedOpaqueJSON", True)
class UntypedOpaqueJSON:
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
    def from_json(cls, json_dict: typing.Any):
        json_str = json.dumps(json_dict)
        inst = cls(json_str=json_str)
        inst._json = frozen(json_dict)
        return inst

    @property
    def json(self):
        if not hasattr(self, "_json"):
            self._json = frozen(json.loads(self.json_str))
        return self._json

    def __getitem__(self, key):
        return self.json[key]

    def __setitem__(self, key, value):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def __delitem__(self, key):
        raise TypeError(IMMUTABLE_ERROR_MESSAGE)

    def get(self, key, default=None):
        return self.json.get(key, default)

    def __eq__(self, other):
        if isinstance(other, UntypedOpaqueJSON):
            return self.json == other.json
        return self.json == other

    def __iter__(self):
        return iter(self.json)

    def __len__(self):
        return len(self.json)

    def __repr__(self):
        return "UntypedOpaqueJSON(" + self.json_str + ")"

    def items(self):
        return self.json.items()


UntypedOpaqueJSONType = UntypedOpaqueJSON.WeaveType  # type: ignore
