import typing

from . import uris
from . import errors

from . import ref_base
from . import weave_types as types

MEM_OBJS: typing.Dict[str, typing.Any] = {}


class MemRef(ref_base.Ref):
    _name: str

    def __init__(
        self,
        name: str,
        obj: typing.Optional[typing.Any] = None,
        type: typing.Optional["types.Type"] = None,
    ):
        super().__init__(obj=obj, type=type)
        self._name = name

    @classmethod
    def from_uri(cls, uri: "WeaveRuntimeURI") -> "MemRef":
        return cls(uri.full_name)

    @property
    def type(self) -> "types.Type":
        if self._type is not None:
            return self._type
        self._type = types.TypeRegistry.type_of(self.obj)
        return self._type

    @property
    def name(self) -> str:
        return self._name

    def _get(self) -> typing.Any:
        if self._name not in MEM_OBJS:
            name = self._name  # pick name off of self for sentry logging
            raise errors.WeaveStorageError(f"Object {name} not found")
        return MEM_OBJS[self.name]

    def __str__(self) -> str:
        return self.name


def save_mem(obj: typing.Any, name: str) -> MemRef:
    MEM_OBJS[name] = obj
    return MemRef(name)


# Used when the Weave object is constructed at runtime (eg. weave-builtins or user-defined objects)
class WeaveRuntimeURI(uris.WeaveURI):
    scheme = ""

    def __init__(self, uri: str):
        super().__init__(uri)
        parts = self.path.split(":", 1)
        self._full_name = parts[0]
        if len(parts) == 2:
            self._version = parts[1]
        else:
            self._version = None

    def to_ref(self) -> MemRef:
        return MemRef.from_uri(self)

    def __repr__(self) -> str:
        return f"<RuntimeURI({self.uri})>"
