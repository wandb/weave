import copy
from collections import OrderedDict
from typing import Any, Dict


def get_nested_key(d: Dict[str, Any], col: str) -> Any:
    """
    Get a nested key from a dict.

    Example:
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b.c") -> "d"
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b.c.e") -> None
    """

    def _get(dictionary: Dict[str, Any], key: str) -> Any:
        if isinstance(dictionary, dict):
            return dictionary.get(key, {})
        return None

    keys = col.split(".")
    curr = d
    for key in keys[:-1]:
        curr = _get(curr, key)
    return _get(curr, keys[-1])


def set_nested_key(d: Dict[str, Any], col: str, val: Any) -> None:
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
    def __init__(self, max_size: int = 1000, *args: Any, **kwargs: Dict[str, Any]):
        self.max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        if len(self) >= self.max_size:
            self.popitem(last=False)
        super().__setitem__(key, value)
