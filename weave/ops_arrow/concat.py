# Concat implementation for ArrowWeaveList. Should work in all cases!
#
# Any places where we extend lists need to follow our merge_types implementation.
# Fortunately, concat is the only place that extends lists! Everything else should
# make use of concat to do so.


import typing
import dataclasses
import numpy as np
import pyarrow as pa
from pyarrow import compute as pc

from .. import weave_types as types
from ..language_features.tagging import tagged_value_type

from . import errors
from .list_ import (
    ArrowWeaveList,
    ArrowWeaveListGeneric,
    is_typedict_arrowweavelist,
    is_object_arrowweavelist,
    is_taggedvalue_arrowweavelist,
    is_list_arrowweavelist,
    unsafe_awl_construction,
    offsets_starting_at_zero,
    make_vec_none,
)

DEBUG = False

from .. import engine_trace

tracer = engine_trace.tracer()


@dataclasses.dataclass
class UnionMember:
    values: ArrowWeaveList
    mask: pa.Array
    offsets: pa.Array


def indent_print(indent: int = 0, *args) -> None:
    if DEBUG:
        print("    " * indent + " ".join([str(a) for a in args]))


def pa_concat_arrays(arrays: list[typing.Union[pa.Array, pa.ChunkedArray]]) -> pa.Array:
    arrays = [a if isinstance(a, pa.Array) else a.combine_chunks() for a in arrays]

    with tracer.trace("pa_concat_arrays"):
        try:
            return pa.concat_arrays(arrays)
        except pa.lib.ArrowNotImplementedError as e:
            # pyarrow doesn't support concatenating all dictionaries, so we have to do it ourselves.
            if all(isinstance(a, pa.DictionaryArray) for a in arrays):
                # We can concatenate dictionaries by concatenating the indices and the dictionary
                # values separately.

                index_offset = 0
                indices = []
                for a in arrays:
                    indices.append(pc.add(a.indices, index_offset).cast(pa.int32()))
                    index_offset += len(a.dictionary)

                indices = pa_concat_arrays(indices)
                dictionary = pa_concat_arrays([a.dictionary for a in arrays])
                return pa.DictionaryArray.from_arrays(indices, dictionary)
            else:
                raise


def _concatenate_typeddicts(
    l1: ArrowWeaveListGeneric[types.TypedDict],
    l2: ArrowWeaveListGeneric[types.TypedDict],
    depth: int = 0,
) -> ArrowWeaveList:
    # Columns are in the order they're encountered.
    all_keys = {**l1.object_type.property_types, **l2.object_type.property_types}
    if not all_keys:
        # Both are empty
        return ArrowWeaveList(
            pa_concat_arrays([l1._arrow_data, l2._arrow_data]),
            types.TypedDict({}),
            invalid_reason="Possibly nullable",
        )
    properties: dict[str, ArrowWeaveList] = {}
    for key in all_keys:
        indent_print(depth, "TypedDict key", key)
        if key not in l1.object_type.property_types:
            properties[key] = _concatenate(
                make_vec_none(len(l1._arrow_data)), l2.column(key), depth=depth + 1
            )
        elif key not in l2.object_type.property_types:
            properties[key] = _concatenate(
                l1.column(key), make_vec_none(len(l2)), depth=depth + 1
            )
        else:
            properties[key] = _concatenate(
                l1.column(key), l2.column(key), depth=depth + 1
            )

    return ArrowWeaveList(
        pa.StructArray.from_arrays(
            [properties[key]._arrow_data for key in all_keys],
            list(all_keys),
            mask=pa_concat_arrays(
                [
                    pa.compute.is_null(l1._arrow_data),
                    pa.compute.is_null(l2._arrow_data),
                ]
            ),
        ),
        types.TypedDict({key: properties[key].object_type for key in all_keys}),
        l1._artifact,
        invalid_reason="Possibly nullable",
    )


