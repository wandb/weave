"""
This file contains the Weave Types and Mappers needed to handle tagged values.

Here we will briefly describe how TaggedValues work. Firstly, note that we need
to be able to associate any object in the python runtime with a set of tags. Due
to the way Python works, the best way to implement this is to use a memory
mapping from the python id of an object to a dictionary of tags. This is
implemented in tag_store.py. Unlike other Weave Types, we cannot determine if an
object is tagged simply by looking at its python type, so the TaggedValueType
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
(creating a new memory address) or is not weavifiable, in which case we will simply
drop tags.
"""

import dataclasses
import json
import typing
import functools

from ... import box
from ... import weave_types as types
from ... import mappers_python
from ... import errors
from ... import mappers

from . import tag_store

if typing.TYPE_CHECKING:
    from ... import artifact_base
    from ... import artifact_fs


def flatten_tag_type_to_typed_dict(tag_type: types.Type) -> types.TypedDict:
    """
    In Weave0, we have a more loose definition of what a TaggedValue is. Specifically,
    a TaggedValue type in Weave0 must conform to the following:
        * Tag: Anything, but in practice is either (or a union of):
                * A TypedDict
                * A TaggedValue (where the value side of the chain are TypedDicts)
        * Value: Must not be a TaggedValue

    This means your data shape looks like a chain of TaggedValues. Consider the following:

    b_0 = type_0
    l_1 = Tag({t_1: tv_1}, b_0) =
    Tagged<
        Dict<
            t_1: tv_1
        >,
        b_0
    >
    l_2 = Tag({t_2: tv_2}, l_1) =
    Tagged<
        Tagged<
            Dict<
                t_1: tv_1
            >,
            Dict<
                t_2: tv_2
            >
        >,
        b_0
    >
    l_3 = Tag({t_3: tv_3}, l_2) =
    Tagged<
        Tagged<
            Tagged<
                Dict<
                    t_1: tv_1
                >,
                Dict<
                    t_2: tv_2
                >
            >,
            Dict<
                t_3: tv_3
            >
        >,
        b_0
    >

    When deciding if a type has a specific tag, we traverse the tag chain. essentially,
    perform the following logic:

    def find_tag(obj):
        if isinstance(obj, TaggedValue):
            return _find_tag_inner(obj.tag)
        else:
            return None

    def _find_tag_inner(obj):
        if isinstance(type.val, TypedDict) and tag_name in type.val:
            return type.val[tag_name]
        elif isinstance(type.tag, TypedDict) and tag_name in type.tag:
            return type.tag[tag_name]
        elif isinstance(type.tag, TaggedValue):
            return _find_tag_inner(type.tag, tag_name)
        else:
            return None

    However, in Weave1, we have a more strict definition of what a TaggedValue is. Specifically:
        * Tag: Must be a TypedDict (values can be TaggedValues)
        * Value: Must not be a TaggedValue

    This means that we need to flatten the tag chain into a single TypedDict.The primary
    disadvantage of this approach to Weave0 is that if we have a tag-key collision then
    only the most recent tag is available. So, the above example becomes:
    Tagged<
        Dict<
            t_1: tv_1,
            t_2: tv_2,
            t_3: tv_3
        >,
        b_0
    >

    This is not strictly necessary - i think if we want we can convert to Weave0's
    definition of TaggedValue. However, this is much nicer to work with and understand.


    This function is used to perform the above described flattening of the tag-side of the
    TaggedValue chain.
    """

    # First, if the tag is already a TypedDict, then we are good
    if isinstance(tag_type, types.TypedDict):
        return tag_type

    # Next, if the tag_type is a union, then we want to merge the results.
    # This is subtly different than Weave0, but ensures that the result
    # is always a TypedDict.
    elif isinstance(tag_type, types.UnionType):
        base_type = types.TypedDict({})
        for member in tag_type.members:
            if not isinstance(member, types.NoneType):
                base_type = types.merge_types(base_type, flatten_tag_type_to_typed_dict(member))  # type: ignore
        return base_type

    # Finally, if the tag_type is a TaggedValue, then we want to merge the tag
    # and value props together.
    elif isinstance(tag_type, TaggedValueType):
        assert types.TypedDict({}).assign_type(tag_type.tag), (
            "tag_type.tag must be assignable to TypedDict, found %s" % tag_type.tag
        )
        assert types.TypedDict({}).assign_type(tag_type.value), (
            "tag_type.value must be assignable to TypedDict, found %s" % tag_type.value
        )
        return types.TypedDict(
            {**tag_type.tag.property_types, **tag_type.value.property_types}  # type: ignore
        )
    else:
        raise errors.WeaveTypeError(
            f"tag_type must be TypedDict, UnionType, or TaggedValueType, found {tag_type}"
        )


