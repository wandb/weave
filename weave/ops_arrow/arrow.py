import dataclasses
import json
import pyarrow as pa
from pyarrow import compute as pc
import pyarrow.parquet as pq
import typing

py_type = type

from .. import mappers_python
from .. import weave_types as types
from .. import errors
from .. import artifact_fs


def is_dense_union(array: pa.Array) -> bool:
    return pa.types.is_union(array.type) and array.type.mode == "dense"


def dense_union_to_sparse_union(array: pa.Array) -> pa.Array:
    if not pa.types.is_union(array.type):
        raise ValueError(f"Expected UnionArray, got {type(array)}")
    if array.type.mode != "dense":
        raise ValueError(f"Expected dense UnionArray, got {array.type.mode}")

    type_codes = array.type_codes
    arrays = []

    for field_index, field in enumerate(array.type):
        # convert dense representation to sparse representation
        value_array = array.field(field_index)
        mask = pc.equal(type_codes, pa.scalar(field_index, type=pa.int8()))
        offsets_for_type = pc.filter(offsets_starting_at_zero(array), mask)
        replacements = pc.take(value_array, offsets_for_type)
        empty_array = pa.nulls(len(array), type=field.type)
        result = safe_replace_with_mask(empty_array, mask, replacements)
        arrays.append(result)

    return pa.UnionArray.from_sparse(
        type_codes,
        arrays,
    )


