import typing
import dataclasses
import json
import numpy as np
import pandas as pd
import pyarrow as pa


py_type = type

from ..api import op, weave_class, type, use
from ..decorator_op import arrow_op
from .. import weave_types as types
from .. import graph
from .. import errors
from .. import registry_mem
from .. import mappers_arrow
from .. import mappers_python_def
from .. import mappers_python
from .. import artifacts_local
from .. import storage
from .. import refs
from .. import dispatch
from .. import execute_fast
from .. import weave_internal
from .. import context
from .. import weavify
from .. import op_args
from ..language_features.tagging import tagged_value_type
from ..language_features.tagging import process_opdef_output_type
from . import arrow
from .. import arrow_util

from ..language_features.tagging import tag_store

from . import arrow

from .arrow import arrow_as_array

if typing.TYPE_CHECKING:
    from .. import artifacts_local

FLATTEN_DELIMITER = "➡️"


def _recursively_flatten_structs_in_array(
    arr: pa.Array, prefix: str, _stack_depth=0
) -> dict[str, pa.Array]:
    if pa.types.is_struct(arr.type):
        result: dict[str, pa.Array] = {}
        for field in arr.type:
            new_prefix = (
                prefix + (FLATTEN_DELIMITER if _stack_depth > 0 else "") + field.name
            )
            result.update(
                _recursively_flatten_structs_in_array(
                    arr.field(field.name),
                    new_prefix,
                    _stack_depth=_stack_depth + 1,
                )
            )
        return result
    return {prefix: arr}


# TODO: make more efficient
def _unflatten_structs_in_flattened_table(table: pa.Table) -> pa.Table:
    """take a table with column names like {a.b.c: [1,2,3], a.b.d: [4,5,6], a.e: [7,8,9]}
    and return a struct array with the following structure:
    [ {a: {b: {c: 1, d: 4}, e: 7}}, {a: {b: {c: 2, d: 5}, e: 8}}, {a: {b: {c: 3, d: 6}, e: 9}} ]"""

    # get all columns in table
    column_names = list(
        map(lambda name: name.split(FLATTEN_DELIMITER), table.column_names)
    )
    multi_index = pd.MultiIndex.from_tuples(column_names)
    df = table.to_pandas()
    df.columns = multi_index
    records = df.to_dict(orient="records")

    # convert to arrow
    # records now looks like [{('a', 'b', 'c'): 1, ('a', 'b', 'd'): 2, ('a', 'e', nan): 3},
    # {('a', 'b', 'c'): 4, ('a', 'b', 'd'): 5, ('a', 'e', nan): 6},
    # {('a', 'b', 'c'): 7, ('a', 'b', 'd'): 8, ('a', 'e', nan): 9}]
    new_records = []
    for record in records:
        new_record: dict[str, typing.Any] = {}
        for entry in record:
            current_pointer = new_record
            filtered_entry = list(filter(lambda key: key is not np.nan, entry))
            for i, key in enumerate(filtered_entry):
                if key not in current_pointer and i != len(filtered_entry) - 1:
                    current_pointer[key] = {}
                elif i == len(filtered_entry) - 1:
                    current_pointer[key] = record[entry]
                current_pointer = current_pointer[key]
        new_records.append(new_record)
    rb = pa.RecordBatch.from_pylist(new_records)
    return pa.Table.from_batches([rb])


def unzip_struct_array(arr: pa.ChunkedArray) -> pa.Table:
    flattened = _recursively_flatten_structs_in_array(arr.combine_chunks(), "")
    return pa.table(flattened)


def _pick_output_type(input_types):
    if not isinstance(input_types["key"], types.Const):
        return types.UnknownType()
    key = input_types["key"].val
    prop_type = input_types["self"].object_type.property_types.get(key)
    if prop_type is None:
        return types.Invalid()
    return ArrowWeaveListType(prop_type)


def rewrite_weavelist_refs(arrow_data, object_type, artifact):
    if _object_type_has_props(object_type):
        prop_types = _object_type_prop_types(object_type)
        if isinstance(arrow_data, pa.Table):
            arrays = {}
            for col_name, col_type in prop_types.items():
                column = arrow_data[col_name]
                arrays[col_name] = rewrite_weavelist_refs(column, col_type, artifact)
            return pa.table(arrays)
        elif isinstance(arrow_data, pa.ChunkedArray):
            arrays = {}
            unchunked = arrow_data.combine_chunks()
            for col_name, col_type in prop_types.items():
                column = unchunked.field(col_name)
                arrays[col_name] = rewrite_weavelist_refs(column, col_type, artifact)
            return pa.StructArray.from_arrays(arrays.values(), names=arrays.keys())
        elif isinstance(arrow_data, pa.StructArray):
            arrays = {}
            for col_name, col_type in prop_types.items():
                column = arrow_data.field(col_name)
                arrays[col_name] = rewrite_weavelist_refs(column, col_type, artifact)
            return pa.StructArray.from_arrays(arrays.values(), names=arrays.keys())
        else:
            raise errors.WeaveTypeError('Unhandled type "%s"' % type(arrow_data))
    elif isinstance(object_type, types.UnionType):
        non_none_members = [
            m for m in object_type.members if not isinstance(m, types.NoneType)
        ]
        if len(non_none_members) > 1:
            raise errors.WeaveInternalError(
                "Unions not fully supported yet in Weave arrow"
            )
        return rewrite_weavelist_refs(arrow_data, types.non_none(object_type), artifact)
    elif _object_type_is_basic(object_type):
        return arrow_data
    elif isinstance(object_type, types.List):
        # This is a bit unfortunate that we have to loop through all the items - would be nice to do a direct memory replacement.
        return pa.array(_rewrite_pyliteral_refs(item.as_py(), object_type, artifact) for item in arrow_data)  # type: ignore

    else:
        # We have a column of refs
        new_refs = []
        for ref_str in arrow_data:
            ref_str = ref_str.as_py()
            new_refs.append(_rewrite_ref_entry(ref_str, object_type, artifact))
        return pa.array(new_refs)


