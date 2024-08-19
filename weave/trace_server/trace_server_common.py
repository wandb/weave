import copy
import typing
from collections import OrderedDict


def get_nested_key(d: dict[str, typing.Any], col: str) -> typing.Any:
    """
    Get a nested key from a dict.

    Example:
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b.c") -> "d"
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b.c.e") -> None
    """
    keys = col.split(".")
    curr = d
    for key in keys[:-1]:
        curr = curr.get(key, {})
    return curr.get(keys[-1], None)


def set_nested_key(d: dict[str, typing.Any], col: str, val: typing.Any) -> None:
    """
    Set a nested key in a dict.

    Example:
    set_nested_key({"a": {"b": "c"}}, "a.b", "e") -> {"a": {"b": "e"}}
    """
    keys = col.split(".")
    curr = d
    for key in keys[:-1]:
        curr = curr.setdefault(key, {})
    curr[keys[-1]] = copy.deepcopy(val)


class LRUCache(OrderedDict):
    def __init__(self, maxsize=1000, *args, **kwargs):
        self.maxsize = maxsize
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if len(self) >= self.maxsize:
            self.popitem(last=False)
        super().__setitem__(key, value)