def safe_replace_with_mask(
    array: pa.Array, mask: pa.Array, replacements: pa.Array
) -> pa.Array:
    if array.type != replacements.type:
        raise errors.WeaveInternalError(
            f"Expected array and replacements to have the same type, got {array.type} and {replacements.type}"
        )

    if pa.types.is_struct(array.type):
        if array.type.num_fields == 0:
            return array
        arrays = []
        names = []
        for field_index, field in enumerate(array.type):
            value_array = array.field(field_index)
            replacement_array = replacements.field(field_index)
            result = safe_replace_with_mask(value_array, mask, replacement_array)
            arrays.append(result)
            names.append(field.name)

        return pa.StructArray.from_arrays(
            arrays,
            names,
            mask=pc.replace_with_mask(
                pa.compute.invert(array.is_valid()),
                mask,
                pa.compute.invert(replacements.is_valid()),
            ),
        )
    elif pa.types.is_list(array.type):
        # Note: this is admittedly not efficient, but there does not seem to be
        # a better alternative. Basically, `pc.replace_with_mask` does not work
        # on list arrays. There are a number of problems:
        # 1. Calling `flatten` on a list array drops the nulls.
        # 2. In order to enter another level of recursion with
        # `safe_replace_with_mask`, we would need to create a new mask, value,
        # and replacement array. The value and mask arrays cannot be correctly
        # created with pure pyarrow functions and require looping over every sub
        # element in the lists. Unless that can be solved, then this single loop
        # over the outer list is the best we can do.
        final_arr = []
        replacement_ndx = 0
        for i in range(len(array)):
            if mask[i].as_py():
                final_arr.append(replacements[replacement_ndx].as_py())
                replacement_ndx += 1
            else:
                final_arr.append(array[i].as_py())
        return pa.array(final_arr, type=array.type)

        # Note: Danny had commented that the above implementation would fail in
        # the case that array.type is a dense union. This is true - see
        # https://github.com/wandb/weave-internal/pull/542/files#r1100703368.
        #
        # A test commented out test case is provided in `test_safe_replace_with_mask`
        # which stresses this.
        #
        # In particular, it would need to follow something like this logic
        # (which is pretty challenging to implement and likely requires visiting
        # every single value!):
        #
        #
        # array: ListArray<T> - length L
        # replacements - ListArray<T> - length R
        # mask: BooleanArray - length L (R number of True values)
        #
        # flattened_array: (assuming [3,3])
        # [0_0, 0_1, 0_2, 1_0, 1_1, 1_2, 2_0, 2_1, 2_2]
        #  |-----L0-----| |-----L1-----| |-----L2-----|
        #
        # flattened_mask:
        # [0_B, 0_B, 0_B, 1_B, 1_B, 1_B, 2_B, 2_B, 2_B]
        #  |-----L0-----| |-----L1-----| |-----L2-----|
        #
        # flattened_replacements: (assuming (2,2))
        # [0_0, 0_1, 1_0, 1_1]
        #  |--R0--| |--R1---|
        #
        # Now, let's assume the mask is [True, False, True],
        #
        # Then we want to replace the first and third list in the original array,
        # so the mask needs to be:
        # [True, True, False, False, False, True, True]
        #  |--M0--|    |-------M1-------|   |--M2--|
        #
        # Notice that the expanded values of the masks are not always the same length - they
        # take the length of the original list if False, and the length of the replacement list
        # if True. But since our masks and array need to be the same length, the true flattened
        # array needs to be something like:
        # [None, None, 1_0, 1_1, 1_2, None, None]
        #  |--L0--|    |-----L1----|   |-L2---|
        #
        # Where the masked entries are turned into None values of length R#!
        #
        #
        # Similarly, the offsets are also a bit odd:
        #
        # flattened_offsets:
        # [0, 2, 5, 7]
        #
        #
        # These offsets need to be derived from the mask, and offsets of both the original
        # and replacement arrays.
        #
        #
        # array_offsets:
        # [0, 3, 6, 9]
        #
        # replacement_offsets:
        # [0, 2, 4]
        #
        # So to calculate the offsets, we basically need to do a cumulative sum, shifting
        # between the different offsets depending on the value of the mask. so:
        #
        # step 1: - each entry is the length of the inner list corresponding to that
        #           index in either either the original or replacement array if the mask
        #           is False or True respectively:
        # [0, 2, 3, 2]
        #
        # step 2: cumulative sum:
        # [0, 2, 5, 7]
        #
        #
        # So, our final calculated vars are:
        #
        # flattened_modified_array = [None, None, 1_0, 1_1, 1_2, None, None]
        # flattened_mask           = [True, True, False, False, False, True, True]
        # flattened_offsets        = [0, 2, 5, 7]
        # flattened_replacements   = [0_0, 0_1, 1_0, 1_1]
        #
        # new_replaced = safe_replace_with_mask(flattened_modified_array, flattened_mask, flattened_replacements)
        # return pa.ListArray.from_arrays(flattened_offsets, new_replaced)
    elif pa.types.is_union(array.type):
        if is_dense_union(array):
            sparse_array = dense_union_to_sparse_union(array)
        else:
            sparse_array = array

        if is_dense_union(replacements):
            sparse_replacements = dense_union_to_sparse_union(replacements)
        else:
            sparse_replacements = replacements

        new_arrays = []
        for f_ndx in range(sparse_array.type.num_fields):
            array_field = sparse_array.field(f_ndx)
            replacement_field = sparse_replacements.field(f_ndx)
            new_arrays.append(
                safe_replace_with_mask(array_field, mask, replacement_field)
            )
        sparse_replaced = pa.UnionArray.from_sparse(sparse_array.type_codes, new_arrays)

        if is_dense_union(array):
            return sparse_union_to_dense_union(sparse_replaced)
        else:
            return sparse_replaced
    elif pa.types.is_null(array.type) and pa.types.is_null(replacements.type):
        return array
    elif pa.types.is_null(array.type):
        return pc.replace_with_mask(array.cast(replacements.type), mask, replacements)
    elif pa.types.is_null(replacements.type):
        return pc.replace_with_mask(array, mask, replacements.cast(array.type))

    return pc.replace_with_mask(array, mask, replacements)


def fallback_dictionary_encode(array: pa.Array) -> pa.DictionaryArray:
    """Dictionary encoding not implemented for this type, need to break out to python."""
    pydata = array.to_pylist()

    # we need to json encode because dicts and lists are not hashable, but we need them to be
    json_encoded = [json.dumps(v) for v in pydata]
    unique_values_json = list(set(json_encoded))
    unique_values = [json.loads(v) for v in unique_values_json]

    indices = [unique_values_json.index(v) for v in json_encoded]
    indices_array = pa.array(indices, type=pa.int32())
    unique_values_array = pa.array(unique_values)
    return pa.DictionaryArray.from_arrays(indices_array, unique_values_array)