def _rewrite_pyliteral_refs(pyliteral_data, object_type, artifact):
    if _object_type_has_props(object_type):
        prop_types = _object_type_prop_types(object_type)
        if isinstance(pyliteral_data, dict):
            return {
                key: _rewrite_pyliteral_refs(pyliteral_data[key], value, artifact)
                for key, value in prop_types.items()
            }
        else:
            raise errors.WeaveTypeError('Unhandled type "%s"' % type(pyliteral_data))
    elif isinstance(object_type, types.UnionType):
        non_none_members = [
            m for m in object_type.members if not isinstance(m, types.NoneType)
        ]
        if len(non_none_members) > 1:
            raise errors.WeaveInternalError(
                "Unions not fully supported yet in Weave arrow"
            )
        return _rewrite_pyliteral_refs(
            pyliteral_data, types.non_none(object_type), artifact
        )
    elif _object_type_is_basic(object_type):
        return pyliteral_data
    elif isinstance(object_type, types.List):
        return [
            _rewrite_pyliteral_refs(item, object_type.object_type, artifact)
            for item in pyliteral_data
        ]
    else:
        return _rewrite_ref_entry(pyliteral_data, object_type, artifact)


def _object_type_has_props(object_type):
    return (
        isinstance(object_type, types.TypedDict)
        or isinstance(object_type, types.ObjectType)
        or isinstance(object_type, tagged_value_type.TaggedValueType)
    )


def _object_type_prop_types(object_type):
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
    return isinstance(object_type, types.BasicType) or (
        isinstance(object_type, types.Const)
        and isinstance(object_type.val_type, types.BasicType)
    )


def _rewrite_ref_entry(entry: str, object_type, artifact):
    if ":" in entry:
        return entry
    else:
        return str(refs.Ref.from_local_ref(artifact, entry, object_type).uri)


def rewrite_groupby_refs(arrow_data, group_keys, object_type, artifact):
    # TODO: Handle unions

    # hmm... we should just iterate over table columns instead!
    # This would be a nested iterate
    if isinstance(object_type, types.TypedDict) or isinstance(
        object_type, types.ObjectType
    ):
        prop_types = object_type.property_types
        if callable(prop_types):
            prop_types = prop_types()
        arrays = {}
        for group_key in group_keys:
            arrays[group_key] = arrow_data[group_key]
        for col_name, col_type in prop_types.items():
            col_name = col_name + "_list"
            column = arrow_data[col_name]
            arrays[col_name] = rewrite_groupby_refs(
                column, group_keys, col_type, artifact
            )
        return pa.table(arrays)
    elif isinstance(object_type, types.UnionType):
        if any(types.is_custom_type(m) for m in object_type.members):
            raise errors.WeaveInternalError(
                "Unions of custom types not yet support in Weave arrow"
            )
        return arrow_data
    else:
        if isinstance(object_type, types.BasicType):
            return arrow_data

        # We have a column of refs

        new_refs = []
        for ref_str_list in arrow_data:
            ref_str_list = ref_str_list.as_py()
            new_ref_str_list = []
            for ref_str in ref_str_list:
                if ":" in ref_str:
                    new_ref_str_list.append(ref_str)
                else:
                    ref = refs.LocalArtifactRef.from_local_ref(
                        artifact, ref_str, object_type
                    )
                    new_ref_str_list.append(str(ref.uri))
            new_refs.append(new_ref_str_list)
        return pa.array(new_refs)


@dataclasses.dataclass(frozen=True)
class ArrowTableGroupByType(types.Type):
    name = "ArrowTableGroupBy"

    object_type: types.Type = types.Any()
    key: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.object_type, obj.key_type)

    def save_instance(self, obj, artifact, name):
        if obj._artifact == artifact:
            raise errors.WeaveInternalError("not yet implemented")
        table = rewrite_weavelist_refs(obj._table, obj.object_type, obj._artifact)
        d = {
            "_table": table,
            "_groups": obj._groups,
            "_group_keys": obj._group_keys,
            "object_type": obj.object_type,
            "key_type": obj.key_type,
        }
        type_of_d = types.TypedDict(
            {
                "_table": types.union(arrow.ArrowTableType(), arrow.ArrowArrayType()),
                "_groups": types.union(arrow.ArrowTableType(), arrow.ArrowArrayType()),
                "_group_keys": types.List(types.String()),
                "object_type": types.TypeType(),
                "key_type": types.TypeType(),
            }
        )
        serializer = mappers_python.map_to_python(type_of_d, artifact)
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.ArrowTableGroupBy.json") as f:
            json.dump(result_d, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.ArrowTableGroupBy.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_table": types.union(arrow.ArrowTableType(), arrow.ArrowArrayType()),
                "_groups": types.union(arrow.ArrowTableType(), arrow.ArrowArrayType()),
                "_group_keys": types.List(types.String()),
                "object_type": types.TypeType(),
                "key_type": types.TypeType(),
            }
        )

        mapper = mappers_python.map_from_python(type_of_d, artifact)
        res = mapper.apply(result)
        return ArrowTableGroupBy(
            res["_table"],
            res["_groups"],
            res["_group_keys"],
            res["object_type"],
            res["key_type"],
            artifact,
        )