# A custom Weave Type used to represent tagged values.
@dataclasses.dataclass(frozen=True)
class TaggedValueType(types.Type):
    name = "tagged"
    tag: types.TypedDict = dataclasses.field(
        default_factory=lambda: types.TypedDict({})
    )
    value: types.Type = dataclasses.field(default_factory=lambda: types.Any())

    _assignment_form_cached = None

    # We use this technique to apply post-processing to the inputs, but also works
    # around the frozen dataclass issue.
    def __post_init__(self) -> None:
        if isinstance(self.value, TaggedValueType):
            self.__dict__["tag"] = types.TypedDict(
                {
                    **self.tag.property_types,
                    **self.value.tag.property_types,
                }
            )
            if isinstance(self.value.value, TaggedValueType):
                raise errors.WeaveTypeError(
                    f"TaggedValueType value types cannot be TaggedValueType, found {self.value.value}"
                )
            self.__dict__["value"] = self.value.value

        # This post processing step is to handle the case where the value is a
        # union of None and a TaggedValueType. This is a common pattern in
        # Weave. In this step, we hoist the tags in the inner TaggedValueType up
        # to the outer TaggedValueType and make them optional, leaving the union
        # to be a union of None and the TaggedValueType's inner value type.
        # While this seems highly specific, the motivation is to solve a bug in
        # Arrow.
        #
        # Firstly, let's justify why this is allowed in the first place. Take
        # the following type: Tagged<{TO},Maybe<Tagged<TI, TV>>. The
        # transformation ends up being: Tagged<{TO, Maybe<TI>},Maybe<TV>>. Now,
        # from a Weave0 compatibility perspective, this is fine because anything
        # the original type is assignable to, the new type is also assignable
        # to. Therefore we are making a slightly broader type here.
        #
        # In fact, I think we can generalize this even farther to always merge
        # out inner unions of TaggedValues.
        #
        # From an op perspective, this fits our model since any tag get
        # operation on the original type will result in an optional value if the
        # tag is on the inner TaggedValue. So, this is perfectly compatible.
        #
        # Now, why do this? The main motivation is AWL. When adding tags to AWL,
        # we use a helper function `direct_add_arrow_tags` which will merge tags
        # in an attempt to conform to the post processing rule above. However,
        # there is one edge case which is incorrect: when the inner value is
        # this optional tagged value case. The reason is because the arrow's
        # `nullable` property on fields is not the same as the Weave union None
        # type. So we have no way of knowing if there is an intermediate "None"
        # and therefore will always merge the tags. This creates a bug when
        # doing type traversal because the Weave type does not match the
        # underlying data shape anymore. This post processing step ensures the
        # types are always aligned.
        #
        # As a bonus, this actually makes the types more accurate with respect
        # to how they are stored in the op_store as well. In the op_store, we
        # merge types in a similar manner, but since we don't need to do any
        # column mapping on the op_store data we never ran into this problem.
        if isinstance(self.value, types.UnionType):
            if len(self.value.members) == 2:
                maybe_none_type = None
                maybe_tagged_value_type = None
                for member in self.value.members:
                    if isinstance(member, types.NoneType):
                        maybe_none_type = member
                    elif isinstance(member, TaggedValueType):
                        maybe_tagged_value_type = member
                if maybe_none_type and maybe_tagged_value_type:
                    new_tag = types.TypedDict(
                        {
                            **self.tag.property_types,
                            **{
                                k: types.optional(v)
                                for k, v in maybe_tagged_value_type.tag.property_types.items()
                            },
                        }
                    )
                    new_value = maybe_tagged_value_type.value

                    self.__dict__["tag"] = new_tag
                    self.__dict__["value"] = new_value

    def simple_str(self) -> str:
        return str(self.value)

    @functools.cached_property
    def _assignment_form(self) -> types.Type:
        if isinstance(self.value, types.UnionType):
            return types.union(
                *[TaggedValueType(self.tag, mem) for mem in self.value.members]
            )
        return self

    def _is_assignable_to(self, other_type: types.Type) -> typing.Optional[bool]:
        if other_type.__class__ != TaggedValueType:
            return other_type.assign_type(self.value)
        return None

    def __getattr__(self, attr: str) -> typing.Any:
        # When getting a property from a tagged value, we want the request to
        # flow through to the inner type. However, if we are getting a type
        # property, we want to wrap the type correctly on the way out. There are
        # two special cases: 1 for property_types and 1 for members. (typeddict
        # and union).
        res = getattr(self.value, attr)
        if isinstance(res, types.Type):
            res = TaggedValueType(self.tag, res)
        elif attr == "property_types" and isinstance(res, dict):
            res = {k: TaggedValueType(self.tag, v) for k, v in res.items()}
        elif attr == "members" and isinstance(res, list):
            res = [TaggedValueType(self.tag, v) for v in res]
        return res

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
        tag_type = flatten_tag_type_to_typed_dict(
            types.TypeRegistry.type_from_dict(d["tag"])
        )
        value_type = types.TypeRegistry.type_from_dict(d["value"])
        res = cls(
            tag_type,
            value_type,
        )
        return res

    def _to_dict(self) -> dict:
        return {"tag": self.tag.to_dict(), "value": self.value.to_dict()}

    def save_instance(
        self, obj: types.Any, artifact: "artifact_fs.FilesystemArtifact", name: str
    ) -> None:
        serializer = mappers_python.map_to_python(self, artifact)

        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(
        self,
        artifact: "artifact_fs.FilesystemArtifact",
        name: str,
        extra: typing.Optional[list[str]] = None,
    ) -> typing.Any:
        with artifact.open(f"{name}.object.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)

    def __repr__(self) -> str:
        return (
            f"TaggedValueType({{{list(self.tag.property_types.keys())}}}, {self.value})"
        )


class TaggedValueMapper(mappers.Mapper):
    def __init__(
        self,
        type_: TaggedValueType,
        mapper: typing.Callable,  # TODO: Make this more specific
        artifact: "artifact_base.Artifact",
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
        expected_tag_keys = set(
            key
            for key, tag_type in self.type.tag.property_types.items()
            if not types.is_optional(tag_type)
        )
        if len(expected_tag_keys - set(obj_tags.keys())) > 0:
            raise errors.WeaveTypeError(
                f"Expected tags {self.type.tag.property_types.keys()}, found {obj_tags.keys()}"
            )
        result["_tag"] = self._tag_serializer.apply(obj_tags)
        result["_value"] = self._value_serializer.apply(obj)
        return result


class TaggedValueFromPy(TaggedValueMapper):
    def apply(self, obj: dict) -> typing.Any:
        value = self._value_serializer.apply(obj["_value"])
        tags = self._tag_serializer.apply(obj["_tag"])
        value = box.box(value)
        tag_store.add_tags(value, tags)
        return value