def _concatenate_objects(
    l1: ArrowWeaveListGeneric[types.ObjectType],
    l2: ArrowWeaveListGeneric[types.ObjectType],
    depth: int = 0,
) -> ArrowWeaveList:
    assert l1.object_type.name == l2.object_type.name
    attrs: dict[str, ArrowWeaveList] = {}
    merged_type = typing.cast(
        types.ObjectType, types.merge_types(l1.object_type, l2.object_type)
    )
    for key in merged_type.property_types():
        attrs[key] = _concatenate(l1.column(key), l2.column(key), depth=depth + 1)
    return ArrowWeaveList(
        pa.StructArray.from_arrays(
            [attrs[key]._arrow_data for key in attrs],
            list(attrs.keys()),
            mask=pa_concat_arrays(
                [
                    pa.compute.is_null(l1._arrow_data),
                    pa.compute.is_null(l2._arrow_data),
                ]
            ),
        ),
        merged_type,
        l1._artifact,
        invalid_reason="Possibly nullable",
    )


def _concatenate_taggedvalues(
    l1: ArrowWeaveListGeneric[tagged_value_type.TaggedValueType],
    l2: ArrowWeaveListGeneric[tagged_value_type.TaggedValueType],
    depth: int = 0,
) -> ArrowWeaveList:
    tag = _concatenate(l1.tagged_value_tag(), l2.tagged_value_tag(), depth=depth + 1)
    value = _concatenate(
        l1.tagged_value_value(), l2.tagged_value_value(), depth=depth + 1
    )
    return ArrowWeaveList(
        pa.StructArray.from_arrays(
            [tag._arrow_data, value._arrow_data],
            ["_tag", "_value"],
            mask=pa_concat_arrays(
                [
                    pa.compute.is_null(l1._arrow_data),
                    pa.compute.is_null(l2._arrow_data),
                ]
            ),
        ),
        tagged_value_type.TaggedValueType(tag.object_type, value.object_type),  # type: ignore
        l1._artifact,
        invalid_reason="Possibly nullable",
    )


def _concatenate_lists(
    l1: ArrowWeaveListGeneric[types.List],
    l2: ArrowWeaveListGeneric[types.List],
    depth: int = 0,
) -> ArrowWeaveList:
    self_values: ArrowWeaveList = ArrowWeaveList(
        l1._arrow_data.flatten(), l1.object_type.object_type, l2._artifact
    )
    other_values: ArrowWeaveList = ArrowWeaveList(
        l2._arrow_data.flatten(), l2.object_type.object_type, l2._artifact
    )
    concatted_values = _concatenate(self_values, other_values, depth=depth + 1)
    new_offsets = pa_concat_arrays(
        [
            offsets_starting_at_zero(l1._arrow_data)[:-1],
            pa.compute.add(
                offsets_starting_at_zero(l2._arrow_data),
                len(self_values),
            ).cast(pa.int32()),
        ]
    )
    return ArrowWeaveList(
        pa.ListArray.from_arrays(
            new_offsets,
            concatted_values._arrow_data,
            mask=pa_concat_arrays(
                [
                    pa.compute.is_null(l1._arrow_data),
                    pa.compute.is_null(l2._arrow_data),
                ]
            ),
        ),
        types.List(
            types.merge_types(l1.object_type.object_type, l2.object_type.object_type)
        ),
        l1._artifact,
        invalid_reason="Possibly nullable",
    )