@weave_class(weave_type=ArrowTableGroupByType)
class ArrowTableGroupBy:
    def __init__(self, _table, _groups, _group_keys, object_type, key_type, artifact):
        self._table = _table
        self._groups = _groups
        self._group_keys = _group_keys
        self.object_type = object_type
        self.key_type = key_type
        # if self.object_type is None:
        #     self.object_type = types.TypeRegistry.type_of(self._table).object_type
        self._artifact = artifact
        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)

    @op()
    def count(self) -> int:
        return len(self._groups)

    def __len__(self):
        return len(self._groups)

    @op(
        output_type=lambda input_types: ArrowTableGroupResultType(
            input_types["self"].object_type,
            input_types["self"].key,
        )
    )
    def __getitem__(self, index: int):
        try:
            row = self._groups.slice(index, 1)
        except pa.ArrowIndexError:
            return None

        if len(row) == 0:
            return None

        if self._group_keys == ["group_key"]:
            group_key = row["group_key"][0]
        else:
            row_key = row.select(self._group_keys)
            key = {}
            for col_name, column in zip(row_key.column_names, row_key.columns):
                key[col_name.removeprefix("group_key_")] = column.combine_chunks()
            group_key = pa.StructArray.from_arrays(key.values(), key.keys())[0]

        group_indexes = row["_index_list"].combine_chunks()[0].values
        group_table = self._table.take(group_indexes)

        return ArrowTableGroupResult(
            # TODO: remove as_py() from group_key. Stay in arrow!
            group_table,
            group_key.as_py(),
            self.object_type,
            self._artifact,
        )

    @op(
        input_type={
            "self": ArrowTableGroupByType(),
            "map_fn": lambda input_types: types.Function(
                {
                    "row": ArrowTableGroupResultType(
                        input_types["self"].object_type,
                        input_types["self"].key,
                    )
                },
                types.Any(),
            ),
        },
        output_type=lambda input_types: types.List(input_types["map_fn"].output_type),
    )
    def map(self, map_fn):
        return execute_fast.fast_map_fn(self, map_fn)


ArrowTableGroupByType.instance_classes = ArrowTableGroupBy
ArrowTableGroupByType.instance_class = ArrowTableGroupBy


@dataclasses.dataclass(frozen=True)
class ArrowWeaveListType(types.Type):
    _base_type = types.List()
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
                obj._arrow_data, obj.object_type, obj._artifact
            )

        d = {"_arrow_data": arrow_data, "object_type": obj.object_type}
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(
                    arrow.ArrowTableType(), arrow.ArrowArrayType()
                ),
                "object_type": types.TypeType(),
            }
        )
        if hasattr(self, "_key"):
            d["_key"] = obj._key
            type_of_d.property_types["_key"] = self._key

        serializer = mappers_python.map_to_python(type_of_d, artifact)
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.ArrowWeaveList.json") as f:
            json.dump(result_d, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.ArrowWeaveList.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(
                    arrow.ArrowTableType(), arrow.ArrowArrayType()
                ),
                "object_type": types.TypeType(),
            }
        )
        if hasattr(self, "_key"):
            type_of_d.property_types["_key"] = self._key

        mapper = mappers_python.map_from_python(type_of_d, artifact)
        res = mapper.apply(result)
        return self.instance_class(artifact=artifact, **res)


ArrowWeaveListObjectTypeVar = typing.TypeVar("ArrowWeaveListObjectTypeVar")


def map_output_type(input_types):
    return ArrowWeaveListType(input_types["map_fn"].output_type)


