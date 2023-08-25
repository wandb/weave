import dataclasses
import json
import pyarrow as pa
import numpy as np
from pyarrow import compute as pc
import pyarrow.parquet as pq
import pyarrow.feather as pf
import typing
import textwrap

py_type = type

from .. import partial_object
from .. import weave_types as types
from .. import errors
from .. import artifact_fs


def arrow_type_to_weave_type(pa_type: pa.DataType) -> types.Type:
    if pa_type == pa.null():
        return types.NoneType()
    elif pa.types.is_dictionary(pa_type):
        return arrow_type_to_weave_type(pa_type.value_type)
    elif pa_type == pa.string():
        return types.String()
    elif pa_type == pa.large_string():
        return types.String()
    elif pa_type == pa.int64() or pa_type == pa.int32():
        return types.Int()
    elif pa_type in [pa.float64(), pa.float32(), pa.float16()]:
        return types.Float()
    elif pa_type == pa.bool_():
        return types.Boolean()
    elif pa.types.is_temporal(pa_type):
        return types.Timestamp()
    elif pa.types.is_binary(pa_type):
        return types.Bytes()
    elif pa.types.is_list(pa_type):
        return types.List(arrow_field_to_weave_type(pa_type.value_field))
    elif pa.types.is_struct(pa_type):
        return types.TypedDict({f.name: arrow_field_to_weave_type(f) for f in pa_type})
    elif pa.types.is_union(pa_type):
        return types.UnionType(*[arrow_type_to_weave_type(f.type) for f in pa_type])
    raise errors.WeaveTypeError(
        "Type conversion not implemented for arrow type: %s" % pa_type
    )


def arrow_field_to_weave_type(pa_field: pa.Field) -> types.Type:
    t = arrow_type_to_weave_type(pa_field.type)
    if pa_field.nullable:
        return types.optional(t)
    return t


def arrow_schema_to_weave_type(schema) -> types.Type:
    return types.TypedDict({f.name: arrow_field_to_weave_type(f) for f in schema})


@dataclasses.dataclass(frozen=True)
class ArrowArrayType(types.Type):
    instance_classes = [pa.ChunkedArray, pa.ExtensionArray, pa.Array]
    name = "ArrowArray"

    object_type: types.Type = types.Any()
    UNION_PREFIX = "__weave_union"
    UNION_TO_STRUCT_TYPE_CODE_COLNAME = "__weave_type_code"
    EMPTY_STRUCT_DUMMY_FIELD_NAME = "__weave_empty_struct"

    @classmethod
    def type_of_instance(cls, obj: pa.Array):
        return cls(arrow_type_to_weave_type(obj.type))

    def save_instance(self, obj, artifact, name):
        table = pa.table({"arr": obj})
        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(table, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.parquet", binary=True) as f:
            deserialized = pq.read_table(f)
            deserialized = deserialized["arr"].combine_chunks()
            return deserialized


@dataclasses.dataclass(frozen=True)
class ArrowTableType(types.Type):
    instance_classes = pa.Table
    name = "ArrowTable"

    object_type: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj: pa.Table):
        return cls(arrow_schema_to_weave_type(obj.schema))

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.parquet", binary=True) as f:
            return pq.read_table(f)


# This function is evil and breaks performance because of the dictionary_decode
# call. Don't use it. TODO: remove all calls
def arrow_as_array(obj) -> pa.Array:
    # assumes obj is table or array
    if isinstance(obj, pa.Table):
        return pa.StructArray.from_arrays(
            # TODO: we shouldn't need to combine chunks, we can produce this in the
            # original chunked form for zero copy
            [c.combine_chunks() for c in obj.columns],
            names=obj.column_names,
        )
    elif isinstance(obj, pa.ChunkedArray):
        return obj.combine_chunks()
    elif isinstance(obj, pa.DictionaryArray):
        return arrow_as_array(obj.dictionary_decode())
    elif not isinstance(obj, pa.Array):
        raise TypeError("Expected pyarrow Array or Table, got %s" % type(obj))
    return obj


