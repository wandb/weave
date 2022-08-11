import typing
import dataclasses
import json
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from .. import weave_internal

from ..api import op, weave_class
from . import list_
from .. import weave_types as types
from .. import graph
from .. import errors
from .. import registry_mem


class ArrowArrayVectorizer:
    def __init__(self, arr):
        self.arr = arr

    def _get_col(self, key):
        col = self.arr._get_col(key)
        if isinstance(col, list):
            return col
        return ArrowArrayVectorizer(col)

    def items(self):
        for col_name in self.arr._arrow_data.column_names:
            yield col_name, self._get_col(col_name)

    def __getattr__(self, attr):
        return self._get_col(attr)

    def __len__(self):
        return len(self.arr)

    def __getitem__(self, key):
        return ArrowArrayVectorizer(self.arr[key])

    def __add__(self, other):
        if isinstance(other, ArrowArrayVectorizer):
            other = other.arr
        return ArrowArrayVectorizer(pc.add(self.arr, other))

    def __sub__(self, other):
        if isinstance(other, ArrowArrayVectorizer):
            other = other.arr
        return ArrowArrayVectorizer(pc.subtract(self.arr, other))

    def __gt__(self, other):
        return ArrowArrayVectorizer(pc.greater(self.arr, other))

    def __mult__(self, other):
        if isinstance(other, ArrowArrayVectorizer):
            other = other.arr
        return ArrowArrayVectorizer(pc.divide(self.arr, other))

    def __truediv__(self, other):
        if isinstance(other, ArrowArrayVectorizer):
            other = other.arr
        return ArrowArrayVectorizer(pc.divide(self.arr, other))

    def __pow__(self, other):
        if isinstance(other, ArrowArrayVectorizer):
            other = other.arr
        return ArrowArrayVectorizer(pc.power(self.arr, other))


def mapped_fn_to_arrow(arrow_table, node):
    if isinstance(node, graph.ConstNode):
        return node.val
    elif isinstance(node, graph.OutputNode):
        op_name = graph.op_full_name(node.from_op)
        inputs = {
            k: mapped_fn_to_arrow(arrow_table, i)
            for k, i in node.from_op.inputs.items()
        }
        if op_name == "pick":
            return inputs["obj"]._get_col(inputs["key"])
        elif op_name == "typedDict-pick":
            return inputs["self"]._get_col(inputs["key"])
        elif op_name == "dict":
            for k, v in inputs.items():
                if isinstance(v, ArrowArrayVectorizer):
                    inputs[k] = v.arr
            return pa.table(inputs)
        elif op_name == "merge":
            lhs = inputs["lhs"]
            rhs = inputs["rhs"]
            t = rhs
            for col_name, column in zip(lhs.column_names, lhs.columns):
                t.append_column(col_name, column)
            return t
        op_def = registry_mem.memory_registry.get_op(op_name)
        if list(inputs.keys())[0] == "self" and isinstance(
            list(inputs.values())[0], list
        ):
            import copy

            row_inputs = copy.copy(inputs)
            res = []
            for row in list(inputs.values())[0]:
                row_inputs["self"] = row
                res.append(op_def.resolve_fn(**row_inputs))
            return ArrowArrayVectorizer(pa.array(res))
        result = op_def.resolve_fn(**inputs)
        if isinstance(node.type, types.ObjectType):
            cols = {}
            for k in node.type.property_types():
                cols[k] = getattr(result, k)
                if isinstance(cols[k], ArrowArrayVectorizer):
                    cols[k] = cols[k].arr
            return pa.table(cols)
        return result
    elif isinstance(node, graph.VarNode):
        if node.name == "row":
            if isinstance(arrow_table, ArrowWeaveList) and (
                isinstance(arrow_table._arrow_data, pa.ChunkedArray)
                or isinstance(arrow_table._arrow_data, pa.Array)
            ):
                return ArrowArrayVectorizer(arrow_table._arrow_data)

            return ArrowArrayVectorizer(arrow_table)
        elif node.name == "index":
            return np.arange(arrow_table._count())
        raise Exception("unhandled var name", node.name)