@weave_class(weave_type=ArrowWeaveListType)
class ArrowWeaveList(typing.Generic[ArrowWeaveListObjectTypeVar]):
    _arrow_data: typing.Union[pa.Table, pa.ChunkedArray, pa.Array]
    object_type: types.Type

    def _arrow_data_asarray_no_tags(self) -> pa.Array:
        """Cast `self._arrow_data` as an array and recursively strip its tags."""

        # arrow_as_array is idempotent so even though we will hit this on every recursive call,
        # it will be a no-op after the first time.
        arrow_data = arrow_as_array(self._arrow_data)

        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return ArrowWeaveList(
                arrow_data.field("_value"),
                self.object_type.value,
                self._artifact,
            )._arrow_data_asarray_no_tags()

        elif isinstance(self.object_type, (types.TypedDict, types.ObjectType)):
            # strip tags from each field
            arrays = []
            keys = []

            prop_types = self.object_type.property_types
            if callable(prop_types):
                prop_types = prop_types()

            for field in arrow_data.type:
                keys.append(field.name)
                arrays.append(
                    ArrowWeaveList(
                        arrow_data.field(field.name),
                        prop_types[field.name],
                        self._artifact,
                    )._arrow_data_asarray_no_tags()
                )
            return pa.StructArray.from_arrays(arrays, names=keys)

        elif isinstance(self.object_type, types.List):
            offsets = arrow_data.offsets
            # strip tags from each element
            flattened = ArrowWeaveList(
                arrow_data.flatten(),
                self.object_type.object_type,
                self._artifact,
            )._arrow_data_asarray_no_tags()

            # unflatten
            return pa.ListArray.from_arrays(offsets, flattened)

        elif isinstance(self.object_type, types.UnionType):
            # strip tags from each element
            for member in self.object_type.members:
                if isinstance(member, tagged_value_type.TaggedValueType):
                    raise NotImplementedError(
                        'TODO: implement handling of "Union[TaggedValue, ...]'
                    )

        return arrow_data

    def __array__(self, dtype=None):
        return np.asarray(self.to_pylist())

    def __iter__(self):
        for item in self.to_pylist():
            yield self._mapper.apply(item)

    def __repr__(self):
        return f"<ArrowWeaveList: {self.object_type}>"

    def to_pylist_notags(self):
        return self._arrow_data_asarray_no_tags().to_pylist()

    def to_pylist(self):
        if isinstance(self, graph.Node):
            return []
        return self._arrow_data.to_pylist()

    # TODO: Refactor to disable None artifact? (Only used in tests)
    def __init__(self, _arrow_data, object_type=None, artifact=None) -> None:
        self._arrow_data = _arrow_data
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._arrow_data).object_type
        self._artifact = artifact
        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)
        # TODO: construct mapper

    @op(output_type=lambda input_types: types.List(input_types["self"].object_type))
    def to_py(self):
        return list(self)

    def _count(self):
        return len(self._arrow_data)

    def __len__(self):
        return self._count()

    @op()
    def count(self) -> int:
        return self._count()

    def _get_col(self, name):
        if isinstance(self._arrow_data, pa.Table):
            col = self._arrow_data[name]
        elif isinstance(self._arrow_data, pa.ChunkedArray):
            raise NotImplementedError("TODO: implement this")
        elif isinstance(self._arrow_data, pa.StructArray):
            col = self._arrow_data.field(name)
        col_mapper = self._mapper._property_serializers[name]
        if isinstance(col_mapper, mappers_python_def.DefaultFromPy):
            return [col_mapper.apply(i.as_py()) for i in col]
        return col

    def _index(self, index):
        try:
            row = self._arrow_data.slice(index, 1)
        except IndexError:
            return None
        if not row:
            return None
        res = self._mapper.apply(row.to_pylist()[0])
        return res

    @op(output_type=lambda input_types: input_types["self"].object_type)
    def __getitem__(self, index: int):
        return self._index(index)

    @arrow_op(
        input_type={
            "self": ArrowWeaveListType(),
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type, "index": types.Int()},
                types.Any(),
            ),
        },
        output_type=map_output_type,
    )
    def map(self, map_fn):
        vectorized_map_fn = vectorize(map_fn)
        map_result_node = weave_internal.call_fn(
            vectorized_map_fn,
            {
                "row": weave_internal.make_const_node(
                    ArrowWeaveListType(self.object_type), self
                )
            },
        )

        return use(map_result_node)

    def _append_column(self, name: str, data) -> "ArrowWeaveList":
        if not data:
            raise ValueError(f'Data for new column "{name}" must be nonnull.')

        new_data = self._arrow_data.append_column(name, [data])
        return ArrowWeaveList(new_data, None, self._artifact)

    def concatenate(self, other: "ArrowWeaveList") -> "ArrowWeaveList":
        arrow_data = [awl._arrow_data for awl in (self, other)]
        if (
            all([isinstance(ad, pa.ChunkedArray) for ad in arrow_data])
            and arrow_data[0].type == arrow_data[1].type
        ):
            return ArrowWeaveList(
                pa.chunked_array(arrow_data[0].chunks + arrow_data[1].chunks),
                self.object_type,
                self._artifact,
            )
        elif (
            all([isinstance(ad, pa.Table) for ad in arrow_data])
            and arrow_data[0].schema == arrow_data[1].schema
        ):
            return ArrowWeaveList(
                pa.concat_tables([arrow_data[0], arrow_data[1]]),
                self.object_type,
                self._artifact,
            )
        elif (
            all([isinstance(ad, pa.StructArray) for ad in arrow_data])
            and arrow_data[0].type == arrow_data[1].type
        ):
            return ArrowWeaveList(
                pa.concat_arrays(arrow_data), self.object_type, self._artifact
            )
        else:

            raise ValueError(
                "Can only concatenate two ArrowWeaveLists that both contain "
                "ChunkedArrays of the same type or Tables of the same schema."
            )

    @op(
        input_type={
            "self": ArrowWeaveListType(),
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: ArrowTableGroupByType(
            input_types["self"].object_type, input_types["group_by_fn"].output_type
        ),
    )
    def groupby(self, group_by_fn):
        vectorized_groupby_fn = vectorize(group_by_fn)
        group_table_node = weave_internal.call_fn(
            vectorized_groupby_fn,
            {
                "row": weave_internal.make_const_node(
                    ArrowWeaveListType(self.object_type), self
                )
            },
        )
        table = self._arrow_data

        group_table_awl: ArrowWeaveList = use(group_table_node)

        group_table = group_table_awl._arrow_data
        group_table = arrow.arrow_as_array(group_table)

        # strip tags recursively so we group on values only
        group_table = ArrowWeaveList(
            group_table, group_table_node.type.object_type, self._artifact
        )._arrow_data_asarray_no_tags()

        # There was a comment that arrow doesn't allow grouping on struct columns
        # and another large block of code that tried to avoid passing in a struct column.
        # But that code was actually never executing due to a bug.
        # TODO: investigate and fix this (do we really need unzip_struct_array?)
        if isinstance(group_table, (pa.ChunkedArray, pa.Array, pa.StructArray)):
            if isinstance(group_table, pa.ChunkedArray):
                group_table = group_table.combine_chunks()
            original_col_names = ["group_key"]
            group_table = pa.chunked_array(
                pa.StructArray.from_arrays([group_table], names=original_col_names)
            )
            group_table = unzip_struct_array(group_table)
            group_cols = group_table.column_names
        else:
            raise errors.WeaveInternalError(
                "Arrow groupby not yet support for map result: %s" % type(group_table)
            )

        # Serializing a large arrow table and then reading it back
        # causes it to come back with more than 1 chunk. It seems the aggregation
        # operations don't like this. It will raise a cryptic error about
        # ExecBatches need to have the same link without this combine_chunks line
        # But combine_chunks doesn't seem like the most efficient thing to do
        # either, since it'll have to concatenate everything together.
        # But this fixes the crash for now!
        # TODO: investigate this as we optimize the arrow implementation
        group_table = group_table.combine_chunks()

        group_table = group_table.append_column(
            "_index", pa.array(np.arange(len(group_table)))
        )
        grouped = group_table.group_by(group_cols)
        agged = grouped.aggregate([("_index", "list")])
        agged = _unflatten_structs_in_flattened_table(agged)

        for arr in agged:
            tag_store.add_tags(arr, {"groupKey": original_col_names})

        return ArrowTableGroupBy(
            table,
            agged,
            original_col_names,
            self.object_type,
            group_by_fn.type,
            self._artifact,
        )

    @op(output_type=lambda input_types: input_types["self"])
    def offset(self, offset: int):
        return ArrowWeaveList(
            self._arrow_data.slice(offset), self.object_type, self._artifact
        )

    def _limit(self, limit: int):
        return ArrowWeaveList(
            self._arrow_data.slice(0, limit), self.object_type, self._artifact
        )

    @op(output_type=lambda input_types: input_types["self"])
    def limit(self, limit: int):
        return self._limit(limit)

    @op(
        input_type={"self": ArrowWeaveListType(types.TypedDict({}))},
        output_type=lambda input_types: ArrowWeaveListType(
            types.TypedDict(
                {
                    k: v
                    if not (types.is_list_like(v) or isinstance(v, ArrowWeaveListType))
                    else v.object_type
                    for (k, v) in input_types["self"].object_type.property_types.items()
                }
            )
        ),
    )
    def unnest(self):
        if not self or not isinstance(self.object_type, types.TypedDict):
            return self

        list_cols = []
        for k, v_type in self.object_type.property_types.items():
            if types.is_list_like(v_type):
                list_cols.append(k)
        if not list_cols:
            return self

        if isinstance(self._arrow_data, pa.StructArray):
            rb = pa.RecordBatch.from_struct_array(
                self._arrow_data
            )  # this pivots to columnar layout
            arrow_obj = pa.Table.from_batches([rb])
        else:
            arrow_obj = self._arrow_data

        # todo: make this more efficient. we shouldn't have to convert back and forth
        # from the arrow in-memory representation to pandas just to call the explode
        # function. but there is no native pyarrow implementation of this
        return pa.Table.from_pandas(
            df=arrow_obj.to_pandas().explode(list_cols), preserve_index=False
        )


def pushdown_list_tags(arr: ArrowWeaveList) -> ArrowWeaveList:

    if tag_store.is_tagged(arr):
        tag = tag_store.get_tags(arr)
        tag_type = types.TypeRegistry.type_of(tag)
        tags: ArrowWeaveList = to_arrow([tag] * len(arr))
        return awl_add_arrow_tags(arr, tags._arrow_data, tag_type)
    return arr


ArrowWeaveListType.instance_classes = ArrowWeaveList
ArrowWeaveListType.instance_class = ArrowWeaveList


def awl_object_type_with_index(object_type):
    return tagged_value_type.TaggedValueType(
        types.TypedDict({"indexCheckpoint": types.Int()}), object_type
    )


def arrow_weave_list_createindexcheckpoint_output_type(input_type):
    return ArrowWeaveListType(awl_object_type_with_index(input_type["arr"].object_type))


@op(
    name="arrowWeaveList-createIndexCheckpointTag",
    input_type={"arr": ArrowWeaveListType(types.Any())},
    output_type=arrow_weave_list_createindexcheckpoint_output_type,
)
def arrow_weave_list_createindexCheckpoint(arr):
    # Tags are always stored as a list of dicts, even if there is only one tag
    tag_array = pa.StructArray.from_arrays(
        [pa.array(np.arange(len(arr._arrow_data)))],
        names=["indexCheckpoint"],
    )
    return awl_add_arrow_tags(
        arr,
        tag_array,
        types.TypedDict({"indexCheckpoint": types.Int()}),
    )


# Handle tag pushdown
def _concat_output_type(input_types: typing.Dict[str, types.List]) -> types.Type:
    arr_type: types.List = input_types["arr"]
    arr_object_type = arr_type.object_type

    types_to_check: typing.List[types.Type] = [arr_object_type]
    if isinstance(arr_object_type, types.UnionType):
        types_to_check = arr_object_type.members

    inner_element_members = []
    for element_type in types_to_check:
        if isinstance(element_type, tagged_value_type.TaggedValueType):
            # push down tags
            value_type = element_type.value
            tag_type = element_type.tag
            if not isinstance(value_type, (ArrowWeaveListType, types.NoneType)):
                raise ValueError(
                    f"Cannot concatenate tagged value of type {value_type} with ArrowWeaveList"
                )

            if isinstance(value_type, ArrowWeaveListType):
                # see if elements are tagged
                element_tag_type: types.TypedDict
                if isinstance(
                    value_type.object_type, tagged_value_type.TaggedValueType
                ):
                    element_tag_type = value_type.object_type.tag
                    new_value_type = value_type.object_type.value
                else:
                    element_tag_type = types.TypedDict({})
                    new_value_type = value_type.object_type

                inner_element_members.append(
                    tagged_value_type.TaggedValueType(
                        types.TypedDict(
                            {
                                **tag_type.property_types,
                                **element_tag_type.property_types,
                            }
                        ),
                        new_value_type,
                    )
                )

            else:
                inner_element_members.append(
                    tagged_value_type.TaggedValueType(
                        tag_type,
                        types.NoneType(),
                    )
                )
        elif isinstance(element_type, ArrowWeaveListType):
            return element_type
        elif isinstance(element_type, types.NoneType):
            continue
        else:
            raise ValueError(
                f"Cannot concatenate value of type {element_type} with ArrowWeaveList"
            )

    return ArrowWeaveListType(types.union(*inner_element_members))


@op(
    name="ArrowWeaveList-concat",
    input_type={
        "arr": types.List(
            types.union(types.NoneType(), ArrowWeaveListType(types.Any()))
        )
    },
    output_type=_concat_output_type,
)
def concat(arr):
    arr = [item for item in arr if item != None]

    if len(arr) == 0:
        return to_arrow([])
    elif len(arr) == 1:
        return arr[0]

    res = arr[0]
    res = typing.cast(ArrowWeaveList, res)
    res = pushdown_list_tags(res)

    for i in range(1, len(arr)):
        tagged = pushdown_list_tags(arr[i])
        res = res.concatenate(tagged)
    return res


@dataclasses.dataclass(frozen=True)
class ArrowTableGroupResultType(ArrowWeaveListType):
    name = "ArrowTableGroupResult"

    _key: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(
            obj.object_type,
            types.TypeRegistry.type_of(obj._key),
        )


@weave_class(weave_type=ArrowTableGroupResultType)
class ArrowTableGroupResult(ArrowWeaveList):
    def __init__(self, _arrow_data, _key, object_type=None, artifact=None):
        self._arrow_data = _arrow_data
        self._key = _key
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._table).object_type
        self._artifact = artifact
        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)

    @op(output_type=lambda input_types: input_types["self"]._key)
    def groupkey(self):
        return self._key