def sparse_union_to_dense_union(array: pa.Array) -> pa.Array:
    if not pa.types.is_union(array.type):
        raise ValueError(f"Expected UnionArray, got {type(array)}")
    if array.type.mode != "sparse":
        raise ValueError(f"Expected sparse UnionArray, got {array.type.mode}")

    type_codes = array.type_codes
    arrays: list[pa.Array] = []
    offsets_for_each_type: list[pa.Array] = []
    mask_for_each_type: list[pa.Array] = []

    for field_index, _ in enumerate(array.type):
        # convert sparse representation to dense representation

        # looks like [None, 1, None, 3, 4, None]
        value_array = array.field(field_index)

        mask_for_type = pc.equal(type_codes, pa.scalar(field_index, type=pa.int8()))

        # dictionary encode it to get offsets and values array
        try:
            value_array_encoded = value_array.dictionary_encode(null_encoding="encode")
        except pa.ArrowNotImplementedError:
            # dictionary encoding not implemented for this type, need to break out to python.
            value_array_encoded = fallback_dictionary_encode(value_array)

        offsets_for_type = pc.filter(value_array_encoded.indices, mask_for_type)
        unique_values_for_type = value_array_encoded.dictionary

        arrays.append(unique_values_for_type)
        offsets_for_each_type.append(offsets_for_type)
        mask_for_each_type.append(mask_for_type)

    # merge offsets for each type together into a single offsets array
    combined_offsets_array = pa.nulls(len(array), type=pa.int32())
    for offset, mask in zip(offsets_for_each_type, mask_for_each_type):
        combined_offsets_array = safe_replace_with_mask(
            combined_offsets_array, mask, offset
        )

    return pa.UnionArray.from_dense(
        type_codes,
        combined_offsets_array,
        arrays,
    )


def arrow_type_to_weave_type(pa_type: pa.DataType) -> types.Type:
    if pa_type == pa.null():
        return types.NoneType()
    elif pa.types.is_dictionary(pa_type):
        return arrow_type_to_weave_type(pa_type.value_type)
    elif pa_type == pa.string():
        return types.String()
    elif pa_type == pa.int64() or pa_type == pa.int32():
        return types.Int()
    elif pa_type in [pa.float64(), pa.float32(), pa.float16()]:
        return types.Float()
    elif pa_type == pa.bool_():
        return types.Boolean()
    elif pa.types.is_temporal(pa_type):
        return types.Timestamp()
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


