import functools
import hashlib
import json
import typing
import weakref
from typing import Iterable, Optional, Sequence

from weave import client_context
from weave.legacy import box, context_state, object_context
from weave.legacy.language_features.tagging import tag_store

from . import errors
from . import weave_types as types
from .legacy import uris

# We store Refs here if we can't attach them directly to the object
REFS: weakref.WeakValueDictionary[int, "Ref"] = weakref.WeakValueDictionary()

if typing.TYPE_CHECKING:
    from weave.legacy import run

    from . import weave_client
    from . import weave_types as types


def _map_to_ref_strs(obj: typing.Any) -> typing.Any:
    if isinstance(obj, dict):
        return {k: _map_to_ref_strs(v) for k, v in obj.items()}  # type: ignore
    if isinstance(obj, list):
        return [_map_to_ref_strs(v) for v in obj]  # type: ignore
    ref = get_ref(obj)
    if ref is not None:
        return str(ref)
    return obj


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
        self._type = type
        self.extra = extra
        if obj is not None and type is not None and type.name != "tagged":  # type: ignore
            obj = box.box(obj)
            _put_ref(obj, self)
        self._obj = obj

    @property
    def obj(self) -> typing.Any:
        obj_ctx = object_context.get_object_context()
        if obj_ctx:
            val = obj_ctx.lookup_ref_val(str(self.initial_uri))
            if not isinstance(val, object_context.NoResult):
                return val

        if self._obj is not None:
            return self._obj

        if not self.is_saved:
            # PR TODO: this path needs to happen in FSArtifact, as you can
            # always get the value of a MemArtifact
            # PR: I changed this back to None to get tests passing. What breaks
            # now? My guess is mutations from the UI? Or maybe creating brand
            # new objects from the UI (datasets)
            return None
            raise errors.WeaveArtifactVersionNotFound

        if self.extra is None:
            obj = self._get()
            obj = box.box(obj)
        else:
            ref_without_extra = self.without_extra(None)
            outer_obj = ref_without_extra.get()
            try:
                with context_state.ref_tracking(True):
                    obj = outer_obj._lookup_path(self.extra)  # type: ignore
            except AttributeError:
                raise errors.WeaveInternalError(
                    f"Ref has extra {self.extra} but object of type {type(outer_obj)} does not support _lookup_path"
                )

        # Don't put a ref if the object is tagged, it leads to failures in a couple
        # of the test_arrow.py tests. I don't have the exact rationale, but it's something
        # like we end up later loading the tagged object when we want the untagged one,
        # of vice versa.
        # this check was if self.type.name != 'tagged', however
        # accesing self.type here is problematic, can cause a loop (as it does with tableref).
        # Since we just loaded this object, it will be tagged if it was stored tagged,
        # which I believe is the check we want.
        if not tag_store.is_tagged(obj):
            _put_ref(obj, self)
        self._obj = obj

        if obj_ctx is not None:
            obj_ctx.add_ref(str(self.initial_uri), obj, self.type)

        return obj

    @property
    def ui_url(self) -> str:
        return "[no url for obj]"

    @property
    def type(self) -> "types.Type":
        raise NotImplementedError

    @functools.cached_property
    def digest(self) -> str:
        hash = hashlib.md5()
        # This can encounter non-serialized objects, even though Ref
        # must be a pointer to an object that can only contain serializable
        # stuff and refs. But we recursively deserialize all sub-refs when
        # fetching a ref. So we need to walk obj, converting objs back to
        # refs where we can, before this json.dumps call.
        # TODO: fix
        with_refs = _map_to_ref_strs(self.obj)
        hash.update(json.dumps(with_refs).encode())
        return hash.hexdigest()

    @classmethod
    def from_str(cls, s: str) -> "Ref":
        return uris.WeaveURI.parse(s).to_ref()

    @property
    def initial_uri(self) -> str:
        raise NotImplementedError

    @property
    def uri(self) -> str:
        raise NotImplementedError

    @property
    def is_saved(self) -> bool:
        raise NotImplementedError

    def get(self) -> typing.Any:
        return self.obj

    def _get(self) -> typing.Any:
        raise NotImplementedError

    def without_extra(self, new_type: typing.Optional[types.Type]) -> "Ref":
        raise NotImplementedError

    def with_extra(
        self, new_type: typing.Optional[types.Type], obj: typing.Any, extra: list[str]
    ) -> "Ref":
        raise NotImplementedError

    def __str__(self) -> str:
        return str(self.uri)

    def input_to(self) -> Sequence["weave_client.Call"]:
        client = client_context.weave_client.require_weave_client()
        return client._ref_input_to(self)

    def value_input_to(self) -> Sequence["weave_client.Call"]:
        client = client_context.weave_client.require_weave_client()
        return client._ref_value_input_to(self)


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


# TODO: this cannot be used on tagged objects, since we don't know
# whether obj is intended to be the tagged or untagged version
# So for now we never call it on tagged objects. But this probably
# breaks some behaviors (like automatic cross-artifact references
# for tagged objects)
def _put_ref(obj: typing.Any, ref: Ref) -> None:
    try:
        obj._ref = ref
    except (AttributeError, ValueError):
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


def deref(ref: typing.Any) -> typing.Any:
    if isinstance(ref, Ref):
        return ref.get()
    return ref


types.RefType.instance_classes = Ref