ArrowTableGroupResultType.instance_classes = ArrowTableGroupResult
ArrowTableGroupResultType.instance_class = ArrowTableGroupResult


class VectorizeError(errors.WeaveBaseError):
    pass


def make_vectorized_object_constructor(constructor_op_name: str) -> None:
    constructor_op = registry_mem.memory_registry.get_op(constructor_op_name)
    if callable(constructor_op.raw_output_type):
        raise errors.WeaveInternalError(
            "Unexpected. All object type constructors have fixed return types."
        )

    type_name = constructor_op.raw_output_type.name
    vectorized_constructor_op_name = f'ArrowWeaveList-{type_name.replace("-", "_")}'
    if registry_mem.memory_registry.have_op(vectorized_constructor_op_name):
        return

    output_type = ArrowWeaveListType(constructor_op.raw_output_type)

    @op(
        name=vectorized_constructor_op_name,
        input_type={
            "attributes": ArrowWeaveListType(
                constructor_op.input_type.weave_type().property_types["attributes"]  # type: ignore
            )
        },
        output_type=output_type,
        render_info={"type": "function"},
    )
    def vectorized_constructor(attributes):
        if callable(output_type):
            ot = output_type({"attributes": types.TypeRegistry.type_of(attributes)})
        else:
            ot = output_type
        return ArrowWeaveList(
            attributes._arrow_data, ot.object_type, attributes._artifact
        )


