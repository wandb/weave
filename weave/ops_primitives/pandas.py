import json
import math
import pandas
import numpy

from ..api import op
from .. import weave_types as types
from . import table
from . import file
from .. import graph

# Hack hack hack
# TODO: we can do this with Weave instead of writing a giant switch statement
#   (opNumberGreater can operate on Dataframe)
def filter_fn_to_pandas_filter(df, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        if filter_fn_node.from_op.name == "number-greater":
            return filter_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["lhs"]
            ) > filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["rhs"])
        if filter_fn_node.from_op.name == "pick":
            return filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["obj"])[
                filter_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])
            ]
        raise Exception("unhandled op name", filter_fn_node.from_op.name)
    elif isinstance(filter_fn_node, graph.VarNode):
        if filter_fn_node.name == "row":
            return df
        raise Exception("unhandled var name")


def groupby_fn_to_pandas_filter(df, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        if filter_fn_node.from_op.name == "number-greater":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["lhs"]
            ) > groupby_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["rhs"])
        elif filter_fn_node.from_op.name == "pick":
            return groupby_fn_to_pandas_filter(
                df, filter_fn_node.from_op.inputs["obj"]
            )[groupby_fn_to_pandas_filter(df, filter_fn_node.from_op.inputs["key"])]
        elif filter_fn_node.from_op.name == "dict":
            # Return as list... though we'll need to keep track of that
            # we did this and remap the result keys.
            # TODO
            return list(
                groupby_fn_to_pandas_filter(df, n)
                for n in filter_fn_node.from_op.inputs.values()
            )
        raise Exception("unhandled op name", filter_fn_node.from_op.name)
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


class DataFrame(table.Table):
    _df: pandas.DataFrame

    def __init__(self, df):
        self._df = df

    def _to_list_table(self):
        return table.ListTable([self.index(i) for i in range(self.count())])

    def count(self):
        return len(self._df)

    def index(self, index):
        try:
            # TODO
            # to_json and back to dict then back to json :(
            return json.loads(self._df.iloc[index].to_json())
        except IndexError:
            return None

    def pick(self, key):
        return self._to_list_table().pick(key)

    def map(self, mapFn):
        return self._to_list_table().map(mapFn)

    def filter(self, filterFn):
        return DataFrame(self._df[filter_fn_to_pandas_filter(self._df, filterFn)])

    def groupby(self, groupByFn):
        group_keys = None
        if groupByFn.from_op.name == "dict":
            group_keys = list(groupByFn.from_op.inputs.keys())
        pandas_gb = groupby_fn_to_pandas_filter(self._df, groupByFn)
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
            result.append(table.GroupResult(row_result, group_key))
        return table.ListTable(result)
        # return self._to_list_table().groupby(groupByFn)


@op(
    name="file-pandasreadcsv",
    input_type={"file": types.FileType()},
    # TODO: we should have a DataFrame table that extends Table!
    output_type=types.Table(),
)
def file_pandasreadcsv(file):
    local_path = file.get_local_path()
    # Warning, terrible hack to make demo work
    try:
        return DataFrame(pandas.read_csv(local_path))
    except:
        return DataFrame(pandas.read_csv(local_path, delimiter=";"))
