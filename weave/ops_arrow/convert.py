import pyarrow as pa
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

from .arrow import ArrowWeaveListType
from .list_ import ArrowWeaveList


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
    pyarrow_type: pa.DataType,
    mapper,
    py_objs_already_mapped: bool = False,
) -> pa.Array:
    arrays: list[pa.Array] = []

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
            ),
        )

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
            if isinstance(
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

    if py_objs_already_mapped:
        return pa.array(py_objs, pyarrow_type)

    arrays = [mapper.apply(o) if o is not None else None for o in py_objs]
    return pa.array(arrays, pyarrow_type)


# This will be a faster version fo to_arrow (below). Its
# used in op file-table, to convert from a wandb Table to Weave
# (that code is very experimental and not totally working yet)
def to_arrow_from_list_and_artifact(
    obj: typing.Any, object_type: types.Type, artifact: artifact_base.Artifact
) -> ArrowWeaveList:
    # Get what the parquet type will be.
    merged_object_type = recursively_merge_union_types_if_they_are_unions_of_structs(
        object_type
    )
    mapper = mappers_arrow.map_to_arrow(merged_object_type, artifact)
    pyarrow_type = mapper.result_type()

    arrow_obj = recursively_build_pyarrow_array(
        obj, pyarrow_type, mapper, py_objs_already_mapped=False
    )
    return ArrowWeaveList(arrow_obj, merged_object_type, artifact)


def to_arrow(obj, wb_type=None):
    if isinstance(obj, ArrowWeaveList):
        return obj
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifact_mem.MemArtifact()
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
        weave_obj = ArrowWeaveList(arrow_obj, merged_object_type, artifact)

        # Save the weave object to the artifact
        # ref = storage.save(weave_obj, artifact=artifact)
        if outer_tags is not None:
            tag_store.add_tags(weave_obj, outer_tags)

        return weave_obj

    raise errors.WeaveInternalError("to_arrow not implemented for: %s" % obj)


def to_weave_arrow(v: typing.Any):
    awl = to_arrow(v)
    return api.weave(awl)