def adjust_table_after_parquet_deserialization(table: pa.Table) -> pa.Table:
    def convert_struct_to_union_and_nullify_dummy_empty_structs(
        column: pa.ChunkedArray, column_name: str
    ) -> tuple[str, pa.ChunkedArray]:

        if column_name.startswith(ArrowArrayType.UNION_PREFIX):
            # we have a union field
            # As of pyarrow 10.0.1 there seems to be a bug with constructing a Union array
            # from a sub-chunk of a chunked array. from_sparse fails with a size mismatch
            # error. That function thinks the last chunk size is the size of the whole
            # chunked array. So we combine chunks here.
            a = column.combine_chunks()
            arrays = []
            type_code_array: typing.Optional[pa.Array] = None

            for field in a.type:
                if field.name == ArrowArrayType.UNION_TO_STRUCT_TYPE_CODE_COLNAME:
                    type_code_array = a.field(
                        ArrowArrayType.UNION_TO_STRUCT_TYPE_CODE_COLNAME
                    )
                else:
                    arrays.append(a.field(field.name))
            if type_code_array is None:
                raise errors.WeaveTypeError(
                    "Expected struct array with type code field"
                )
            if len(type_code_array) == type_code_array.null_count:
                # Nulls should only be in the type code array in the specific
                # instance that this entire column is null. If any entry is not
                # null, then the type code for the null elements will be the
                # first null type code in the union. However, in the case that
                # everything is null, then the entire block is nulled out. Here
                # we can just use the first type code in the union as the type
                # code for the entire column.  This is because our serialization
                # side correctly applies the mask to this union column. When
                # pyarrow can represent nulls using one of the type codes, then
                # the mask will always be all true, even if there are nulls.
                # However, if the entire thing is null, payarrow's mask is false
                # for the whole column.
                type_code_array = pc.fill_null(type_code_array, 0)
            sparse = pa.UnionArray.from_sparse(type_code_array, arrays)
            new_col = sparse_union_to_dense_union(sparse)
            column_name = column_name[len(ArrowArrayType.UNION_PREFIX) :]
            return column_name, pa.chunked_array([new_col])

        elif pa.types.is_struct(column.type):
            new_col = []

            if (
                len(column.type) == 1
                and column.type[0].name == ArrowArrayType.EMPTY_STRUCT_DUMMY_FIELD_NAME
            ):
                # serialized representation of empty struct,
                for a in column.chunks:

                    def empty_struct_generator():
                        for _ in range(len(a)):
                            yield {}

                    new_col.append(
                        pa.array(
                            empty_struct_generator(),
                            mask=pa.compute.invert(a.is_valid()),
                        )
                    )
            else:

                # we have a struct field - recurse it and convert all subfields to unions where applicable

                for a in column.chunks:
                    arrays = []
                    names = []
                    for field in a.type:
                        (
                            name,
                            array,
                        ) = convert_struct_to_union_and_nullify_dummy_empty_structs(
                            pa.chunked_array(a.field(field.name)), field.name
                        )

                        arrays.append(array.combine_chunks())
                        names.append(name)
                    new_col.append(
                        pa.StructArray.from_arrays(
                            arrays, names, mask=pa.compute.is_null(a)
                        )
                    )
            return column_name, pa.chunked_array(new_col)

        elif pa.types.is_list(column.type):
            new_col = []
            for a in column.chunks:
                (
                    name,
                    array,
                ) = convert_struct_to_union_and_nullify_dummy_empty_structs(
                    pa.chunked_array(a.flatten()), column.type.value_field.name
                )
                new_col.append(
                    pa.ListArray.from_arrays(
                        offsets_starting_at_zero(a),
                        array.combine_chunks(),
                        mask=pa.compute.is_null(a),
                        type=pa.list_(pa.field(name, array.type)),
                    )
                )
            return column_name, pa.chunked_array(new_col)

        else:
            # we have a regular field
            return column_name, column

    for i, column_name in enumerate(table.column_names):
        current_column = table[column_name]
        new_name, new_column = convert_struct_to_union_and_nullify_dummy_empty_structs(
            current_column, column_name
        )
        if new_column is not current_column:
            table = table.remove_column(i)
            table = table.add_column(i, new_name, new_column)

    return table


