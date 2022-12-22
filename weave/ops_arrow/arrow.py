import dataclasses
import pyarrow as pa
import pyarrow.parquet as pq
import typing

py_type = type

from .. import weave_types as types
from .. import errors


def arrow_type_to_weave_type(pa_type) -> types.Type:
    if pa_type == pa.null():
        return types.NoneType()
    elif pa_type == pa.string():
        return types.String()
    elif pa_type == pa.int64() or pa_type == pa.int32():
        return types.Int()
    elif pa_type == pa.float64():
        return types.Float()
    elif pa_type == pa.bool_():
        return types.Boolean()
    elif pa.types.is_temporal(pa_type):
        return types.Datetime()
    elif pa.types.is_list(pa_type):
        return types.List(arrow_type_to_weave_type(pa_type.value_field.type))
    elif pa.types.is_struct(pa_type):
        return types.TypedDict(
            {f.name: arrow_type_to_weave_type(f.type) for f in pa_type}
        )
    elif pa.types.is_union(pa_type):
        return types.UnionType([arrow_type_to_weave_type(f.type) for f in pa_type])
    raise errors.WeaveTypeError(
        "Type conversion not implemented for arrow type: %s" % pa_type
    )


def arrow_schema_to_weave_type(schema) -> types.Type:
    return types.TypedDict({f.name: arrow_type_to_weave_type(f.type) for f in schema})


def table_with_structs_as_unions(table: pa.Table) -> pa.Table:
    def convert_struct_to_union(
        column: pa.ChunkedArray, column_name: str
    ) -> tuple[str, pa.ChunkedArray]:

        if column_name.startswith(ArrowArrayType.UNION_PREFIX):
            # we have a union field
            new_col = []
            for a in column.chunks:
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
                new_col.append(pa.UnionArray.from_sparse(type_code_array, arrays))
                column_name = column_name[len(ArrowArrayType.UNION_PREFIX) :]
            return column_name, pa.chunked_array(new_col)

        elif pa.types.is_struct(column.type):
            # we have a struct field - recurse it and convert all subfields to unions where applicable
            new_col = []
            for a in column.chunks:
                arrays = []
                names = []
                for field in a.type:
                    name, array = convert_struct_to_union(
                        pa.chunked_array(a.field(field.name)), field.name
                    )

                    arrays.append(array.combine_chunks())
                    names.append(name)
                new_col.append(pa.StructArray.from_arrays(arrays, names))
            return column_name, pa.chunked_array(new_col)

        else:
            # we have a regular field
            return column_name, column

    for i, column_name in enumerate(table.column_names):
        current_column = table[column_name]
        new_name, new_column = convert_struct_to_union(current_column, column_name)
        if new_column is not current_column:
            table = table.remove_column(i)
            table = table.add_column(i, new_name, new_column)

    return table


def table_with_unions_as_structs(table: pa.Table) -> pa.Table:
    def recursively_convert_unions_to_structs(
        column: pa.ChunkedArray, column_name: str
    ) -> tuple[str, pa.ChunkedArray]:

        if pa.types.is_union(column.type):
            new_col = []
            for a in column.chunks:
                if isinstance(a, pa.UnionArray):
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
            for a in column.chunks:
                names = []
                arrays = []
                for field in a.type:
                    new_name, chunked_array = recursively_convert_unions_to_structs(
                        pa.chunked_array(a.field(field.name)), field.name
                    )
                    names.append(new_name)
                    arrays.append(chunked_array.combine_chunks())

                new_col.append(pa.StructArray.from_arrays(arrays, names))
            column = pa.chunked_array(new_col)

        return column_name, column

    for i, column_name in enumerate(table.column_names):
        current_column = table[column_name]
        new_name, new_column = recursively_convert_unions_to_structs(
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

        table = table_with_unions_as_structs(table)

        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(table, f)

    def load_instance(self, artifact, name, extra=None):

        with artifact.open(f"{name}.parquet", binary=True) as f:
            deserialized = pq.read_table(f)
            # convert struct to union. parquet does not know how to serialize arrow unions, so
            # we store them in a struct format
            deserialized = table_with_structs_as_unions(deserialized)
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
    if isinstance(obj, pa.ChunkedArray):
        return obj.combine_chunks()
    if not isinstance(obj, pa.Array):
        raise TypeError("Expected pyarrow Array or Table, got %s" % type(obj))
    return obj
