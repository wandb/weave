import dataclasses
import pyarrow as pa
import pyarrow.parquet as pq

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
    raise errors.WeaveTypeError(
        "Type conversion not implemented for arrow type: %s" % pa_type
    )


def arrow_schema_to_weave_type(schema) -> types.Type:
    return types.TypedDict({f.name: arrow_type_to_weave_type(f.type) for f in schema})


@dataclasses.dataclass(frozen=True)
class ArrowArrayType(types.Type):
    instance_classes = [pa.ChunkedArray, pa.ExtensionArray, pa.Array]
    name = "ArrowArray"

    object_type: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj: pa.Array):
        return cls(arrow_type_to_weave_type(obj.type))

    def save_instance(self, obj, artifact, name):
        # Could use the arrow format instead. I think it supports memory
        # mapped random access, but is probably larger.
        # See here: https://arrow.apache.org/cookbook/py/io.html#saving-arrow-arrays-to-disk
        # TODO: what do we want?
        table = pa.table({"arr": obj})
        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(table, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.parquet", binary=True) as f:
            return pq.read_table(f)["arr"].combine_chunks()


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