def vectorize(
    weave_fn,
    with_respect_to: typing.Optional[typing.Iterable[graph.VarNode]] = None,
    stack_depth: int = 0,
):
    """Convert a Weave Function of T to a Weave Function of ArrowWeaveList[T]

    We walk the DAG represented by weave_fn, starting from its roots. Replace
    with_respect_to VarNodes of Type T with ArrowWeaveList[T]. Then as we
    walk up the DAG, replace OutputNodes with new op calls to whatever ops
    exist that can handle the changed input types.
    """

    # TODO: handle with_respect_to, it doesn't do anything right now.

    if stack_depth > 10:
        raise VectorizeError("Vectorize recursion depth exceeded")

    def ensure_object_constructors_created(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            if node.from_op.name.startswith("objectConstructor-"):
                make_vectorized_object_constructor(node.from_op.name)
        return node

    def expand_nodes(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            inputs = node.from_op.inputs
            if node.from_op.name == "number-pybin":
                bin_fn = weave_internal.use(inputs["bin_fn"])
                in_ = inputs["in_"]
                return weave_internal.call_fn(bin_fn, {"row": in_})  # type: ignore
        return node

    def convert_node(node):
        if isinstance(node, graph.OutputNode):
            inputs = node.from_op.inputs
            # since dict takes OpVarArgs(typing.Any()) as input, it will always show up
            # as a candidate for vectorizing itself. We don't want to do that, so we
            # explicitly force using ArrowWeaveList-dict instead.
            if node.from_op.name == "dict":
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveList-vectorizedDict"
                )
                return op.lazy_call(**inputs)
            if node.from_op.name == "list":
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveList-vectorizedList"
                )
                return op.lazy_call(**inputs)
            elif node.from_op.name == "Object-__getattr__":
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveListObject-__vectorizedGetattr__"
                )
                return op.lazy_call(**inputs)
            else:
                # Get a version of op that can handle vectorized (ArrowWeaveList) inputs
                op = dispatch.get_op_for_input_types(
                    node.from_op.name, [], {k: v.type for k, v in inputs.items()}
                )
                if (
                    op
                    and isinstance(op.input_type, op_args.OpNamedArgs)
                    and isinstance(
                        list(op.input_type.arg_types.values())[0], ArrowWeaveListType
                    )
                ):
                    # We have a vectorized implementation of this op already.
                    final_inputs = {
                        k: v for k, v in zip(op.input_type.arg_types, inputs.values())
                    }
                    return op.lazy_call(**final_inputs)
                # see if weave function can be expanded and vectorized
                op_def = registry_mem.memory_registry.get_op(node.from_op.name)
                if op_def.weave_fn is None:
                    # this could raise
                    try:
                        op_def.weave_fn = weavify.op_to_weave_fn(op_def)
                    except errors.WeavifyError:
                        pass
                if op_def.weave_fn is not None:
                    vectorized = vectorize(op_def.weave_fn, stack_depth=stack_depth + 1)
                    return weave_internal.call_fn(vectorized, inputs)
                else:
                    # No weave_fn, so we can't vectorize this op. Just
                    # use map
                    input0_name, input0_val = list(inputs.items())[0]
                    if isinstance(input0_val, ArrowWeaveList):
                        py_node = input0_val.to_py()
                        new_inputs = {input0_name: py_node}
                        for k, v in list(inputs.items())[1:]:
                            new_inputs[k] = v
                    else:
                        new_inputs = inputs
                    op = dispatch.get_op_for_input_types(
                        node.from_op.name,
                        [],
                        {k: v.type for k, v in new_inputs.items()},
                    )
                    if op is None:
                        raise VectorizeError(
                            "No fallback mapped op found for: %s" % node.from_op.name
                        )
                    return op.lazy_call(**new_inputs)
        elif isinstance(node, graph.VarNode):
            # Vectorize variable
            # NOTE: This is the only line that is specific to the arrow
            #     implementation (uses ArrowWeaveListType). Everything
            #     else will work for other List types, as long as there is
            #     a set of ops declared that can handle the new types.
            if with_respect_to is None or any(
                node is wrt_node for wrt_node in with_respect_to
            ):
                return graph.VarNode(ArrowWeaveListType(node.type), node.name)
            return node
        elif isinstance(node, graph.ConstNode):
            return node

    weave_fn = graph.map_nodes(weave_fn, ensure_object_constructors_created)
    weave_fn = graph.map_nodes(weave_fn, expand_nodes)
    return graph.map_nodes(weave_fn, convert_node)