def arrow_type_to_weave_type(pa_type) -> types.Type:
    if pa_type == pa.string():
        return types.String()
    elif pa_type == pa.int64():
        return types.Int()
    elif pa_type == pa.float64():
        return types.Float()
    elif pa_type == pa.bool_():
        return types.Boolean()
    elif pa.types.is_list(pa_type):
        return types.List(arrow_type_to_weave_type(pa_type.value_field.type))
    elif pa.types.is_struct(pa_type):
        return types.TypedDict(
            {f.name: arrow_type_to_weave_type(f.type) for f in pa_type}
        )
    raise errors.WeaveTypeError(
        "Type conversion not implemented for arrow type: %s" % pa_type
    )


@dataclasses.dataclass
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
            return pq.read_table(f)["arr"]


@dataclasses.dataclass
class ArrowTableType(types.Type):
    instance_classes = pa.Table
    name = "ArrowTable"

    object_type: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj: pa.Table):
        obj_prop_types = {}
        for field in obj.schema:
            obj_prop_types[field.name] = arrow_type_to_weave_type(field.type)
        return cls(types.TypedDict(obj_prop_types))

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.parquet", binary=True) as f:
            return pq.read_table(f)


_pick_output_type = list_.make_pick_output_type("self")


def rewrite_weavelist_refs(arrow_data, object_type, artifact):
    # TODO: Handle unions

    if isinstance(object_type, types.TypedDict) or isinstance(
        object_type, types.ObjectType
    ):
        prop_types = object_type.property_types
        if callable(prop_types):
            prop_types = prop_types()
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
    elif isinstance(object_type, types.UnionType):
        non_none_members = [
            m for m in object_type.members if not isinstance(m, types.NoneType)
        ]
        if len(non_none_members) > 1:
            raise errors.WeaveInternalError(
                "Unions not fully supported yet in Weave arrow"
            )
        return rewrite_weavelist_refs(arrow_data, types.non_none(object_type), artifact)
    else:
        if isinstance(object_type, types.BasicType):
            return arrow_data

        # # We have a column of refs
        from .. import refs

        new_refs = []
        for ref_str in arrow_data:
            ref_str = ref_str.as_py()
            if ":" in ref_str:
                new_refs.append(ref_str)
            else:
                ref = refs.Ref.from_local_ref(artifact, ref_str, object_type)
                new_refs.append(str(ref.uri))
        return pa.array(new_refs)


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
        from .. import refs

        new_refs = []
        for ref_str_list in arrow_data:
            ref_str_list = ref_str_list.as_py()
            new_ref_str_list = []
            for ref_str in ref_str_list:
                if ":" in ref_str:
                    new_ref_str_list.append(ref_str)
                    # ref = uris.WeaveURI.parse(ref_str).to_ref()
                else:
                    ref = refs.LocalArtifactRef.from_local_ref(
                        artifact, ref_str, object_type
                    )
                    new_ref_str_list.append(str(ref.uri))
            new_refs.append(new_ref_str_list)
        return pa.array(new_refs)


@dataclasses.dataclass
class ArrowTableGroupByType(types.Type):
    name = "ArrowTableGroupBy"

    object_type: types.Type = types.Any()
    key: types.String = types.String()

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
                "_table": types.union(ArrowTableType(), ArrowArrayType()),
                "_groups": types.union(ArrowTableType(), ArrowArrayType()),
                "_group_keys": types.List(types.String()),
                "object_type": types.Type(),
                "key_type": types.Type(),
            }
        )
        from .. import mappers_python

        serializer = mappers_python.map_to_python(type_of_d, artifact)
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.ArrowTableGroupBy.json") as f:
            json.dump(result_d, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.ArrowTableGroupBy.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_table": types.union(ArrowTableType(), ArrowArrayType()),
                "_groups": types.union(ArrowTableType(), ArrowArrayType()),
                "_group_keys": types.List(types.String()),
                "object_type": types.Type(),
                "key_type": types.Type(),
            }
        )
        from .. import mappers_python

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
        from .. import mappers_arrow

        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)

    @op()
    def count(self) -> int:
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
        calls = []
        for i in range(len(self._groups)):
            row = self.__getitem__.resolve_fn(self, i)
            calls.append(
                weave_internal.call_fn(
                    map_fn,
                    {
                        "row": graph.ConstNode(types.Any(), row),
                        "index": graph.ConstNode(types.Number(), i),
                    },
                )
            )
        result = weave_internal.use_internal(calls)
        return result


