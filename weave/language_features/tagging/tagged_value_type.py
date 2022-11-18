"""
This file contains the Weave Types and Mappers needed to handle tagged values.

Here we will briefly describe how TaggedValues work. Firstly, note that we need
to be able to associate any object in the python runtime with a set of tags. Due
the the way Python works, the best way to implement this is to use a memory
mapping from the python id of an object to a dictionary of tags. This is
implemented in tag_store.py. Unlike other Weave Types, we cannot determine if an
object is tagged simply by looking at it's python type, so the TaggedValueType
has custom logic to determine if an object is a TaggedValue as well as special
assignability rules. Furthermore when serializing the TaggedValue to disk, we
need to serialize the tags as well - this is handled between the type class and
the mappers below. 

The net result of this system is that op resolvers can operate entirely agnostic
to tags - there is no mutation of the underlying python object whatsoever.
However, the op resolver can still access the tags by using the `find_tag`
function in tag_store.py. This is used by tag getters. Ops can add tags by using
the `add_tags` function in tag_store.py. This is used by tag setters (like
list-tagCheckpoint). Ops that are core language ops will need to operate on tags
directly (for example, list-concat). And ops that are weavifiable will get all
internal tag handling for free (although, this is not yet implemented).
Currently, the degenerate case is that a custom op either copies the object
(creating a new memory address) or is not weavifiable, in which we will simply
drop tags.
"""

import json
import typing

from ... import artifacts_local
from ... import box
from ... import weave_types as types
from ... import mappers_python
from ... import errors
from ... import refs
from ... import mappers

from . import tag_store

# A custom Weave Type used to represent tagged values.
class TaggedValueType(types.Type):
    name = "tagged"
    tag: types.TypedDict = types.TypedDict({})
    value: types.Type = types.Any()

    def __init__(
        self,
        tag: types.TypedDict = types.TypedDict({}),
        value: types.Type = types.Any(),
    ):
        assert types.TypedDict({}).assign_type(tag), (
            "Tags must be assignable to TypedDict, found %s" % tag
        )
        # We flatten tags in Weave1
        if isinstance(value, TaggedValueType):
            tag = types.TypedDict({**tag.property_types, **value.tag.property_types})
        self.tag = tag
        self.value = value

    def __getattr__(self, attr: str) -> typing.Any:
        return getattr(self.value, attr)

    @classmethod
    def is_instance(cls, obj: typing.Any) -> bool:
        return box.is_boxed(obj) and tag_store.is_tagged(obj)

    @classmethod
    def type_of_instance(cls, obj: typing.Any) -> "TaggedValueType":
        obj = box.box(obj)
        tags = tag_store.get_tags(obj)
        with tag_store.with_visited_obj(obj):
            tag_type = types.TypeRegistry.type_of(tags)
            assert isinstance(tag_type, types.TypedDict), (
                "Tags must be a dictionary, found %s" % tag_type
            )
            value_type = types.TypeRegistry.type_of(obj)
        res = cls(
            tag_type,
            value_type,
        )
        return res

    @classmethod
    def from_dict(cls, d: dict) -> "TaggedValueType":
        tag_type = types.TypeRegistry.type_from_dict(d["tag"])
        if isinstance(tag_type, TaggedValueType):
            # here, we are coming from JS
            assert types.TypedDict({}).assign_type(tag_type.tag), (
                "tag_type.tag must be assignable to TypedDict, found %s" % tag_type.tag
            )
            assert types.TypedDict({}).assign_type(tag_type.value), (
                "tag_type.value must be assignable to TypedDict, found %s"
                % tag_type.value
            )
            tag_type = types.TypedDict(
                {**tag_type.tag.property_types, **tag_type.value.property_types}  # type: ignore
            )
        return cls(
            tag_type,  # type: ignore
            types.TypeRegistry.type_from_dict(d["value"]),
        )

    def _to_dict(self) -> dict:
        return {"tag": self.tag.to_dict(), "value": self.value.to_dict()}

    def _assign_type_inner(self, next_type: types.Type) -> bool:
        return (
            isinstance(next_type, TaggedValueType)
            and self.tag.assign_type(next_type.tag)
            and self.value.assign_type(next_type.value)
        )

    def save_instance(
        self, obj: types.Any, artifact: artifacts_local.Artifact, name: str
    ) -> None:
        serializer = mappers_python.map_to_python(self, artifact)

        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(
        self,
        artifact: artifacts_local.Artifact,
        name: str,
        extra: typing.Optional[list[str]] = None,
    ) -> typing.Any:
        with artifact.open(f"{name}.object.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)

    def __repr__(self) -> str:
        return f"TaggedValueType({self.tag}, {self.value})"


class TaggedValueMapper(mappers.Mapper):
    def __init__(
        self,
        type_: TaggedValueType,
        mapper: typing.Callable,  # TODO: Make this more specific
        artifact: artifacts_local.Artifact,
        path: list[str] = [],
    ):
        self.type = type_
        self._artifact = artifact
        self._tag_serializer = mapper(type_.tag, artifact, path=path + ["_tag"])
        self._value_serializer = mapper(type_.value, artifact, path=path + ["_value"])


class TaggedValueToPy(TaggedValueMapper):
    def apply(self, obj: typing.Any) -> dict:
        result = {}
        obj_tags = tag_store.get_tags(obj)
        if len(set(self.type.tag.property_types.keys()) - set(obj_tags.keys())) > 0:
            raise errors.WeaveTypeError(
                f"Expected tags {self.type.tag.property_types.keys()}, found {obj_tags.keys()}"
            )
        result["_tag"] = self._tag_serializer.apply(obj_tags)
        result["_value"] = self._value_serializer.apply(obj)
        return result


class TaggedValueFromPy(TaggedValueMapper):
    def apply(self, obj: dict) -> typing.Any:
        # If the value is a string, but the type is not, then we assume it is a reference.
        # In this case, we should follow the reference before deserializing the value.
        # We only want to use that target reference if the value is actually the true value
        if isinstance(obj["_value"], str) and not self.type.value.assign_type(
            types.String()
        ):
            try:
                ref = refs.Ref.from_str(obj["_value"])
                if not isinstance(ref, refs.MemRef) and ref.type == self.type:
                    return ref.get()
            except (errors.WeaveInvalidURIError, errors.WeaveStorageError):
                # This would indicate that the value is not a reference.
                pass
        value = self._value_serializer.apply(obj["_value"])
        tags = self._tag_serializer.apply(obj["_tag"])
        value = box.box(value)
        tag_store.add_tags(value, tags)
        return value
