import pyarrow as pa
import pyarrow.compute as pc
import typing


from .. import artifact_base
from .. import weave_types as types
from .. import box
from .. import mappers_arrow
from ..language_features.tagging import tag_store, tagged_value_type
from .. import artifact_mem
from .. import errors
from .. import arrow_util
from .. import api


from .arrow import (
    ArrowWeaveListType,
)
from .list_ import ArrowWeaveList, PathType, unsafe_awl_construction


# Hmm... this doesn't work on ObjectType, which contains a Union of Struct...
# We need that because our ImageFileArtifactRefType has a union of structs
# in its property types.

# Could test a fix by hard-coding that to be the merged type, just to show it
# works...


def recursively_merge_union_types_if_they_are_unions_of_structs(
    type_: types.Type,
) -> types.Type:
    """Input preprocessor for to_arrow()."""
    if isinstance(type_, types.TypedDict):
        return types.TypedDict(
            {
                k: recursively_merge_union_types_if_they_are_unions_of_structs(v)
                for k, v in type_.property_types.items()
            }
        )
    elif isinstance(type_, types.UnionType):
        if type_.is_simple_nullable() or len(type_.members) < 2:
            return type_

        new_type = type_.members[0]
        for member in type_.members[1:]:
            new_type = types.merge_types(new_type, member)

        if isinstance(new_type, types.UnionType):
            # cant go down any further
            return new_type

        return recursively_merge_union_types_if_they_are_unions_of_structs(new_type)

    elif isinstance(type_, types.List):
        return types.List(
            recursively_merge_union_types_if_they_are_unions_of_structs(
                type_.object_type
            )
        )
    elif isinstance(type_, ArrowWeaveListType):
        return ArrowWeaveListType(
            recursively_merge_union_types_if_they_are_unions_of_structs(
                type_.object_type
            )
        )
    elif isinstance(type_, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueType(
            typing.cast(
                types.TypedDict,
                recursively_merge_union_types_if_they_are_unions_of_structs(type_.tag),
            ),
            recursively_merge_union_types_if_they_are_unions_of_structs(type_.value),
        )

    return type_


def recursively_build_pyarrow_array(
    py_objs: list[typing.Any],
    pyarrow_type: typing.Union[pa.DataType, arrow_util.ArrowTypeWithFieldInfo],
    mapper,
    py_objs_already_mapped: bool = False,
) -> pa.Array:
    arrays: list[pa.Array] = []

    if isinstance(pyarrow_type, arrow_util.ArrowTypeWithFieldInfo):
        pyarrow_type = arrow_util.arrow_type(pyarrow_type)
    pyarrow_type = typing.cast(pa.DataType, pyarrow_type)

    def none_unboxer(iterator: typing.Iterable):
        for obj in iterator:
            if isinstance(obj, box.BoxedNone):
                # get rid of box
                yield None
            else:
                yield obj

    if isinstance(mapper.type, types.UnionType) and mapper.type.is_simple_nullable():
        nonnull_mapper = [
            m for m in mapper._member_mappers if m.type != types.NoneType()
        ][0]

        return recursively_build_pyarrow_array(
            list(none_unboxer(py_objs)),
            pyarrow_type,
            nonnull_mapper,
            py_objs_already_mapped,
        )
    elif pa.types.is_null(pyarrow_type):
        return pa.array(
            none_unboxer(py_objs),
            type=pyarrow_type,
        )

    elif pa.types.is_struct(pyarrow_type):
        keys: list[str] = []
        # keeps track of null values so that we can null entries at the struct level
        mask: list[bool] = []

        assert isinstance(
            mapper,
            (
                mappers_arrow.TypedDictToArrowStruct,
                mappers_arrow.TaggedValueToArrowStruct,
                mappers_arrow.ObjectToArrowStruct,
                mappers_arrow.GQLHasKeysToArrowStruct,
            ),
        )

        if isinstance(mapper, mappers_arrow.GQLHasKeysToArrowStruct):
            _dictionary: dict[typing.Optional[str], typing.Tuple[int, typing.Any]] = {}
            indices: list[typing.Optional[int]] = []
            for py_obj in py_objs:
                id = py_obj["id"] if py_obj is not None else None
                if id in _dictionary:
                    indices.append(_dictionary[id][0])
                else:
                    new_index = len(_dictionary)
                    _dictionary[id] = (new_index, py_obj)
                    indices.append(new_index)

            dictionary = [
                mapper.apply(v[1]) if v[1] is not None else None
                for v in _dictionary.values()
            ]
            array = recursively_build_pyarrow_array(
                dictionary,
                pyarrow_type,
                mapper.as_typeddict_mapper(),
                True,
            )

            indices = pa.array(indices, type=pa.int32())
            return pa.DictionaryArray.from_arrays(indices, array)

        else:
            # handle empty struct case - the case where the struct has no fields
            if len(pyarrow_type) == 0:
                return pa.array(py_objs, type=pyarrow_type)

            for i, field in enumerate(pyarrow_type):
                data: list[typing.Any] = []
                if isinstance(
                    mapper,
                    mappers_arrow.TypedDictToArrowStruct,
                ):
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        else:
                            data.append(py_obj.get(field.name, None))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = recursively_build_pyarrow_array(
                        data,
                        field.type,
                        mapper._property_serializers[field.name],
                        py_objs_already_mapped,
                    )
                elif isinstance(
                    mapper,
                    mappers_arrow.ObjectToArrowStruct,
                ):
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        elif py_objs_already_mapped:
                            data.append(py_obj.get(field.name, None))
                        else:
                            data.append(getattr(py_obj, field.name, None))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = recursively_build_pyarrow_array(
                        data,
                        field.type,
                        mapper._property_serializers[field.name],
                        py_objs_already_mapped,
                    )

                elif isinstance(mapper, mappers_arrow.TaggedValueToArrowStruct):
                    if field.name == "_tag":
                        for py_obj in py_objs:
                            if py_obj is None:
                                data.append(None)
                            else:
                                data.append(tag_store.get_tags(py_obj))
                            if i == 0:
                                mask.append(py_obj is None)

                        array = recursively_build_pyarrow_array(
                            data,
                            field.type,
                            mapper._tag_serializer,
                            py_objs_already_mapped,
                        )
                    else:
                        for py_obj in py_objs:
                            if py_obj is None:
                                data.append(None)
                            else:
                                data.append(box.unbox(py_obj))
                            if i == 0:
                                mask.append(py_obj is None)

                        array = recursively_build_pyarrow_array(
                            data,
                            field.type,
                            mapper._value_serializer,
                            py_objs_already_mapped,
                        )
                else:
                    assert isinstance(
                        mapper,
                        mappers_arrow.GQLHasKeysToArrowStruct,
                    )
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        else:
                            data.append(mapper.apply(py_obj))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = recursively_build_pyarrow_array(
                        data,
                        field.type,
                        mapper._property_serializers[field.name],
                        False,
                    )

                arrays.append(array)
                keys.append(field.name)
            return pa.StructArray.from_arrays(
                arrays, keys, mask=pa.array(mask, type=pa.bool_())
            )
    elif pa.types.is_union(pyarrow_type):
        assert isinstance(mapper, mappers_arrow.UnionToArrowUnion)
        type_codes: list[int] = [
            0 if o == None else mapper.type_code_of_obj(o) for o in py_objs
        ]
        offsets: list[int] = []
        py_data: list[list] = []
        for _ in range(len(pyarrow_type)):
            py_data.append([])

        for row_index, type_code in enumerate(type_codes):
            offsets.append(len(py_data[type_code]))
            py_data[type_code].append(py_objs[row_index])

        for i, raw_py_data in enumerate(py_data):
            array = recursively_build_pyarrow_array(
                raw_py_data,
                pyarrow_type.field(i).type,
                mapper.mapper_of_type_code(i),
                py_objs_already_mapped,
            )
            arrays.append(array)

        return pa.UnionArray.from_dense(
            pa.array(type_codes, type=pa.int8()),
            pa.array(offsets, type=pa.int32()),
            arrays,
        )
    elif pa.types.is_list(pyarrow_type):
        assert isinstance(mapper, mappers_arrow.ListToArrowArr)
        offsets = [0]
        flattened_objs = []
        mask = []
        for obj in py_objs:
            mask.append(obj == None)
            if obj == None:
                obj = []
            offsets.append(offsets[-1] + len(obj))
            flattened_objs += obj
        new_objs = recursively_build_pyarrow_array(
            flattened_objs,
            pyarrow_type.value_type,
            mapper._object_type,
            py_objs_already_mapped,
        )
        return pa.ListArray.from_arrays(
            offsets, new_objs, mask=pa.array(mask, type=pa.bool_())
        )
    elif pa.types.is_temporal(pyarrow_type):
        if py_objs_already_mapped:
            return pa.array(py_objs, type=pyarrow_type)

    values = [mapper.apply(o) if o is not None else None for o in py_objs]

    # These are plain values.

    if mapper.type == types.Number():
        # Let pyarrow infer this type.
        # This covers the case where a Weave0 table includes a Number column that
        # contains integers that are too large for float64. We map Number to float64,
        # but allow it to be int64 as well in our ArrowWeaveList.validate method.
        res = pa.array(values)
        if pa.types.is_null(res.type):
            res = res.cast(pa.int64())
    else:
        res = pa.array(values, type=pyarrow_type)
    return res


# This will be a faster version fo to_arrow (below). Its
# used in op file-table, to convert from a wandb Table to Weave
# (that code is very experimental and not totally working yet)
def to_arrow_from_list_and_artifact(
    obj: typing.Any,
    object_type: types.Type,
    artifact: artifact_base.Artifact,
    py_objs_already_mapped: bool = False,
) -> ArrowWeaveList:
    # Get what the parquet type will be.
    merged_object_type = recursively_merge_union_types_if_they_are_unions_of_structs(
        object_type
    )
    mapper = mappers_arrow.map_to_arrow(merged_object_type, artifact)
    pyarrow_type = mapper.result_type()

    arrow_obj = recursively_build_pyarrow_array(
        obj, pyarrow_type, mapper, py_objs_already_mapped=py_objs_already_mapped
    )
    return ArrowWeaveList(arrow_obj, merged_object_type, artifact)


def to_arrow(
    obj,
    wb_type=None,
    artifact: typing.Optional[artifact_base.Artifact] = None,
):
    if isinstance(obj, ArrowWeaveList):
        return obj
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifact or artifact_mem.MemArtifact()
    outer_tags: typing.Optional[dict[str, typing.Any]] = None
    if isinstance(wb_type, tagged_value_type.TaggedValueType):
        outer_tags = tag_store.get_tags(obj)
        wb_type = wb_type.value
    if isinstance(wb_type, types.List):
        merged_object_type = (
            recursively_merge_union_types_if_they_are_unions_of_structs(
                wb_type.object_type
            )
        )

        # Convert to arrow, serializing Custom objects to the artifact
        mapper = mappers_arrow.map_to_arrow(merged_object_type, artifact)
        pyarrow_type = arrow_util.arrow_type(mapper.result_type())

        arrow_obj = recursively_build_pyarrow_array(obj, pyarrow_type, mapper)
        weave_obj: ArrowWeaveList = ArrowWeaveList(
            arrow_obj, merged_object_type, artifact
        )

        # Save the weave object to the artifact
        # ref = storage.save(weave_obj, artifact=artifact)
        if outer_tags is not None:
            tag_store.add_tags(weave_obj, outer_tags)

        return weave_obj

    raise errors.WeaveInternalError("to_arrow not implemented for: %s" % obj)


def to_weave_arrow(v: typing.Any):
    awl = to_arrow(v)
    return api.weave(awl)


def to_parquet_friendly(l: ArrowWeaveList) -> ArrowWeaveList:
    def _convert_col_to_parquet_friendly(
        col: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        _, non_none_type = types.split_none(col.object_type)
        if isinstance(non_none_type, types.UnionType):
            full_length_fields = []
            for i in range(len(non_none_type.members)):
                member_field = col._arrow_data.field(i)
                padding = len(col) - len(member_field)
                if padding > 0:
                    member_field = pa.concat_arrays(
                        [member_field, pa.nulls(padding, type=member_field.type)]
                    )
                else:
                    # A case where this can happen:
                    # pa.nulls(1, pa.list_(pa.dense_union([pa.field('a', pa.int32()), pa.field('b', pa.float64())])))
                    # Then union in the list has type_codes and offsets of len zero, but a field
                    # of len one that has the null.
                    member_field = member_field.slice(0, len(col))
                full_length_fields.append(member_field)
            struct = pa.StructArray.from_arrays(
                [col._arrow_data.type_codes, col._arrow_data.offsets]
                + full_length_fields,
                ["type_codes", "offsets"]
                + [str(i) for i in list(range(len(full_length_fields)))],
            )
            return ArrowWeaveList(struct, col.object_type, col._artifact)
        elif isinstance(col.object_type, types.TypedDict):
            if not col.object_type.property_types:
                return ArrowWeaveList(
                    col._arrow_data.is_valid(),
                    col.object_type,
                    col._artifact,
                )
        return None

    with unsafe_awl_construction("to_parquet_friendly"):
        return l.map_column(_convert_col_to_parquet_friendly)


def from_parquet_friendly(l: ArrowWeaveList) -> ArrowWeaveList:
    def _ident(col: ArrowWeaveList, path: PathType) -> typing.Optional[ArrowWeaveList]:
        return None

    def _convert_col_from_parquet_friendly(
        col: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        _, non_none_type = types.split_none(col.object_type)
        if isinstance(non_none_type, types.UnionType):
            struct = col._arrow_data
            type_codes = struct.field("type_codes")
            offsets = struct.field("offsets")
            member_fields = []
            for i in range(len(non_none_type.members)):
                full_length_field = struct.field(str(i))
                mask = pa.compute.equal(type_codes, i).cast(pa.int32())
                masked_offsets = pa.compute.multiply(offsets, mask)
                max_offset = pa.compute.max(masked_offsets).as_py()
                if max_offset is None:
                    max_offset = 0
                else:
                    max_offset += 1

                # TODO: This will hold all the zero memory!
                member_field = full_length_field.slice(0, max_offset)
                member_fields.append(member_field)

            if type_codes.null_count > 0 or offsets.null_count > 0:
                if type_codes.null_count != len(type_codes):
                    # I think this only happens when we have empty objects somewhere
                    # in the tree?
                    raise errors.WeaveInternalError(
                        "Unexpected nulls in type_codes for union"
                    )
                type_codes = type_codes.fill_null(0)
                offsets = offsets.fill_null(0)
                if len(member_fields[0]) == 0:
                    member_fields[0] = pa.nulls(1, member_fields[0].type)
            union = pa.UnionArray.from_dense(
                type_codes.fill_null(0), offsets.fill_null(0), member_fields
            )
            return ArrowWeaveList(union, col.object_type, col._artifact)
        elif isinstance(col.object_type, types.TypedDict):
            if not col.object_type.property_types:
                # Can have nulls because map_columns can put masks on parents in the
                # to_parquet pass.
                valid = col._arrow_data.fill_null(False)
                return ArrowWeaveList(
                    pa.array(
                        [{}] * len(col._arrow_data),
                        mask=pa.compute.invert(valid),
                        type=pa.struct([]),
                    ),
                    col.object_type,
                    col._artifact,
                )
        return None

    return l.map_column(_ident, _convert_col_from_parquet_friendly)


def simple_to_string(arr: pa.Array):
    return pa.compute.binary_join_element_wise(
        "__t_%s" % arr.type.id,
        arr.cast(pa.string()),
        "-",
    )


def to_compare_safe(awl: ArrowWeaveList) -> ArrowWeaveList:
    """Converts any ArrowWeaveList to simple type that pa.compute.equal can compare."""
    from ..ops_domain.wbmedia import ArtifactAssetType

    # Returns a number of string arrow weave list, possibly with Nones
    def _to_compare_safe(
        col: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        if pa.types.is_null(col._arrow_data.type):
            return ArrowWeaveList(
                pa.nulls(len(col), type=pa.string()),
                types.String(),
                None,
            )
        elif pa.types.is_string(col._arrow_data.type):
            return ArrowWeaveList(col._arrow_data, types.String(), None)
        elif pa.types.is_dictionary(col._arrow_data.type):
            if not isinstance(col.object_type, types.String):
                raise errors.WeaveInternalError(
                    "Unexpected dictionary type for non-string type"
                )
            return ArrowWeaveList(col._arrow_data, types.String(), None)
        elif pa.types.is_floating(col._arrow_data.type):
            # Ensure that -0.0 is 0. If we end up converting to a string
            # later (which happens if we have non-numeric types within a union)
            # then -0.0 will be converted to "-0.0" which is not equal to "0.0"
            return ArrowWeaveList(
                pc.choose(pc.equal(col._arrow_data, 0), col._arrow_data, 0),
                types.Number(),
                None,
            )
        elif pa.types.is_integer(col._arrow_data.type):
            return ArrowWeaveList(col._arrow_data, types.Number(), None)
        elif pa.types.is_timestamp(col._arrow_data.type):
            # Cast to int64 and then string. Leaving this as timestamp
            # means it will later be cast directly to string, which is very expensive in
            # pyarrow (1.6s for 500k records v. 0.01s for int64, a 100x improvement)
            return ArrowWeaveList(
                col._arrow_data.cast(pa.int64()).cast(pa.string()), types.String(), None
            )
        elif pa.types.is_boolean(col._arrow_data.type):
            return ArrowWeaveList(col._arrow_data, types.Boolean(), None)
        elif ArtifactAssetType.assign_type(col.object_type):
            # Special logic as implemented in Weave0 for media types that contain sha256
            # checksums.
            # This idea is generalized already in Weave1. Any persistent ref to an artifact
            # is a uniquely comparable string for that object.
            return ArrowWeaveList(col._arrow_data.field("sha256"), types.String(), None)
        elif pa.types.is_struct(col._arrow_data.type):
            value_string_arrs = []
            field_names = sorted(field.name for field in col._arrow_data.type)
            for field_name in field_names:
                value_string_arrs.append(
                    pa.compute.binary_join_element_wise(
                        "__sk_%s" % (field_name),
                        simple_to_string(col._arrow_data.field(field_name)).fill_null(
                            "__none_"
                        ),
                        "_",
                    )
                )
            if not value_string_arrs:
                return ArrowWeaveList(
                    pa.nulls(len(col), type=pa.string()),
                    types.String(),
                    None,
                )
            struct_strings = pa.compute.binary_join_element_wise(
                *value_string_arrs, "-"
            )
            return ArrowWeaveList(
                pa.compute.replace_with_mask(
                    struct_strings,
                    pa.compute.invert(col._arrow_data.is_valid()),
                    pa.nulls(len(col._arrow_data), pa.string()),
                ),
                types.String(),
                None,
            )
        elif pa.types.is_list(col._arrow_data.type):
            stringed_list = pa.ListArray.from_arrays(
                col._arrow_data.offsets,
                simple_to_string(col._arrow_data.values).fill_null("__none_"),
            )
            list_strings = pa.compute.binary_join_element_wise(
                "__list_",
                pa.compute.binary_join(stringed_list, "-"),
                "-",
            )
            res: ArrowWeaveList = ArrowWeaveList(
                pa.compute.replace_with_mask(
                    list_strings,
                    pa.compute.invert(col._arrow_data.is_valid()),
                    pa.nulls(len(col._arrow_data), pa.string()),
                ),
                types.String(),
                None,
            )
            return res
        elif pa.types.is_union(col._arrow_data.type):
            merged = pa.nulls(len(col), pa.string())
            for type_code in range(len(col._arrow_data.type)):
                field = col._arrow_data.field(type_code)
                if len(field) == 0:
                    continue
                string_field = simple_to_string(field)
                mask = pa.compute.equal(col._arrow_data.type_codes, type_code)
                indexes = pa.compute.multiply(
                    mask.cast(pa.int8()), col._arrow_data.offsets
                )
                values = string_field.take(indexes)
                merged = pa.compute.if_else(mask, values, merged)

            return ArrowWeaveList(
                merged,
                types.String(),
                None,
            )
        else:
            raise errors.WeaveInternalError(
                'Unhandled type in "to_compare_safe" %s' % col._arrow_data.type
            )

    return awl.map_column(_to_compare_safe)


def unify_types(*arrs: ArrowWeaveList):
    """Ensures each arr has the same type using merge_types/concat."""
    # We make use of concat, which converts its inputs to the same type.
    if not arrs:
        return ()
    concatted = arrs[0]
    for a in arrs[1:]:
        concatted = concatted.concat(a)
    result = []
    arr_start_index = 0
    for a in arrs:
        result.append(concatted._slice(arr_start_index, arr_start_index + len(a)))
        arr_start_index += len(a)
    return result