def _concatenate_non_unions(
    self: ArrowWeaveList, other: ArrowWeaveList, depth: int = 0
) -> typing.Optional[ArrowWeaveList]:
    if is_typedict_arrowweavelist(self) and is_typedict_arrowweavelist(other):
        return _concatenate_typeddicts(self, other, depth=depth)
    elif is_object_arrowweavelist(self) and is_object_arrowweavelist(other):
        if self.object_type.name == other.object_type.name:
            return _concatenate_objects(self, other, depth=depth)
    elif is_taggedvalue_arrowweavelist(self) and is_taggedvalue_arrowweavelist(other):
        return _concatenate_taggedvalues(self, other, depth=depth)
    elif is_list_arrowweavelist(self) and is_list_arrowweavelist(other):
        # Lists with different object types
        return _concatenate_lists(self, other, depth=depth)

    if isinstance(self.object_type, types.Number) and isinstance(
        other.object_type, types.Number
    ):
        # Numeric special case
        indent_print(
            depth, "Extend case number types", self.object_type, other.object_type
        )

        # Weave numeric types are odd for legacy reasons. We have three numeric types
        # Number, Float, Int. Unfortunately Number is a Union of Float and Int, but
        # also assignable to Int.

        # We should fix that. But for now we rely on the arrow type for this special
        # case.

        if self._arrow_data.type == other._arrow_data.type:
            new_arrow_type = self._arrow_data.type
        else:
            # If types aren't equal, just cast to float64. This is not entirely
            # correct! Very large integers will be truncated.
            new_arrow_type = pa.float64()

        new_weave_type: types.Type
        if pa.types.is_integer(new_arrow_type):
            new_weave_type = types.Int()
        elif pa.types.is_floating(new_arrow_type):
            new_weave_type = types.Float()
        else:
            raise errors.WeaveInternalError('Unexpected type for "Number" type.')

        if len(self) == 0:
            data = other._arrow_data
        elif len(other) == 0:
            data = self._arrow_data
        else:
            data = pa_concat_arrays(
                [
                    self._arrow_data.cast(new_arrow_type),
                    other._arrow_data.cast(new_arrow_type),
                ]
            )
        return ArrowWeaveList(
            data, new_weave_type, self._artifact, invalid_reason="Possibly nullable"
        )
    elif self.object_type == other.object_type:
        # Types exactly equal case
        indent_print(depth, "Extend case equal", self.object_type, other.object_type)
        if len(self) == 0:
            data = other._arrow_data
        elif len(other) == 0:
            data = self._arrow_data
        else:
            data = pa_concat_arrays([self._arrow_data, other._arrow_data])
        return ArrowWeaveList(
            data, self.object_type, self._artifact, invalid_reason="Possibly nullable"
        )
    return None


