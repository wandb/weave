import typing
import weakref

from . import uris
from . import box
from . import errors

# We store Refs here if we can't attach them directly to the object
REFS: weakref.WeakValueDictionary[int, "Ref"] = weakref.WeakValueDictionary()

if typing.TYPE_CHECKING:
    from . import weave_types as types


class Ref:
    _obj: typing.Any
    _type: typing.Optional["types.Type"]
    extra: typing.Optional[list[str]]

    def __init__(
        self,
        obj: typing.Optional[typing.Any] = None,
        type: typing.Optional["types.Type"] = None,
        extra: typing.Optional[list[str]] = None,
    ):
        self._obj = obj
        if obj is not None:
            obj = box.box(obj)
            put_ref(obj, self)
        self._type = type
        self.extra = extra

    @property
    def obj(self) -> typing.Any:
        if self._obj is not None:
            return self._obj
        obj = self._get()
        obj = box.box(obj)
        put_ref(obj, self)
        self._obj = obj
        return obj

    @property
    def type(self) -> "types.Type":
        raise NotImplemented

    @classmethod
    def from_str(cls, s: str) -> "Ref":
        return uris.WeaveURI.parse(s).to_ref()

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def uri(self) -> str:
        raise NotImplementedError()

    def get(self) -> typing.Any:
        return self.obj

    def _get(self) -> typing.Any:
        raise NotImplementedError

    def __str__(self) -> str:
        return self.uri


def get_ref(obj: typing.Any) -> typing.Optional[Ref]:
    if isinstance(obj, Ref):
        return obj
    if hasattr(obj, "_ref"):
        return obj._ref
    try:
        if id(obj) in REFS:
            return REFS[id(obj)]
    except TypeError:
        pass
    return None


def put_ref(obj: typing.Any, ref: Ref) -> None:
    try:
        obj._ref = ref
    except AttributeError:
        if isinstance(obj, (int, float, str, list, dict, set)):
            return
        REFS[id(obj)] = ref


def clear_ref(obj: typing.Any) -> None:
    try:
        delattr(obj, "_ref")
    except AttributeError:
        pass
    if id(obj) in REFS:
        REFS.pop(id(obj))


def deref(ref: Ref) -> typing.Any:
    if isinstance(ref, Ref):
        return ref.get()
    return ref