def adjust_table_for_parquet_serialization(table: pa.Table) -> pa.Table:
    def recursively_convert_unions_to_structs_and_impute_empty_structs(
        column: pa.ChunkedArray, column_name: str
    ) -> tuple[str, pa.ChunkedArray]:

        if pa.types.is_union(column.type):
            new_col = []
            for a in column.chunks:
                if isinstance(a, pa.UnionArray):
                    # a is a dense union, we need sparse here
                    a = dense_union_to_sparse_union(a)

                    arrays = []
                    names = []
                    for i, field in enumerate(a.type):
                        arrays.append(a.field(i))
                        names.append(field.name)

                    arrays.append(a.type_codes)
                    names.append(ArrowArrayType.UNION_TO_STRUCT_TYPE_CODE_COLNAME)

                    new_col.append(pa.StructArray.from_arrays(arrays, names))

            column = pa.chunked_array(new_col)
            column_name = ArrowArrayType.UNION_PREFIX + column_name

        if pa.types.is_struct(column.type):
            new_col = []

            if len(column.type) == 0:
                # empty struct, add dummy field so we can serialize to parquet
                # (parquet does not support empty structs)
                for a in column.chunks:
                    dummy_values = [""]
                    indices = []
                    for i in range(len(a)):
                        indices.append(0)
                    dummy_array = pa.DictionaryArray.from_arrays(
                        pa.array(indices, pa.int32()), pa.array(dummy_values)
                    )
                    new_col.append(
                        pa.StructArray.from_arrays(
                            [dummy_array],
                            [ArrowArrayType.EMPTY_STRUCT_DUMMY_FIELD_NAME],
                            mask=pa.compute.invert(a.is_valid()),
                        )
                    )

            else:
                for a in column.chunks:
                    names = []
                    arrays = []
                    for field in a.type:
                        (
                            new_name,
                            chunked_array,
                        ) = recursively_convert_unions_to_structs_and_impute_empty_structs(
                            pa.chunked_array(a.field(field.name)), field.name
                        )
                        names.append(new_name)
                        arrays.append(chunked_array.combine_chunks())

                    new_col.append(
                        pa.StructArray.from_arrays(
                            arrays, names, mask=pa.compute.invert(a.is_valid())
                        )
                    )
            column = pa.chunked_array(new_col)

        if pa.types.is_list(column.type):
            new_col = []
            for a in column.chunks:
                (
                    new_name,
                    chunked_array,
                ) = recursively_convert_unions_to_structs_and_impute_empty_structs(
                    pa.chunked_array(a.flatten()), column.type.value_field.name
                )
                new_col.append(
                    pa.ListArray.from_arrays(
                        offsets_starting_at_zero(a),
                        chunked_array.combine_chunks(),
                        mask=pa.compute.invert(a.is_valid()),
                        type=pa.list_(pa.field(new_name, chunked_array.type)),
                    )
                )

            column = pa.chunked_array(new_col)

        return column_name, column

    for i, column_name in enumerate(table.column_names):
        current_column = table[column_name]
        (
            new_name,
            new_column,
        ) = recursively_convert_unions_to_structs_and_impute_empty_structs(
            current_column, column_name
        )
        if new_column is not current_column:
            table = table.remove_column(i)
            table = table.add_column(i, new_name, new_column)

    return table


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
        # Could use the arrow format instead. I think it supports memory
        # mapped random access, but is probably larger.
        # See here: https://arrow.apache.org/cookbook/py/io.html#saving-arrow-arrays-to-disk
        # TODO: what do we want?

        table = pa.table({"arr": obj})
        # convert unions to structs. parquet does not know how to serialize arrow unions, so
        # we store them in a struct format that we convert back to a union on deserialization

        table = adjust_table_for_parquet_serialization(table)

        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(table, f)

    def load_instance(self, artifact, name, extra=None):

        with artifact.open(f"{name}.parquet", binary=True) as f:
            deserialized = pq.read_table(f)

            # convert struct to union. parquet does not know how to serialize arrow unions, so
            # we store them in a struct format
            deserialized = adjust_table_after_parquet_deserialization(deserialized)
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
        # If we are saving to the same artifact as we were written to,
        # then we don't need to rewrite any references.
        if obj._artifact == artifact:
            arrow_data = obj._arrow_data
        else:
            # super().save_instance(obj, artifact, name)
            # return
            arrow_data = rewrite_weavelist_refs(
                obj._arrow_data, obj.object_type, obj._artifact, artifact
            )

        d = {"_arrow_data": arrow_data, "object_type": obj.object_type}
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(ArrowTableType(), ArrowArrayType()),
                "object_type": types.TypeType(),
            }
        )
        if hasattr(self, "_key"):
            d["_key"] = obj._key
            type_of_d.property_types["_key"] = self._key

        serializer = mappers_python.map_to_python(type_of_d, artifact, path=[name])
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.ArrowWeaveList.json") as f:
            json.dump(result_d, f)

    def load_instance(
        self, artifact: artifact_fs.FilesystemArtifact, name: str, extra=None
    ):
        with artifact.open(f"{name}.ArrowWeaveList.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(ArrowTableType(), ArrowArrayType()),
                "object_type": types.TypeType(),
            }
        )
        if hasattr(self, "_key"):
            type_of_d.property_types["_key"] = self._key  # type: ignore

        mapper = mappers_python.map_from_python(type_of_d, artifact)
        res = mapper.apply(result)
        return self.instance_class(artifact=artifact, **res)  # type: ignore


def rewrite_weavelist_refs(arrow_data, object_type, source_artifact, target_artifact):
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