def _concatenate(
    self: "ArrowWeaveList", other: "ArrowWeaveList", depth=0
) -> "ArrowWeaveList":
    if depth > 50:
        raise ValueError("Maximum recursion depth exceeded")
    indent_print(depth, "EXTEND TOP", depth, self.object_type, other.object_type)

    # We use UnknownType for two things:
    #   1. to indicate that we don't know the type of an object,
    #   2. as the object type of a zero length array.
    # The former case, where we don't know the type of an object,
    # should never happen here! This is runtime and we know the types of
    # things.

    # Zero length arrays of unknown type
    if self.object_type == types.UnknownType():
        if len(self) == 0:
            return other
        else:
            raise errors.WeaveInternalError(
                'Encountered non-zero length "UnknownType" array'
            )
    if other.object_type == types.UnknownType():
        if len(other) == 0:
            return self
        else:
            raise errors.WeaveInternalError(
                'Encountered non-zero length "UnknownType" array'
            )

    # Cases where one of the types is None
    if isinstance(self.object_type, types.NoneType) and isinstance(
        other.object_type, types.NoneType
    ):
        return make_vec_none(len(self) + len(other))
    elif isinstance(self.object_type, types.NoneType):
        indent_print(depth, "Extend case self None")
        if len(self) == 0:
            return other
        elif len(other) == 0:
            return self
        self_data = pa.nulls(len(self), other._arrow_data.type)
        other_data = other._arrow_data
        data = pa_concat_arrays([self_data, other_data])
        return ArrowWeaveList(data, types.optional(other.object_type), other._artifact)
    elif isinstance(other.object_type, types.NoneType):
        indent_print(depth, "Extend case other None")
        if len(self) == 0:
            return other
        elif len(other) == 0:
            return self
        self_data = self._arrow_data
        other_data = pa.nulls(len(other), self._arrow_data.type)
        data = pa_concat_arrays([self_data, other_data])
        return ArrowWeaveList(data, types.optional(self.object_type), self._artifact)

    # Separate nulls from type
    self_nullable, self_non_none_type = types.split_none(self.object_type)
    other_nullable, other_non_none_type = types.split_none(other.object_type)
    self = self._with_object_type(
        self_non_none_type, invalid_reason="Possibly nullable"
    )
    other = other._with_object_type(
        other_non_none_type, invalid_reason="Possibly nullable"
    )
    result_nullable = self_nullable or other_nullable

    if not isinstance(self.object_type, types.UnionType) and not isinstance(
        other.object_type, types.UnionType
    ):
        result = _concatenate_non_unions(self, other, depth=depth)
        if result is not None:
            if result_nullable:
                return result._with_object_type(types.optional(result.object_type))
            else:
                return result._clear_invalid_reason()

    # Otherwise, we have types that can't be merged, we're going to produce a union

    if isinstance(self.object_type, types.UnionType):
        self_field_types = self.object_type.members
        self_type_codes = self._arrow_data.type_codes
        self_offsets = self._arrow_data.offsets
        self_fields = [
            self._arrow_data.field(i) for i in range(len(self._arrow_data.type))
        ]
    else:
        self_field_types = [self.object_type]
        self_type_codes = pa.array(np.zeros(len(self), dtype=np.int8))
        self_offsets = pa.array(np.arange(len(self), dtype=np.int32))
        self_fields = [self._arrow_data]

    if isinstance(other.object_type, types.UnionType):
        other_field_types = other.object_type.members
        other_type_codes = other._arrow_data.type_codes
        other_offsets = other._arrow_data.offsets
        other_fields = [
            other._arrow_data.field(i) for i in range(len(other._arrow_data.type))
        ]
    else:
        other_field_types = [other.object_type]
        other_type_codes = pa.array(np.zeros(len(other), dtype=np.int8))
        other_offsets = pa.array(np.arange(len(other), dtype=np.int32))
        other_fields = [other._arrow_data]

    assert len(self_field_types) == len(self_fields)
    assert len(other_field_types) == len(other_fields)

    # produce merged union
    new_member_awls: list[UnionMember] = []

    indent_print(depth, "MERGING UNIONS")
    indent_print(depth, "SELF NULLABLE", self_nullable)
    # indent_print(depth, "SELF MEMBERS")
    # for member in self_fields:
    #     indent_print(depth + 1, member)
    indent_print(depth, "OTHER NULLABLE", other_nullable)
    # indent_print(depth, "OTHER MEMBERS")
    # for member in other_fields:
    #     indent_print(depth + 1, member)

    remaining_other_indexes = {i: True for i in range(len(other_fields))}
    for self_i, (self_member_type, self_field) in enumerate(
        zip(self_field_types, self_fields)
    ):
        for other_i in remaining_other_indexes:
            other_member_type = other_field_types[other_i]
            other_field = other_fields[other_i]
            if types.types_are_mergeable(self_member_type, other_member_type):
                indent_print(
                    depth,
                    "SELF OTHER FIELD merge",
                    self_i,
                    other_i,
                    "self type:",
                    self_member_type,
                    "other type:",
                    other_member_type,
                )
                concatted = _concatenate_non_unions(
                    ArrowWeaveList(
                        self_field, self_member_type, invalid_reason="Possibly nullable"
                    ),
                    ArrowWeaveList(
                        other_field,
                        other_member_type,
                        invalid_reason="Possibly nullable",
                    ),
                )
                if concatted is None:
                    raise errors.WeaveInternalError(
                        "Could not concatenate mergable types"
                    )
                new_member_awls.append(
                    UnionMember(
                        values=concatted,
                        mask=pa_concat_arrays(
                            [
                                pa.compute.equal(self_type_codes, self_i).cast(
                                    pa.int8()
                                ),
                                pa.compute.equal(other_type_codes, other_i).cast(
                                    pa.int8()
                                ),
                            ]
                        ),
                        offsets=pa_concat_arrays(
                            [
                                self_offsets,
                                pa.compute.add(other_offsets, len(self_field)).cast(
                                    pa.int32()
                                ),
                            ]
                        ),
                    )
                )
                indent_print(
                    depth,
                    "SELF OTHER FIELD merge RESULT",
                    new_member_awls[-1].values.object_type,
                )
                remaining_other_indexes.pop(other_i)
                break
        else:
            # no matching other member found
            indent_print(depth, "SELF FIELD solo", self_i, self_member_type)
            new_member_awls.append(
                UnionMember(
                    values=ArrowWeaveList(
                        self_fields[self_i],
                        self_member_type,
                        self._artifact,
                        invalid_reason="Possibly nullable",
                    ),
                    mask=pa_concat_arrays(
                        [
                            pa.compute.equal(self_type_codes, self_i).cast(pa.int8()),
                            pa.array(np.zeros(len(other), dtype=np.int8)),
                        ]
                    ),
                    # offsets=pa.array(np.arange(len(self), dtype=np.int32)),
                    offsets=pa_concat_arrays(
                        [
                            self_offsets,
                            pa.array(np.zeros(len(other), dtype=np.int32)),
                        ]
                    ),
                )
            )
    for other_i in remaining_other_indexes:
        other_member_type = other_field_types[other_i]
        indent_print(depth, "OTHER FIELD solo", other_i, other_member_type)
        other_field = other_fields[other_i]
        new_member_awls.append(
            UnionMember(
                values=ArrowWeaveList(
                    other_field,
                    other_member_type,
                    other._artifact,
                    invalid_reason="Possibly nullable",
                ),
                mask=pa_concat_arrays(
                    [
                        pa.array(np.zeros(len(self), dtype=np.int8)),
                        pa.compute.equal(other_type_codes, other_i).cast(pa.int8()),
                    ]
                ),
                # offsets=pa.array(np.arange(len(other), dtype=np.int32)),
                offsets=pa_concat_arrays(
                    [
                        pa.array(np.zeros(len(self), dtype=np.int32)),
                        other_offsets,
                    ]
                ),
            )
        )

    # I think we will always have at least two union members here. Because we
    # must have had a union on one side coming in.
    if len(new_member_awls) < 2:
        raise errors.WeaveInternalError("Not enough union members after merge")

    member_types = [m.values.object_type for m in new_member_awls]

    result_type_codes = pa.array(np.zeros(len(self) + len(other), dtype=np.int8))
    for i, new_member_awl in enumerate(new_member_awls):
        result_type_codes = pa.compute.add(
            result_type_codes, pa.compute.multiply(new_member_awl.mask, i)
        )
    result_offsets = pa.array(np.zeros(len(self) + len(other), dtype=np.int32))
    for i, new_member_awl in enumerate(new_member_awls):
        result_offsets = pa.compute.add(
            result_offsets,
            pa.compute.multiply(new_member_awl.mask, new_member_awl.offsets),
        )

    assert len(member_types) == len(new_member_awls)
    expected_object_type_members = len(new_member_awls)
    new_object_type = types.UnionType(*member_types)
    if len(new_object_type.members) != expected_object_type_members:
        indent_print(
            depth,
            "ERROR PRODUCING UNION",
            len(new_object_type.members),
            len(new_member_awls),
        )
        indent_print(depth, "new_object.type.members")
        for m in new_object_type.members:
            indent_print(depth + 1, m)
        indent_print(depth, "new_member_awls")
        for m2 in new_member_awls:
            indent_print(depth + 1, m2.values.object_type)

        assert len(new_object_type.members) == expected_object_type_members

    indent_print(depth, "NEW MEMBER TYPE", new_object_type)
    indent_print(depth, "RESULT NULLABLE", result_nullable)
    return ArrowWeaveList(
        pa.UnionArray.from_dense(
            result_type_codes.cast(pa.int8()),
            result_offsets.cast(pa.int32()),
            [m.values._arrow_data for m in new_member_awls],
        ),
        types.optional(new_object_type) if result_nullable else new_object_type,
        self._artifact,
    )


def concatenate(
    self: "ArrowWeaveList", other: "ArrowWeaveList", depth=0
) -> "ArrowWeaveList":
    with unsafe_awl_construction("Possibly nullable"):
        result = _concatenate(self, other, depth)
    result.validate()
    return result