ArrowTableGroupByType.instance_classes = ArrowTableGroupBy
ArrowTableGroupByType.instance_class = ArrowTableGroupBy


# It seems like this should inherit from types.ListType...

# Alright. The issue is...
#   we're saving ArrowWeaveList inside of a Table object.
#   so we're using mappers to save ArrowWeaveList instead of the custom
#   save_instance implementation below.
#
# What we actually want here:
#   - ArrowWeaveList can be represented as a TypedDict, so we want to
#     convert to that so it can be nested (like ObjectType)
#   - But we want to provide custom saving logic so we can convert inner refs
#     in a totally custom way.
#   - We have custom type_of_instance logic


@dataclasses.dataclass
class ArrowWeaveListType(types.Type):
    name = "ArrowWeaveList"

    object_type: types.Type = types.Type()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.object_type)

    def save_instance(self, obj, artifact, name):
        # TODO: why do we need this check?
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
                "_arrow_data": types.union(ArrowTableType(), ArrowArrayType()),
                "object_type": types.Type(),
            }
        )
        if hasattr(self, "_key"):
            d["_key"] = obj._key
            type_of_d.property_types["_key"] = self._key

        from .. import mappers_python

        serializer = mappers_python.map_to_python(type_of_d, artifact)
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.ArrowWeaveList.json") as f:
            json.dump(result_d, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.ArrowWeaveList.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(ArrowTableType(), ArrowArrayType()),
                "object_type": types.Type(),
            }
        )
        if hasattr(self, "_key"):
            type_of_d.property_types["_key"] = self._key
        from .. import mappers_python

        mapper = mappers_python.map_from_python(type_of_d, artifact)
        res = mapper.apply(result)
        # TODO: This won't work for Grouped result!
        return ArrowWeaveList(res["_arrow_data"], res["object_type"], artifact)


