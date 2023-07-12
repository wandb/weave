import dataclasses
import json
import math
import pandas
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import numpy

from ..api import op, weave_class
from .. import box
from .. import weave_types as types
from . import list_
from .. import mappers_python
from .. import graph
from .. import errors
from .. import file_base
from ..language_features.tagging import tag_store, tagged_value_type


# Hack hack hack
# TODO: we can do this with Weave instead of writing a giant switch statement
#   (opNumberGreater can operate on Dataframe)
def filter_fn_to_pandas_filter(df, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        op_name = graph.op_full_name(filter_fn_node.from_op)
        if op_name == "number-greater":
            return filter_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["lhs"]
            ) > filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["rhs"])
        elif op_name == "pick":
            return filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["obj"])[
                filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])
            ]
        elif op_name == "typedDict-pick":
            return filter_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["self"]
            )[filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])]
        raise Exception("unhandled op name", op_name)
    elif isinstance(filter_fn_node, graph.VarNode):
        if filter_fn_node.name == "row":
            return df
        raise Exception("unhandled var name")


def groupby_fn_to_pandas_filter(df, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        op_name = graph.op_full_name(filter_fn_node.from_op)
        if op_name == "number-greater":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["lhs"]
            ) > groupby_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["rhs"])
        elif op_name == "pick":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["obj"]
            )[groupby_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])]
        elif op_name == "typedDict-pick":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["self"]
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


@dataclasses.dataclass(frozen=True)
class DataFrameType(types.Type):
    instance_classes = pandas.DataFrame
    name = "dataframe"

    object_type: types.Type = types.Any()

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
            elif dtype == np.dtype("bool"):
                weave_type = types.Boolean()

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


@dataclasses.dataclass(frozen=True)
class DataFrameTableType(types.Type):
    _base_type = types.List
    name = "dataframeTable"

    object_type: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.object_type)

    def save_instance(self, obj, artifact, name):
        d = {"_df": obj._df, "object_type": obj.object_type}
        type_of_d = types.TypedDict(
            {
                "_df": DataFrameType(),
                "object_type": types.TypeType(),
            }
        )

        serializer = mappers_python.map_to_python(type_of_d, artifact)
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.DataFrameTable.json") as f:
            json.dump(result_d, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.DataFrameTable.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_df": DataFrameType(),
                "object_type": types.TypeType(),
            }
        )
        mapper = mappers_python.map_from_python(type_of_d, artifact)
        res = mapper.apply(result)
        return self.instance_class(artifact=artifact, **res)


def index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["self"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.object_type
    else:
        return self_type.object_type


@weave_class(weave_type=DataFrameTableType)
class DataFrameTable:
    _df: pandas.DataFrame
    object_type: types.Type

    def __init__(self, _df, object_type=None, artifact=None):
        self._df = _df
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._df).object_type

    def __iter__(self):
        # Iter is implemented to make list_indexCheckpoint work, which
        # currently expects to be able to iterate. Iteration gets stuck in an
        # infinite loop without implementing __iter__ here, since Python will
        # default to using __getitem__, which is a lazy Weave op.
        # TODO: When we fix arrow/vectorization and tagging, we'll have to
        # fix this.
        for row in self._df.itertuples():
            yield row._asdict()

    def _count(self):
        return len(self._df)

    def __len__(self):
        return self._count()

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

    # @op(output_type=mapped_pick_output_type)
    # def pick(self, key: str):
    #     return self._df[key]

    @op(
        input_type={
            "filterFn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def filter(self, filterFn):
        return DataFrameTable(self._df[filter_fn_to_pandas_filter(self._df, filterFn)])

    @op(
        input_type={
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(input_types["self"].object_type),
    )
    def map(self, map_fn):
        self_list = []
        for i in range(self._count()):
            self_list.append(self._index(i))
        return list_.List.map.resolve_fn(self_list, map_fn)

    @op(
        input_type={
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict(
                    {
                        "groupKey": input_types["group_by_fn"].output_type,
                    }
                ),
                types.List(input_types["self"].object_type),
            )
        ),
    )
    def groupby(self, group_by_fn):
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
            item = box.box(row_result)
            tag_store.add_tags(item, {"groupKey": group_key})
            result.append(item)
        return result


DataFrameTableType.instance_classes = DataFrameTable
DataFrameTableType.instance_class = DataFrameTable


def _pd_dtype_to_weave(dtype):
    if dtype.name == "object" or dtype.name == "category":
        return types.String()
    elif dtype.name == "int64":
        return types.Int()
    elif dtype.name == "float64":
        return types.Float()
    elif dtype.name == "bool":
        return types.Boolean()
    elif dtype.name == "datetime64" or dtype.name == "timedelta[ns]":
        return types.Timestamp()
    else:
        raise NotImplementedError("Unsupported dtype: {}".format(dtype))


@op(
    name="file-refine_pandasreadcsv",
    hidden=True,
    input_type={"file": file_base.FileBaseType()},
    output_type=types.TypeType(),
)
def refine_pandasreadcsv(file):
    res = pandasreadcsv.raw_resolve_fn(file)
    columns = res._df.dtypes.index.values.tolist()
    dtypes = res._df.dtypes.values.tolist()
    prop_types = {col: _pd_dtype_to_weave(dtype) for col, dtype in zip(columns, dtypes)}
    return DataFrameTableType(types.TypedDict(prop_types))


@op(
    name="file-pandasreadcsv",
    input_type={"file": file_base.FileBaseType()},
    output_type=DataFrameTableType(),
    refine_output_type=refine_pandasreadcsv,
)
def pandasreadcsv(file):
    local_path = file.get_local_path()
    # Warning, terrible hack to make demo work
    try:
        return DataFrameTable(pandas.read_csv(local_path, low_memory=False))
    except:
        return DataFrameTable(
            pandas.read_csv(local_path, delimiter=";", low_memory=False)
        )
