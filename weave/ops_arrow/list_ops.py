import pyarrow as pa
import pyarrow.compute as pc
import numpy as np
import typing

from ..api import op
from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from ..language_features.tagging import (
    tagged_value_type,
    tagged_value_type_helpers,
)
from collections import defaultdict
from .. import op_args
from ..ops_primitives import list_ as primitive_list
from .. import op_def

from .arrow import ArrowWeaveListType, arrow_as_array, offsets_starting_at_zero
from .list_ import (
    ArrowWeaveList,
    safe_pa_concat_arrays,
)
from . import arrow_tags
from .vectorize import _apply_fn_node_with_tag_pushdown
from . import convert
from .util import _to_compare_safe_call
from .constructors import (
    vectorized_container_constructor_preprocessor,
    vectorized_input_types,
)


FLATTEN_DELIMITER = "➡️"

NestedTableColumns = dict[str, typing.Union[dict, pa.ChunkedArray]]


def unflatten_structs_in_flattened_table(table: pa.Table) -> pa.Table:
    """take a table with column names like {a.b.c: [1,2,3], a.b.d: [4,5,6], a.e: [7,8,9]}
    and return a struct array with the following structure:
    [ {a: {b: {c: 1, d: 4}, e: 7}}, {a: {b: {c: 2, d: 5}, e: 8}}, {a: {b: {c: 3, d: 6}, e: 9}} ]"""

    def recursively_build_nested_struct_array(
        columns: dict[str, pa.Array]
    ) -> pa.StructArray:
        result: NestedTableColumns = defaultdict(lambda: {})
        for colname in columns:
            spl_colname = colname.split(FLATTEN_DELIMITER)
            prefix = spl_colname[0]
            suffix = FLATTEN_DELIMITER.join(spl_colname[1:])
            if suffix:
                result[prefix][suffix] = columns[colname]
            else:
                result[prefix] = columns[colname]

        for colname in result:
            if isinstance(result[colname], dict):
                result[colname] = recursively_build_nested_struct_array(result[colname])

        names: list[str] = []
        arrays: list[pa.ChunkedArray] = []

        for name, array in result.items():
            names.append(name)
            arrays.append(array)

        return pa.StructArray.from_arrays(arrays, names)

    recurse_input = {
        colname: table[colname].combine_chunks() for colname in table.column_names
    }

    sa = recursively_build_nested_struct_array(recurse_input)

    names: list[str] = []
    chunked_arrays: list[pa.ChunkedArray] = []

    for field in sa.type:
        names.append(field.name)
        chunked_arrays.append(pa.chunked_array(sa.field(field.name)))

    return pa.Table.from_arrays(chunked_arrays, names=names)


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


def unzip_struct_array(arr: pa.ChunkedArray) -> pa.Table:
    flattened = _recursively_flatten_structs_in_array(arr.combine_chunks(), "")
    return pa.table(flattened)