def offsets_starting_at_zero(arr: pa.ListArray) -> pa.IntegerArray:
    """
    We often have code to operate on the elements of a list array. That code
    will do something like:
    ```
        offsets = arr.offsets
        elements = arr.flatten()
        transformed = do_something(elements)
        result = pa.ListArray.from_arrays(offsets, transformed)
    ```
    However, sometimes for performance reasons, the offsets do not start at 0.
    For example, when the ListArray is actually a slice of a larger underlying
    buffer. We should use this helper function anytime we are doing something
    like the above example.
    """
    raw_offsets = arr.offsets
    if len(raw_offsets) == 0:
        return raw_offsets
    first_value = raw_offsets[0]
    if first_value == 0:
        return raw_offsets
    else:
        return pc.subtract(raw_offsets, first_value)


@dataclasses.dataclass(frozen=True)
class ArrowWeaveListType(types.Type):
    _base_type = types.List
    name = "ArrowWeaveList"

    object_type: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.object_type)

    def save_instance(self, obj, artifact, name):
        # rewriting refs is disabled after a refactor. We need this to work
        # for media and caching with local artifacts to work. But we don't need
        # it for W&B production for weave0 use cases.
        # TODO: fix this

        # If we are saving to the same artifact as we were written to,
        # then we don't need to rewrite any references.

        # if obj._artifact == artifact:
        #     arrow_data = obj._arrow_data
        # else:
        #     # super().save_instance(obj, artifact, name)
        #     # return
        #     arrow_data = rewrite_weavelist_refs(
        #         obj._arrow_data, obj.object_type, obj._artifact, artifact
        #     )
        if not obj._artifact == artifact:
            # somehow we still need this block of code to get the test passing,
            # even though we don't use its result.
            rewrite_weavelist_refs(
                obj._arrow_data, obj.object_type, obj._artifact, artifact
            )

        # v1 AWL format
        # from . import convert

        # parquet_friendly = convert.to_parquet_friendly(obj)
        # table = pa.table({"arr": parquet_friendly._arrow_data})
        # with artifact.new_file(f"{name}.ArrowWeaveList.parquet", binary=True) as f:
        #     pq.write_table(table, f)

        # v2 AWL format
        # - if it's a top-level typeddict we don't save in nested sub-array.
        #   reading specific columns from a parquet or feather file only gives a perf
        #   improvement for top-level columns.
        # - saved as feather file instead of parquet. There are some issues in our
        #   to/from parquet conversion with unions. They can be triggered by using
        #   v1 format with the hypothesis tests.
        artifact.metadata["_weave_awl_format"] = 2
        if isinstance(obj.object_type, types.TypedDict):
            arrow_data = obj._arrow_data
            if not obj.object_type.property_types:
                arrow_data = pa.StructArray.from_arrays(
                    [pa.nulls(len(arrow_data))], names=["_dummy"]
                )
            table = pa.Table.from_arrays(
                [arrow_data.field(i) for i in range(len(arrow_data.type))],
                names=[f.name for f in arrow_data.type],
            )
        else:
            table = pa.table({"arr": obj._arrow_data})
        with artifact.new_file(f"{name}.ArrowWeaveList.feather", binary=True) as f:
            pf.write_feather(table, f)

        with artifact.new_file(f"{name}.ArrowWeaveList.type.json") as f:
            json.dump(obj.object_type.to_dict(), f)

    def load_instance(
        self, artifact: artifact_fs.FilesystemArtifact, name: str, extra=None
    ):
        with artifact.open(f"{name}.ArrowWeaveList.type.json") as f:
            object_type = json.load(f)
            object_type = types.TypeRegistry.type_from_dict(object_type)
        from . import list_

        if "_weave_awl_format" not in artifact.metadata:
            # v1 AWL format
            with artifact.open(f"{name}.ArrowWeaveList.parquet", binary=True) as f:
                table = pq.read_table(f)
            arr = table["arr"].combine_chunks()
            with list_.unsafe_awl_construction("load_from_parquet"):
                l = self.instance_class(arr, object_type=object_type, artifact=artifact)  # type: ignore
                from . import convert

                res = convert.from_parquet_friendly(l)
        elif artifact.metadata["_weave_awl_format"] == 2:
            # v2 AWL format
            with artifact.open(f"{name}.ArrowWeaveList.feather", binary=True) as f:
                table = pf.read_table(f)
            if isinstance(object_type, types.TypedDict):
                if not object_type.property_types:
                    arr = pa.repeat({}, len(table))
                else:
                    arr = pa.StructArray.from_arrays(
                        [table[i].combine_chunks() for i in range(len(table.schema))],
                        names=[f.name for f in table.schema],
                    )
            else:
                arr = table["arr"].combine_chunks()
            res = self.instance_class(arr, object_type=object_type, artifact=artifact)  # type: ignore
        else:
            raise ValueError(
                f"Unknown _weave_awl_format {artifact.metadata['_weave_awl_format']}"
            )

        res.validate()
        return res


