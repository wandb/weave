import typing

from . import weave_types as types
from .decorator_class import weave_class
from . import errors


class UntypedOpaqueDictType(types.BasicType):
    name = "untyped_opaque_dict"


@weave_class(UntypedOpaqueDictType)
class UntypedOpaqueDict(dict):
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

    def __repr__(self) -> str:
        return f"UntypedOpaqueDict({dict(self)})"

    def __str__(self) -> str:
        return self.__repr__()

    def __setitem__(self, key: str, value: typing.Any) -> None:
        raise errors.WeaveTypeError(
            "UntypedOpaqueDict is immutable and does not support setting items."
        )

    def __delitem__(self, key: str) -> None:
        raise errors.WeaveTypeError(
            "UntypedOpaqueDict is immutable and does not support setting items."
        )

    def update(self, *args, **kwargs) -> None:
        raise errors.WeaveTypeError(
            "UntypedOpaqueDict is immutable and does not support setting items."
        )
