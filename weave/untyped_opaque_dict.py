from typing import Optional, Any, Iterator
import json
from dataclasses import field
from .decorator_class import weave_class
from . import weave_types as types


class DictSavedAsStringType(types.BasicType):
    def save_instance(self, obj, artifact, name):
        obj = json.dumps(obj.json_dict, separators=(",", ":"))
        return super().save_instance(obj, artifact, name)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            return json.load(json.load(f))


@weave_class(weave_type=DictSavedAsStringType)
class DictSavedAsString:
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

    json_dict: dict = field(default_factory=lambda: {})

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.json_dict.get(key, default)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DictSavedAsString):
            return False
        return self.json_dict == other.json_dict

    def __getitem__(self, key: str) -> Any:
        return self.json_dict[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.json_dict[key] = value

    def __delitem__(self, key: str) -> None:
        del self.json_dict[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.json_dict)

    def __len__(self) -> int:
        return len(self.json_dict)