def rewrite_weavelist_refs(arrow_data, object_type, source_artifact, target_artifact):
    if isinstance(object_type, partial_object.PartialObjectType):
        # PartialObject is a leaf type
        return arrow_data
    if _object_type_has_props(object_type):
        prop_types = _object_type_prop_types(object_type)

        # handle empty struct case - the case where the struct has no fields
        if len(prop_types) == 0:
            return arrow_data

        if isinstance(arrow_data, pa.Table):
            arrays = {}
            for col_name, col_type in prop_types.items():
                column = arrow_data[col_name]
                arrays[col_name] = rewrite_weavelist_refs(
                    column, col_type, source_artifact, target_artifact
                )
            return pa.table(arrays)
        elif isinstance(arrow_data, pa.ChunkedArray):
            arrays = {}
            unchunked = arrow_data.combine_chunks()
            for col_name, col_type in prop_types.items():
                column = unchunked.field(col_name)
                arrays[col_name] = rewrite_weavelist_refs(
                    column, col_type, source_artifact, target_artifact
                )
            return pa.StructArray.from_arrays(
                arrays.values(), names=arrays.keys(), mask=pa.compute.is_null(unchunked)
            )
        elif isinstance(arrow_data, pa.StructArray):
            arrays = {}
            for col_name, col_type in prop_types.items():
                column = arrow_data.field(col_name)
                arrays[col_name] = rewrite_weavelist_refs(
                    column, col_type, source_artifact, target_artifact
                )
            return pa.StructArray.from_arrays(
                arrays.values(),
                names=arrays.keys(),
                mask=pa.compute.is_null(arrow_data),
            )
        elif isinstance(arrow_data, pa.NullArray):
            return arrow_data
        else:
            raise errors.WeaveTypeError('Unhandled type "%s"' % type(arrow_data))
    elif isinstance(object_type, types.UnionType):
        non_none_members = [
            m for m in object_type.members if not isinstance(m, types.NoneType)
        ]
        nullable = len(non_none_members) < len(object_type.members)
        if len(non_none_members) > 1:
            arrow_data = arrow_as_array(arrow_data)
            if not isinstance(arrow_data.type, pa.UnionType):
                raise errors.WeaveTypeError(
                    "Expected UnionType, got %s" % type(arrow_data.type)
                )
            arrays = []
            for i, _ in enumerate(arrow_data.type):
                rewritten = rewrite_weavelist_refs(
                    arrow_data.field(i),
                    non_none_members[i]
                    if not nullable
                    else types.UnionType(types.NoneType(), non_none_members[i]),
                    source_artifact,
                    target_artifact,
                )
                arrays.append(rewritten)
            return pa.UnionArray.from_dense(
                arrow_data.type_codes, arrow_data.offsets, arrays
            )
        return rewrite_weavelist_refs(
            arrow_data, types.non_none(object_type), source_artifact, target_artifact
        )
    elif _object_type_is_basic(object_type):
        return arrow_data
    elif isinstance(object_type, (types.List, ArrowWeaveListType)):
        data = arrow_data
        if isinstance(arrow_data, pa.ChunkedArray):
            data = arrow_data.combine_chunks()
        return pa.ListArray.from_arrays(
            offsets_starting_at_zero(data),
            rewrite_weavelist_refs(
                data.flatten(),
                object_type.object_type,
                source_artifact,
                target_artifact,
            ),
            mask=pa.compute.is_null(data),
        )
    else:
        # We have a column of refs
        new_refs = []
        for ref_str in arrow_data:
            ref_str = ref_str.as_py()
            new_refs.append(
                _rewrite_ref_for_save(
                    ref_str, object_type, source_artifact, target_artifact
                )
                if ref_str is not None
                else None
            )
        return pa.array(new_refs)


def _object_type_has_props(object_type):
    from ..language_features.tagging import tagged_value_type

    return (
        isinstance(object_type, types.TypedDict)
        or isinstance(object_type, types.ObjectType)
        or isinstance(object_type, tagged_value_type.TaggedValueType)
    )