@weave_class(weave_type=ArrowWeaveListType)
class ArrowWeaveList:
    _arrow_data: typing.Union[pa.Table, pa.ChunkedArray]
    object_type: types.Type

    def to_pylist(self):
        return self._arrow_data.to_pylist()

    def __init__(self, _arrow_data, object_type=None, artifact=None):
        self._arrow_data = _arrow_data
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._arrow_data).object_type
        self._artifact = artifact
        from .. import mappers_arrow

        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)
        # TODO: construct mapper

    # TODO: doesn't belong here
    @op()
    def sum(self) -> float:
        return pa.compute.sum(self._arrow_data)

    def _count(self):
        return len(self._arrow_data)

    @op()
    def count(self) -> int:
        return self._count()

    def _get_col(self, name):
        from .. import mappers_python

        col = self._arrow_data[name]
        col_mapper = self._mapper._property_serializers[name]
        if isinstance(col_mapper, mappers_python.DefaultFromPy):
            return [col_mapper.apply(i.as_py()) for i in col]
        return col_mapper.apply(col)

    def _index(self, index):
        try:
            row = self._arrow_data.slice(index, 1)
        except IndexError:
            return None
        res = self._mapper.apply(row.to_pylist()[0])
        return res

    @op(output_type=lambda input_types: input_types["self"].object_type)
    def __getitem__(self, index: int):
        return self._index(index)

    @op(output_type=_pick_output_type)
    def pick(self, key: str):
        # return self._table[key]
        # TODO: Don't do to_pylist() here! Stay in arrow til as late
        #     as possible

        object_type = self.object_type
        if isinstance(object_type, types.TypedDict):
            col_type = object_type.property_types[key]
        elif isinstance(object_type, types.ObjectType):
            col_type = object_type.property_types()[key]
        else:
            raise errors.WeaveInternalError(
                "unexpected type for pick: %s" % object_type
            )

        return ArrowWeaveList(self._arrow_data[key], col_type, self._artifact)

    @op(
        input_type={
            "self": ArrowWeaveListType(),
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type, "index": types.Int()},
                types.Any(),
            ),
        },
        output_type=lambda input_types: ArrowWeaveListType(
            input_types["map_fn"].output_type
        ),
    )
    def map(self, map_fn):
        res = mapped_fn_to_arrow(self, map_fn)
        if isinstance(res, ArrowArrayVectorizer):
            res = res.arr
        return ArrowWeaveList(res, map_fn.type, self._artifact)

    @op(
        input_type={
            "self": ArrowWeaveListType(ArrowTableType(types.Any())),
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: ArrowTableGroupByType(
            input_types["self"].object_type, input_types["group_by_fn"].output_type
        ),
    )
    def groupby(self, group_by_fn):
        if isinstance(self._arrow_data, pa.ChunkedArray):
            return self._groupby_table(
                pa.table({"self": self._arrow_data}), group_by_fn
            )
        else:
            return self._groupby_table(self._arrow_data, group_by_fn)

    def _groupby_table(self, table, group_by_fn):
        group_table = mapped_fn_to_arrow(self, group_by_fn)
        if isinstance(group_table, ArrowArrayVectorizer):
            group_table = group_table.arr
        if isinstance(group_table, pa.Table):
            group_cols = group_table.column_names
        elif isinstance(group_table, pa.ChunkedArray):
            group_table = pa.table({"group_key": group_table})
            group_cols = ["group_key"]
        else:
            raise errors.WeaveInternalError(
                "Arrow groupby not yet support for map result: %s" % type(group_table)
            )
        group_table = group_table.append_column(
            "_index", pa.array(np.arange(len(group_table)))
        )
        grouped = group_table.group_by(group_cols)
        agged = grouped.aggregate([("_index", "list")])
        return ArrowTableGroupBy(
            table,
            agged,
            group_cols,
            self.object_type,
            group_by_fn.type,
            self._artifact,
        )

    @op(output_type=lambda input_types: input_types["self"])
    def offset(self, offset: int):
        return ArrowWeaveList(
            self._arrow_data.slice(offset), self.object_type, self._artifact
        )

    @op(output_type=lambda input_types: input_types["self"])
    def limit(self, limit: int):
        return ArrowWeaveList(
            self._arrow_data.slice(0, limit), self.object_type, self._artifact
        )


ArrowWeaveListType.instance_classes = ArrowWeaveList
ArrowWeaveListType.instance_class = ArrowWeaveList


@dataclasses.dataclass
class ArrowTableGroupResultType(ArrowWeaveListType):
    name = "ArrowTableGroupResult"

    _key: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(
            obj.object_type,
            types.TypeRegistry.type_of(obj._key),
        )

    # def property_types(self):
    #     return {
    #         "_arrow_data": types.union(ArrowTableType(), ArrowArrayType()),
    #         "object_type": types.Type(),
    #         "_key": self.key,
    #     }


@weave_class(weave_type=ArrowTableGroupResultType)
class ArrowTableGroupResult(ArrowWeaveList):
    def __init__(self, _arrow_data, _key, object_type=None, artifact=None):
        self._arrow_data = _arrow_data
        self._key = _key
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._table).object_type
        self._artifact = artifact
        from .. import mappers_arrow

        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)

    @op(output_type=lambda input_types: input_types["self"]._key)
    def key(self):
        return self._key


ArrowTableGroupResultType.instance_classes = ArrowTableGroupResult
ArrowTableGroupResultType.instance_class = ArrowTableGroupResult


def dataframe_to_arrow(df):
    return ArrowWeaveList(pa.Table.from_pandas(df))
