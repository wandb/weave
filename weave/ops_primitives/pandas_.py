from dataclasses import dataclass
import typing
import json
import math
import pandas
import errors
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import numpy

from ..api import op, weave_class
from .. import weave_types as types
from . import list_
from .. import graph

# Hack hack hack
# TODO: we can do this with Weave instead of writing a giant switch statement
#   (opNumberGreater can operate on Dataframe)
def filter_fn_to_pandas_filter(df, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        op_name = graph.opname_without_version(filter_fn_node.from_op)
        if op_name == "number-greater":
            return filter_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["lhs"]
            ) > filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["rhs"])
        if op_name == "pick":
            return filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["obj"])[
                filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])
            ]
        raise Exception("unhandled op name", op_name)
    elif isinstance(filter_fn_node, graph.VarNode):
        if filter_fn_node.name == "row":
            return df
        raise Exception("unhandled var name")


def groupby_fn_to_pandas_filter(df, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        op_name = graph.opname_without_version(filter_fn_node.from_op)
        if op_name == "number-greater":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["lhs"]
            ) > groupby_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["rhs"])
        elif op_name == "pick":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["obj"]
            )[groupby_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])]
        elif op_name == "dict":
            # Return as list... though we'll need to keep track of that
            # we did this and remap the result keys.
            # TODO
            return list(
                groupby_fn_to_pandas_filter(df, n)
                for n in filter_fn_node.from_op.inputs.values()
            )
        raise Exception("unhandled op name", op_name)
    elif isinstance(filter_fn_node, graph.VarNode):
        if filter_fn_node.name == "row":
            return df
        raise Exception("unhandled var name")


def numpy_val_to_python(val):
    if isinstance(val, numpy.integer):
        return int(val)
    elif isinstance(val, float):
        if math.isnan(val):
            return "nan"
        return float(val)
    return val


class DataFrameType(types.Type):
    instance_classes = pandas.DataFrame
    name = "dataframe"

    object_type: types.Type

    def __init__(self, object_type):
        self.object_type = object_type

    def __str__(self):
        return "<DataFrameType %s>" % self.object_type

    def _to_dict(self):
        return {"objectType": self.object_type.to_dict()}

    @classmethod
    def from_dict(cls, d):
        return cls(types.TypeRegistry.type_from_dict(d["objectType"]))

    @classmethod
    def type_of_instance(cls, obj):
        obj_prop_types = {}
        for col_name, dtype in obj.dtypes.items():
            if dtype == np.dtype("object"):
                weave_type = types.String()
            elif dtype == np.dtype("int64"):
                weave_type = types.Int()
            elif dtype == np.dtype("float64"):
                weave_type = types.Float()
            else:
                raise errors.WeaveTypeError(
                    "Type conversion not implemented for dtype: %s" % dtype
                )
            obj_prop_types[col_name] = weave_type
        return cls(types.TypedDict(obj_prop_types))

    def save_instance(self, obj, artifact, name):
        table = pa.Table.from_pandas(obj)
        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            pq.write_table(table, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.parquet", binary=True) as f:
            table = pq.read_table(f)
        return table.to_pandas()


class DataFrameTableType(types.ObjectType):
    name = "dataframeTable"

    type_vars = {"_df": DataFrameType(types.Any())}

    def __init__(self, _df=DataFrameType(types.Any())):
        self._df = _df

    def property_types(self):
        return {
            "_df": self._df,
        }

    @property
    def object_type(self):
        return self._df.object_type


def index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["self"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.object_type
    else:
        return self_type.object_type


def pick_output_type(input_types):
    if not isinstance(input_types["key"], types.Const):
        return types.UnknownType()
    key = input_types["key"].val
    prop_type = input_types["self"]._df.object_type.property_types.get(key)
    if prop_type is None:
        return types.Invalid()
    return prop_type


@weave_class(weave_type=DataFrameTableType)
class DataFrameTable:
    _df: pandas.DataFrame

    def __init__(self, _df):
        self._df = _df

    def _count(self):
        return len(self._df)

    @op()
    def count(self) -> int:
        return self._count()

    def _index(self, index):
        try:
            # TODO
            # to_json and back to dict then back to json :(
            return json.loads(self._df.iloc[index].to_json())
        except IndexError:
            return None

    @op(output_type=index_output_type)
    def __getitem__(self, index: int):
        return self._index(index)

    @op(output_type=pick_output_type)
    def pick(self, key: str):
        return self._df[key]

    @op(output_type=lambda input_types: input_types["self"])
    def filter(self, filter_fn: typing.Any):
        return DataFrameTable(self._df[filter_fn_to_pandas_filter(self._df, filter_fn)])

    @op(output_type=lambda input_types: types.List(input_types["self"].object_type))
    def map(self, map_fn: typing.Any):
        self_list = []
        for i in range(self._count()):
            self_list.append(self._index(i))
        res = list_.List.map.op_def.resolve_fn(self_list, map_fn)
        return res

    @op(
        output_type=lambda input_types: types.List(
            list_.GroupResultType(types.List(input_types["self"].object_type))
        ),
    )
    def groupby(self, group_by_fn: typing.Any):
        group_keys = None
        if group_by_fn.from_op.name == "dict":
            group_keys = list(group_by_fn.from_op.inputs.keys())
        pandas_gb = groupby_fn_to_pandas_filter(self._df, group_by_fn)
        grouped = self._df.groupby(pandas_gb)
        df = grouped.agg(list)
        result = []
        for i in range(len(df)):
            row = df.iloc[i]
            row_result = []
            for row_val in zip(*row.values):
                row_result.append(dict(zip(df.keys(), row_val)))
            group_key_vals = row.name
            if isinstance(group_key_vals, tuple):
                group_key_vals = [numpy_val_to_python(v) for v in group_key_vals]
            else:
                group_key_vals = numpy_val_to_python(group_key_vals)
            if group_keys is None:
                group_key = group_key_vals
            else:
                if not isinstance(group_key_vals, tuple):
                    group_key_vals = (group_key_vals,)
                group_key = dict(zip(group_keys, group_key_vals))
            result.append(list_.GroupResult(row_result, group_key))
        return result


DataFrameTableType.instance_classes = DataFrameTable
DataFrameTableType.instance_class = DataFrameTable


@op(
    name="file-pandasreadcsv",
    input_type={"file": types.FileType()},
    # TODO: This needs to be implemented. It needs to read the file to
    #     determine what the type will be.
    output_type=DataFrameTableType(DataFrameType(types.TypedDict({}))),
)
def file_pandasreadcsv(file):
    local_path = file.get_local_path()
    # Warning, terrible hack to make demo work
    try:
        return DataFrameTable(pandas.read_csv(local_path, low_memory=False))
    except:
        return DataFrameTable(
            pandas.read_csv(local_path, delimiter=";", low_memory=False)
        )