def _object_type_prop_types(object_type):
    from ..language_features.tagging import tagged_value_type

    if isinstance(object_type, tagged_value_type.TaggedValueType):
        return {
            "_tag": object_type.tag,
            "_value": object_type.value,
        }
    prop_types = object_type.property_types
    if callable(prop_types):
        prop_types = prop_types()
    return prop_types


def _object_type_is_basic(object_type):
    if isinstance(object_type, types.Const):
        object_type = object_type.val_type
    return isinstance(object_type, types.BasicType) or (
        isinstance(object_type, types.Timestamp)
    )


def _rewrite_ref_for_save(entry: str, object_type, source_artifact, target_artifact):
    # TODO: This should be simpler. We take a ref string, which may be absolute or
    # relative, and want to ensure the object is referencable from the target_artifact.
    # This function should be written in those terms.
    if ":" in entry:
        # Already a URI
        return entry

    if isinstance(source_artifact, artifact_fs.FilesystemArtifact):
        # Our source is an artifact, construct a full URI.
        return str(source_artifact.ref_from_local_str(entry, object_type).uri)

    # Source is ObjLookupMem, save to the artifact
    return target_artifact.set(
        entry, object_type, source_artifact.get(entry, object_type)
    ).local_ref_str()


def pretty_print_arrow_type(t: typing.Union[pa.Schema, pa.DataType, pa.Field]) -> str:
    if isinstance(t, pa.Schema):
        return "Schema:\n" + textwrap.indent(
            "\n".join(pretty_print_arrow_type(f) for f in t), "  "
        )
    elif isinstance(t, pa.Field):
        return f"{t.name}: {'nullable' if t.nullable else 'non-null'} {pretty_print_arrow_type(t.type)}"

    if isinstance(t, pa.StructType):
        return "Struct:\n" + textwrap.indent(
            "\n".join(pretty_print_arrow_type(f) for f in t), "  "
        )

    elif isinstance(t, pa.ListType):
        return "List\n" + textwrap.indent(pretty_print_arrow_type(t.value_type), "  ")

    elif isinstance(t, pa.UnionType):
        return "Union:\n" + textwrap.indent(
            "\n".join(pretty_print_arrow_type(f) for f in t), "  "
        )

    return str(t)


def union_is_null(arr: pa.Array):
    # pyarrow doesn't support is_null on unions. We do it ourselves
    # by checking each child entry for whether its null. This code
    # is vectorized so still fast.
    merged = pa.nulls(len(arr), pa.bool_())
    for type_code in range(len(arr.type)):
        field = pa.compute.is_null(arr.field(type_code))
        if len(field) == 0:
            continue
        mask = pa.compute.equal(arr.type_codes, type_code)
        indexes = pa.compute.multiply(mask.cast(pa.int8()), arr.offsets)
        values = field.take(indexes)
        merged = pa.compute.if_else(mask, values, merged)
    return merged


def safe_is_null(arr: pa.Array):
    # is_null that also handles unions correctly since pyarrow doesn't.
    if isinstance(arr.type, pa.UnionType):
        return union_is_null(arr)
    else:
        return pa.compute.is_null(arr)


def safe_coalesce(*arrs: pa.Array):
    if not arrs:
        raise ValueError("coalesce requires at least one argument")
    # pyarrows coalesce doesn't handle unions. This does!
    if len(arrs[0]) == 0:
        return arrs[0]
    result = arrs[0]
    for arr in arrs[1:]:
        result = pa.compute.if_else(safe_is_null(result), arr, result)
    return result


def arrow_zip(*arrs: pa.Array) -> pa.Array:
    n_arrs = len(arrs)
    output_len = min(len(a) for a in arrs)
    array_indexes = np.tile(np.arange(n_arrs, dtype="int64"), output_len)
    item_indexes = np.floor(np.arange(0, output_len, 1.0 / n_arrs)).astype("int64")
    indexes = item_indexes + array_indexes * output_len
    concatted = pa.concat_arrays(arrs)
    interleaved = concatted.take(indexes)
    offsets = np.arange(0, len(interleaved) + len(arrs), len(arrs), dtype="int64")
    return pa.ListArray.from_arrays(offsets, interleaved)