def dataframe_to_arrow(df):
    return ArrowWeaveList(pa.Table.from_pandas(df))


# This will be a faster version fo to_arrow (below). Its
# used in op file-table, to convert from a wandb Table to Weave
# (that code is very experimental and not totally working yet)
def to_arrow_from_list_and_artifact(obj, object_type, artifact):
    # Get what the parquet type will be.
    mapper = mappers_arrow.map_to_arrow(object_type, artifact)
    pyarrow_type = mapper.result_type()

    if pa.types.is_struct(pyarrow_type):
        fields = list(pyarrow_type)
        schema = pa.schema(fields)
        arrow_obj = pa.Table.from_pylist(obj, schema=schema)
    else:
        arrow_obj = pa.array(obj, pyarrow_type)
    weave_obj = ArrowWeaveList(arrow_obj, object_type, artifact)
    return weave_obj


def to_arrow(obj, wb_type=None):
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifacts_local.LocalArtifact("to-arrow-%s" % wb_type.name)
    outer_tags: typing.Optional[dict[str, typing.Any]] = None
    if isinstance(wb_type, tagged_value_type.TaggedValueType):
        outer_tags = tag_store.get_tags(obj)
        wb_type = wb_type.value
    if isinstance(wb_type, types.List):
        object_type = wb_type.object_type

        # Convert to arrow, serializing Custom objects to the artifact
        mapper = mappers_arrow.map_to_arrow(object_type, artifact)
        pyarrow_type = mapper.result_type()
        py_objs = (mapper.apply(o) for o in obj)

        # TODO: do I need this branch? Does it work now?
        # if isinstance(wb_type.object_type, types.ObjectType):
        #     arrow_obj = pa.array(py_objs, pyarrow_type)
        arrow_obj = pa.array(py_objs, pyarrow_type)
        weave_obj = ArrowWeaveList(arrow_obj, object_type, artifact)

        # Save the weave object to the artifact
        ref = storage.save(weave_obj, artifact=artifact)
        if outer_tags is not None:
            tag_store.add_tags(ref.obj, outer_tags)

        return ref.obj

    raise errors.WeaveInternalError("to_arrow not implemented for: %s" % obj)