@op(
    name="ArrowWeaveList-map",
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
    res = _apply_fn_node_with_tag_pushdown(self, map_fn)
    return res


def _map_each_function_type(input_types: dict[str, types.Type]) -> types.Type:
    base_op_fn_type = primitive_list._map_each_function_type(
        {"arr": input_types["self"]}
    )
    base_op_fn_type.input_types["self"] = ArrowWeaveListType(
        typing.cast(types.List, input_types["self"]).object_type
    )
    return base_op_fn_type


def _map_each_output_type(input_types: dict[str, types.Type]):
    base_output_type = primitive_list._map_each_output_type(
        {"arr": input_types["self"], "mapFn": input_types["map_fn"]}
    )
    return ArrowWeaveListType(base_output_type.object_type)


def _map_each(self: ArrowWeaveList, fn):
    if types.List().assign_type(self.object_type):
        as_array = arrow_as_array(self._arrow_data)
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            as_array = as_array.field("_value")

        offsets = offsets_starting_at_zero(as_array)
        flattened = as_array.flatten()
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            new_object_type = typing.cast(
                types.List, self.object_type.value
            ).object_type
        else:
            new_object_type = typing.cast(types.List, self.object_type).object_type

        new_awl: ArrowWeaveList = ArrowWeaveList(
            flattened,
            new_object_type,
            self._artifact,
        )

        mapped = _map_each(new_awl, fn)
        reshaped_arrow_data: ArrowWeaveList = ArrowWeaveList(
            pa.ListArray.from_arrays(offsets, mapped._arrow_data),
            types.List(fn.type),
            self._artifact,
        )

        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return arrow_tags.awl_add_arrow_tags(
                reshaped_arrow_data,
                self._arrow_data.field("_tag"),
                self.object_type.tag,
            )
        return reshaped_arrow_data
    return _apply_fn_node_with_tag_pushdown(self, fn)


@op(
    name="ArrowWeaveList-mapEach",
    input_type={
        "self": ArrowWeaveListType(),
        "map_fn": _map_each_function_type,
    },
    output_type=_map_each_output_type,
)
def map_each(self, map_fn):
    return _map_each(self, map_fn)


def _slow_arrow_or_list_ranking(
    awl_or_list: typing.Union["ArrowWeaveList", list], col_dirs
):
    # This function is used to handle cases where the sort function will not play nicely with AWL
    if isinstance(awl_or_list, ArrowWeaveList):
        awl_or_list = awl_or_list.to_pylist_notags()
    py_columns: dict[str, list] = {}
    for row in awl_or_list:
        for col_ndx, cell in enumerate(row):
            col_name = f"c_{col_ndx}"
            if col_name not in py_columns:
                py_columns[col_name] = []
            if not isinstance(cell, (str, int, float)):
                # This is the crazy line - we need to convert it to something sane
                # Maybe there is a generic way to do this w/.o str conversion?
                cell = str(cell)
            py_columns[col_name].append(cell)
    table = pa.table(py_columns)
    return pc.sort_indices(
        table,
        sort_keys=[
            (col_name, "ascending" if dir_name == "asc" else "descending")
            for col_name, dir_name in zip(py_columns.keys(), col_dirs)
        ],
        null_placement="at_end",
    )


def _arrow_sort_ranking_to_indicies(sort_ranking, col_dirs):
    flattened = sort_ranking._arrow_data_asarray_no_tags().flatten()

    columns = (
        []
    )  # this is intended to be a pylist and will be small since it is number of sort fields
    col_len = len(sort_ranking._arrow_data)
    dir_len = len(col_dirs)
    col_names = [str(i) for i in range(dir_len)]
    order = [
        (col_name, "ascending" if dir_name == "asc" else "descending")
        for col_name, dir_name in zip(col_names, col_dirs)
    ]
    # arrow data: (col_len x dir_len)
    # [
    #    [d00, d01]
    #    [d10, d11]
    #    [d20, d21]
    #    [d30, d31]
    # ]
    #
    # Flatten
    # [d00, d01, d10, d11, d20, d21, d30, d31]
    #
    # col_x = [d0x, d1x, d2x, d3x]
    # .         i * dir_len + x
    #
    #
    for i in range(dir_len):
        take_array = [j * dir_len + i for j in range(col_len)]
        if len(take_array) > 0:
            columns.append(pc.take(flattened, pa.array(take_array)))
        else:
            columns.append(flattened)
    table = pa.Table.from_arrays(columns, names=col_names)
    return pc.sort_indices(table, order, null_placement="at_end")


@op(
    name="ArrowWeaveList-sort",
    input_type={
        "self": ArrowWeaveListType(),
        "comp_fn": lambda input_types: types.Function(
            {"row": input_types["self"].object_type, "index": types.Int()},
            types.Any(),
        ),
        "col_dirs": types.List(types.String()),
    },
    output_type=lambda input_types: input_types["self"],
)
def sort(self, comp_fn, col_dirs):
    ranking = _apply_fn_node_with_tag_pushdown(self, comp_fn)
    if not types.optional(types.union(types.String(), types.Number())).assign_type(
        comp_fn.type.object_type
    ):
        # Protection! Arrow cannot handle executing a sort on non-primitives.
        # We will defer to a slower python implementation in these cases.
        indicies = _slow_arrow_or_list_ranking(ranking, col_dirs)
    else:
        indicies = _arrow_sort_ranking_to_indicies(ranking, col_dirs)
    return ArrowWeaveList(
        pc.take(self._arrow_data, indicies), self.object_type, self._artifact
    )


@op(
    name="ArrowWeaveList-filter",
    input_type={
        "self": ArrowWeaveListType(),
        "filter_fn": lambda input_types: types.Function(
            {"row": input_types["self"].object_type, "index": types.Int()},
            types.optional(types.Boolean()),
        ),
    },
    output_type=lambda input_types: input_types["self"],
)
def filter(self, filter_fn):
    mask = _apply_fn_node_with_tag_pushdown(self, filter_fn)
    arrow_mask = mask._arrow_data_asarray_no_tags()
    arrow_mask = pc.fill_null(arrow_mask.cast(pa.bool_()), False)
    return ArrowWeaveList(
        arrow_as_array(self._arrow_data).filter(arrow_mask),
        self.object_type,
        self._artifact,
    )


def awl_group_by_result_object_type(
    object_type: types.Type, _key: types.Type
) -> tagged_value_type.TaggedValueType:
    return tagged_value_type.TaggedValueType(
        types.TypedDict(
            {
                "groupKey": _key,
            }
        ),
        ArrowWeaveListType(object_type),
    )


def awl_group_by_result_type(
    object_type: types.Type, key_type: types.Type
) -> "ArrowWeaveListType":
    return ArrowWeaveListType(awl_group_by_result_object_type(object_type, key_type))


@op(
    name="ArrowWeaveList-groupby",
    input_type={
        "self": ArrowWeaveListType(),
        "group_by_fn": lambda input_types: types.Function(
            {"row": input_types["self"].object_type}, types.Any()
        ),
    },
    output_type=lambda input_types: awl_group_by_result_type(
        input_types["self"].object_type, input_types["group_by_fn"].output_type
    ),
)
def groupby(self, group_by_fn):
    safe_group_by_fn = _to_compare_safe_call(group_by_fn)
    group_table_awl = _apply_fn_node_with_tag_pushdown(self, safe_group_by_fn)

    if (
        safe_group_by_fn is group_by_fn
    ):  # we want to use `is` here since we want to check for identity
        unsafe_group_table_awl = group_table_awl
    else:
        # This only can happen if `_to_compare_safe_call` modifies something - which
        # in itself only happens if we are grouping by a media asset
        unsafe_group_table_awl = _apply_fn_node_with_tag_pushdown(self, group_by_fn)

    table = self._arrow_data

    group_table = group_table_awl._arrow_data
    group_table_as_array = arrow_as_array(group_table)

    # strip tags recursively so we group on values only
    group_table_as_array_awl = ArrowWeaveList(
        group_table_as_array, group_table_awl.object_type, self._artifact
    )
    group_table_as_array_awl_stripped = (
        group_table_as_array_awl._arrow_data_asarray_no_tags()
    )
    group_table_chunked = pa.chunked_array(
        pa.StructArray.from_arrays(
            [
                group_table_as_array_awl_stripped,
            ],
            names=["group_key"],
        )
    )
    group_table_chunked_unzipped = unzip_struct_array(group_table_chunked)
    group_cols = group_table_chunked_unzipped.column_names

    # Serializing a large arrow table and then reading it back
    # causes it to come back with more than 1 chunk. It seems the aggregation
    # operations don't like this. It will raise a cryptic error about
    # ExecBatches need to have the same link without this combine_chunks line
    # But combine_chunks doesn't seem like the most efficient thing to do
    # either, since it'll have to concatenate everything together.
    # But this fixes the crash for now!
    # TODO: investigate this as we optimize the arrow implementation
    group_table_combined = group_table_chunked_unzipped.combine_chunks()

    group_table_combined_indexed = group_table_combined.append_column(
        "_index", pa.array(np.arange(len(group_table_combined)))
    )
    awl_grouped = group_table_combined_indexed.group_by(group_cols)
    awl_grouped_agg = awl_grouped.aggregate([("_index", "list")])
    awl_grouped_agg_struct = unflatten_structs_in_flattened_table(awl_grouped_agg)

    combined = awl_grouped_agg_struct.column("_index_list").combine_chunks()
    val_lengths = combined.value_lengths()
    flattened_indexes = combined.flatten()
    values = arrow_as_array(table).take(flattened_indexes)
    offsets = np.cumsum(np.concatenate(([0], val_lengths)))
    grouped_results = pa.ListArray.from_arrays(offsets, values)
    grouped_awl = ArrowWeaveList(
        grouped_results, ArrowWeaveListType(self.object_type), self._artifact
    )
    effective_group_key_indexes = flattened_indexes.take(
        pa.array(offsets.tolist()[:-1]).cast(pa.int64())
    )
    effective_group_keys = arrow_as_array(unsafe_group_table_awl._arrow_data).take(
        effective_group_key_indexes
    )
    nested_effective_group_keys = pa.StructArray.from_arrays(
        [effective_group_keys], names=["groupKey"]
    )

    return arrow_tags.awl_add_arrow_tags(
        grouped_awl,
        nested_effective_group_keys,
        types.TypedDict({"groupKey": unsafe_group_table_awl.object_type}),
    )


@op(
    name="ArrowWeaveList-dropna",
    input_type={"self": ArrowWeaveListType()},
    output_type=lambda input_types: ArrowWeaveListType(
        types.non_none(input_types["self"].object_type)
    ),
)
def dropna(self):
    res = pc.drop_null(self._arrow_data)
    return ArrowWeaveList(res, types.non_none(self.object_type), self._artifact)


@op(name="ArrowWeaveList-count")
def count(self: ArrowWeaveList) -> int:
    return self._count()


@op(
    name="ArrowWeaveList-__getitem__",
    output_type=lambda input_types: primitive_list.getitem_output_type(
        {"arr": input_types["self"]}
    ),
)
def index(self: ArrowWeaveList, index: typing.Optional[int]):
    return self._index(index)


@op(name="ArrowWeaveList-offset", output_type=lambda input_types: input_types["self"])
def offset(self: ArrowWeaveList, offset: int):
    return ArrowWeaveList(
        self._arrow_data.slice(offset), self.object_type, self._artifact
    )


@op(name="ArrowWeaveList-limit", output_type=lambda input_types: input_types["self"])
def limit(self: ArrowWeaveList, limit: int):
    return self._limit(limit)


@op(
    name="ArrowWeaveList-unnest",
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
    new_obj_prop_types = {}
    for k, v_type in self.object_type.property_types.items():
        if types.is_list_like(v_type):
            list_cols.append(k)
            new_obj_prop_types[k] = op_def.normalize_type(v_type.object_type)
        else:
            new_obj_prop_types[k] = v_type
    if not list_cols:
        return self

    if isinstance(self._arrow_data, pa.StructArray):
        rb = pa.RecordBatch.from_struct_array(
            self._arrow_data
        )  # this pivots to columnar layout
        arrow_obj = pa.Table.from_batches([rb])
    else:
        arrow_obj = self._arrow_data

    # Split out tagged list columns into separate columns
    tag_col_name_map = {}
    for col in list_cols:
        col_data = arrow_obj.column(col).combine_chunks()
        if isinstance(
            self.object_type.property_types[col], tagged_value_type.TaggedValueType
        ):
            tag_col_name = f"{col}__tag__"
            tag_col_name_map[col] = tag_col_name

            col_tags = col_data.field("_tag")
            col_values = col_data.field("_value")

            arrow_obj = arrow_obj.remove_column(arrow_obj.column_names.index(col))
            arrow_obj = arrow_obj.append_column(tag_col_name, col_tags)
            arrow_obj = arrow_obj.append_column(col, col_values)

    # todo: make this more efficient. we shouldn't have to convert back and forth
    # from the arrow in-memory representation to pandas just to call the explode
    # function. but there is no native pyarrow implementation of this
    exploded_table = pa.Table.from_pandas(
        df=arrow_obj.to_pandas().explode(list_cols), preserve_index=False
    )

    # Reconstruct the tagged list columns
    for col in exploded_table.column_names:
        if col in tag_col_name_map:
            tag_col_name = tag_col_name_map[col]
            val_col = exploded_table.column(col).combine_chunks()
            tag_col = exploded_table.column(tag_col_name).combine_chunks()
            combined_col = arrow_tags.direct_add_arrow_tags(val_col, tag_col)
            exploded_table = exploded_table.remove_column(
                exploded_table.column_names.index(tag_col_name)
            )
            exploded_table = exploded_table.remove_column(
                exploded_table.column_names.index(col)
            )
            exploded_table = exploded_table.append_column(col, combined_col)

    return ArrowWeaveList(
        exploded_table,
        types.TypedDict(new_obj_prop_types),
        self._artifact,
    )


def _concat_output_type(input_types: typing.Dict[str, types.List]) -> types.Type:
    arr_type: types.List = input_types["arr"]
    inner_type = types.non_none(arr_type.object_type)

    if isinstance(inner_type, types.UnionType):
        if not all(types.is_list_like(t) for t in inner_type.members):
            raise ValueError(
                "opConcat: expected all members of inner type to be list-like"
            )

        new_union_members = [
            typing.cast(
                ArrowWeaveListType,
                tagged_value_type_helpers.push_down_tags_from_container_type_to_element_type(
                    t
                ),
            ).object_type
            for t in inner_type.members
        ]

        # merge the types into a single type
        new_inner_type = new_union_members[0]
        for t in new_union_members[1:]:
            new_inner_type = types.merge_types(new_inner_type, t)

        return ArrowWeaveListType(new_inner_type)

    elif isinstance(inner_type, tagged_value_type.TaggedValueType):
        inner_type_value = inner_type.value
        inner_type_tag = inner_type.tag
        inner_type_value_inner_type = typing.cast(
            ArrowWeaveListType, inner_type_value
        ).object_type

        return ArrowWeaveListType(
            tagged_value_type.TaggedValueType(
                inner_type_tag, inner_type_value_inner_type
            )
        )

    return inner_type


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
        return convert.to_arrow([])
    elif len(arr) == 1:
        return arrow_tags.pushdown_list_tags(arr[0])

    res = arr[0]
    res = typing.cast(ArrowWeaveList, res)
    res = arrow_tags.pushdown_list_tags(res)

    for i in range(1, len(arr)):
        tagged = arrow_tags.pushdown_list_tags(arr[i])
        res = res.concatenate(tagged)
    return res


# # Putting this here instead of in number b/c it is just a map function
# bin_type = types.TypedDict({"start": types.Number(), "stop": types.Number()})


# @op(
#     name="ArrowWeaveListNumber-bin",
#     input_type={
#         "val": ArrowWeaveListType(types.optional(types.Number())),
#         "binFn": types.Function(
#             {"row": types.Number()},
#             types.TypedDict({"start": types.Number(), "stop": types.Number()}),
#         ),
#     },
#     output_type=ArrowWeaveListType(types.optional(bin_type)),
# )
# def number_bin(val, binFn):
#     tagged_awl = pushdown_list_tags(val)
#     res = _apply_fn_node(tagged_awl, binFn)
#     return res


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
    return arrow_tags.awl_add_arrow_tags(
        arr,
        tag_array,
        types.TypedDict({"indexCheckpoint": types.Int()}),
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
    concatted = safe_pa_concat_arrays(res.arrays)

    if len(concatted) == 0:
        values = concatted
    else:
        take_ndxs = []
        for row_ndx in range(res.max_len):
            take_ndxs.extend([row_ndx + i * res.max_len for i in range(len(e))])
        values = concatted.take(pa.array(take_ndxs))
    offsets = pa.array(
        [i * len(e) for i in range(res.max_len)] + [res.max_len * len(e)]
    )
    return ArrowWeaveList(
        pa.ListArray.from_arrays(offsets, values),
        types.List(types.union(*element_types)),
        res.artifact,
    )


def vectorized_arrow_pick_output_type(input_types):
    inner_type = types.union(*list(input_types["self"].property_types.values()))
    if isinstance(input_types["key"], ArrowWeaveListType):
        return ArrowWeaveListType(inner_type)
    else:
        return types.List(inner_type)


# Combining both list and arrow into the same op since dispatch operates on the
# first input, and the difference would only be in the second input
@op(
    name="_vectorized_list_like-pick",
    input_type={
        "self": types.TypedDict({}),
        "key": types.union(
            ArrowWeaveListType(types.optional(types.String())),
            types.List(types.optional(types.String())),
        ),
    },
    output_type=vectorized_arrow_pick_output_type,
)
def vectorized_arrow_pick(self, key):
    if isinstance(key, list):
        return [self.get(k, None) if k != None else None for k in key]
    de = arrow_as_array(key._arrow_data_asarray_no_tags()).dictionary_encode()
    new_dictionary = pa.array(
        [self.get(key, None) for key in de.dictionary.to_pylist()]
    )
    new_indices = de.indices
    new_array = pa.DictionaryArray.from_arrays(new_indices, new_dictionary)
    result = new_array.dictionary_decode()
    return ArrowWeaveList(
        result,
    )


@arrow_op(
    name="ArrowWeaveList-vectorizedIsNone",
    input_type={"self": ArrowWeaveListType(types.optional(types.Any()))},
    output_type=ArrowWeaveListType(types.Boolean()),
)
def vectorized_is_none(self):
    # Need to break out to python due to this issue we reported
    # https://github.com/apache/arrow/issues/34315
    # TODO: Remove this once the issue is fixed
    # Open PR here: https://github.com/apache/arrow/pull/34408
    if isinstance(self._arrow_data, pa.UnionArray):
        return ArrowWeaveList(
            pa.array([x == None for x in self._arrow_data.to_pylist()]),
            types.Boolean(),
            self._artifact,
        )
    return ArrowWeaveList(
        self._arrow_data.is_null(),
        types.Boolean(),
        self._artifact,
    )
