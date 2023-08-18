from typing import Optional, Any, Iterator
import json
from dataclasses import field
from .decorator_type import type as weave_type


@weave_type("UntypedOpaqueDict", True)
class UntypedOpaqueDict:
    """
    UntypedOpaqueDict is a Weave Type that is used to store arbitrary JSON data.
    Unlike `Dict` or `TypedDict`, this Type does not need to define the keys/fields.
    This is useful in particular for storing GQL responses where the response schema
    may change over time. Usage:

    # From JSON String
    d = UntypedOpaqueDict(json_str='{"a": 1, "b": 2}')
    d["a"]  # 1

    # From Dictionary
    d = UntypedOpaqueDict.from_dict({"a": 1, "b": 2})
    d["a"]  # 1

    Importantly, this will serialize the data as a JSON string, so it can be stored and
    loaded using the Weave Type system.
    """

    json_str: str = field(default="{}")

    @classmethod
    def from_json_dict(cls, json_dict: dict) -> "UntypedOpaqueDict":
        inst = cls(json_str=json.dumps(json_dict, separators=(",", ":")))
        inst._json_dict = json_dict
        return inst

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.json_dict.get(key, default)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, UntypedOpaqueDict):
            return False
        return self.json_dict == other.json_dict

    def __getitem__(self, key: str) -> Any:
        return self.json_dict[key]

    def __setitem__(self, key: str, value: Any) -> None:
        raise NotImplementedError("UntypedOpaqueDict is immutable")

    def __delitem__(self, key: str) -> None:
        raise NotImplementedError("UntypedOpaqueDict is immutable")

    def __iter__(self) -> Iterator[Any]:
        return iter(self.json_dict)

    def __len__(self) -> int:
        return len(self.json_dict)

    @property
    def json_dict(self) -> dict:
        if not hasattr(self, "_json_dict"):
            self._json_dict = json.loads(self.json_str)
        return self._json_dict