def awl_add_arrow_tags(
    l: ArrowWeaveList, arrow_tags: pa.StructArray, tag_type: types.Type
):
    # get current tags
    data = l._arrow_data
    current_tags = None
    if isinstance(data, pa.Table):
        if "_tag" in data.column_names:
            current_tags = data["_tag"].combine_chunks()
    elif isinstance(data, pa.StructArray):
        if data.type.get_field_index("_tag") > -1:
            current_tags = data.field("_tag")
    if current_tags is None:
        tag_arrays = []
        tag_names = []
    else:
        tag_arrays = [current_tags.field(f.name) for f in current_tags.type]
        tag_names = [f.name for f in current_tags.type]

    for tag_field in arrow_tags.type:
        if tag_field.name in tag_names:
            existing_index = tag_names.index(tag_field.name)
            tag_arrays[existing_index] = arrow_tags.field(tag_field.name)
        else:
            tag_arrays.append(arrow_tags.field(tag_field.name))
            tag_names.append(tag_field.name)

    tag_array = pa.StructArray.from_arrays(
        tag_arrays,
        tag_names,
    )
    if isinstance(l._arrow_data, pa.Table):
        if isinstance(l.object_type, tagged_value_type.TaggedValueType):
            new_value = l._arrow_data["_value"]
        else:
            new_value = pa.StructArray.from_arrays(
                # TODO: we shouldn't need to combine chunks, we can produce this in the
                # original chunked form for zero copy
                [c.combine_chunks() for c in l._arrow_data.columns],
                names=l._arrow_data.column_names,
            )
    elif isinstance(l._arrow_data, pa.StructArray):
        if isinstance(l.object_type, tagged_value_type.TaggedValueType):
            new_value = l._arrow_data.field("_value")
        else:
            new_value = l._arrow_data
    else:
        # Else its an arrow array
        new_value = l._arrow_data
    new_value = pa.StructArray.from_arrays([tag_array, new_value], ["_tag", "_value"])

    new_object_type = process_opdef_output_type.op_make_type_tagged_resolver(
        l.object_type, tag_type
    )

    return ArrowWeaveList(new_value, new_object_type, l._artifact)


def vectorized_input_types(input_types: dict[str, types.Type]) -> dict[str, types.Type]:
    prop_types: dict[str, types.Type] = {}
    for input_name, input_type in input_types.items():
        if isinstance(input_type, tagged_value_type.TaggedValueType) and (
            isinstance(input_type.value, ArrowWeaveListType)
            or types.is_list_like(input_type.value)
        ):
            outer_tag_type = input_type.tag
            object_type = input_type.value.object_type  # type: ignore
            if isinstance(object_type, tagged_value_type.TaggedValueType):
                new_prop_type = tagged_value_type.TaggedValueType(
                    types.TypedDict(
                        {
                            **outer_tag_type.property_types,
                            **object_type.tag.property_types,
                        }
                    ),
                    object_type.value,
                )
            else:
                new_prop_type = tagged_value_type.TaggedValueType(
                    outer_tag_type, object_type
                )
            prop_types[input_name] = new_prop_type
        elif isinstance(input_type, ArrowWeaveListType) or types.is_list_like(
            input_type
        ):
            prop_types[input_name] = input_type.object_type  # type: ignore
        else:  # is scalar
            prop_types[input_name] = input_type
    return prop_types


@dataclasses.dataclass
class VectorizedContainerConstructorResults:
    arrays: list[pa.Array]
    prop_types: dict[str, types.Type]
    max_len: int
    artifact: typing.Optional["artifacts_local.Artifact"]


def vectorized_container_constructor_preprocessor(
    input_dict: dict[str, typing.Any]
) -> VectorizedContainerConstructorResults:
    if len(input_dict) == 0:
        return VectorizedContainerConstructorResults([], {}, 0, None)
    arrays = []
    prop_types = {}
    awl_artifact = None
    for k, v in input_dict.items():
        if isinstance(v, ArrowWeaveList):
            if awl_artifact is None:
                awl_artifact = v._artifact
            if tag_store.is_tagged(v):
                list_tags = tag_store.get_tags(v)
                v = awl_add_arrow_tags(
                    v,
                    pa.array([list_tags] * len(v)),
                    types.TypeRegistry.type_of(list_tags),
                )
            prop_types[k] = v.object_type
            v = v._arrow_data
            arrays.append(arrow_as_array(v))
        else:
            prop_types[k] = types.TypeRegistry.type_of(v)
            arrays.append(v)

    array_lens = []
    for a, t in zip(arrays, prop_types.values()):
        if hasattr(a, "to_pylist"):
            array_lens.append(len(a))
        else:
            array_lens.append(0)
    max_len = max(array_lens)
    for l in array_lens:
        if l != 0 and l != max_len:
            raise errors.WeaveInternalError(
                f"Cannot create ArrowWeaveDict with different length arrays (scalars are ok): {array_lens}"
            )
    if max_len == 0:
        max_len = 1
    for i, (a, l) in enumerate(zip(arrays, array_lens)):
        if l == 0:
            arrays[i] = pa.array([a] * max_len)

    return VectorizedContainerConstructorResults(
        arrays, prop_types, max_len, awl_artifact
    )


def vectorized_list_output_type(input_types):
    element_types = vectorized_input_types(input_types).values()
    return ArrowWeaveListType(types.List(types.union(*element_types)))


@op(
    name="ArrowWeaveList-vectorizedList",
    input_type=op_args.OpVarArgs(types.Any()),
    output_type=vectorized_list_output_type,
    render_info={"type": "function"},
)
def arrow_list_(**e):
    res = vectorized_container_constructor_preprocessor(e)
    element_types = res.prop_types.values()
    values = pa.concat_arrays(res.arrays)
    offsets = pa.array(
        [i * len(e) for i in range(res.max_len)] + [res.max_len * len(e)]
    )
    return ArrowWeaveList(
        pa.ListArray.from_arrays(offsets, values),
        types.List(types.union(*element_types)),
        res.artifact,
    )
