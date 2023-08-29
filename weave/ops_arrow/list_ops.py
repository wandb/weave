import random
import pyarrow as pa
import pyarrow.compute as pc
import numpy as np
import typing
from builtins import map as builtin_map

from ..api import op, type_of
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
from .list_ import ArrowWeaveList, PathType, is_list_arrowweavelist
from . import arrow_tags
from .vectorize import _apply_fn_node_with_tag_pushdown
from . import convert
from .convert import to_compare_safe
from .constructors import (
    vectorized_container_constructor_preprocessor,
    vectorized_input_types,
)


FLATTEN_DELIMITER = "➡️"

NestedTableColumns = dict[str, typing.Union[dict, pa.ChunkedArray]]


def unflatten_structs_in_flattened_table(table: pa.Table) -> pa.Table:
    """take a table with column names like {a.b.c: [1,2,3], a.b.d: [4,5,6], a.e: [7,8,9]}
    and return a struct array with the following structure:
    [ {a: {b: {c: 1, d: 4}, e: 7}}, {a: {b: {c: 2, d: 5}, e: 8}}, {a: {b: {c: 3, d: 6}, e: 9}} ]
    """

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
            types.List(mapped.object_type),
            self._artifact,
        )

        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return arrow_tags.awl_add_arrow_tags(
                reshaped_arrow_data,
                self._arrow_data.field("_tag"),
                self.object_type.tag,
            )
        return reshaped_arrow_data
    res = _apply_fn_node_with_tag_pushdown(self, fn)
    return res


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


def _impute_nones_for_sort(awl: ArrowWeaveList) -> ArrowWeaveList:
    """Impute missing values in a table so that it can be sorted. This is a workaround for
    the fact that arrow does not handle missing values in a table when sorting, it just
    moves them all to the end of the list."""

    def impute_nones(
        arrow_list: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        # this does not work for unions in arrow < 12
        if not types.is_optional(arrow_list.object_type):
            return None

        mask = pa.compute.is_null(arrow_list._arrow_data)
        any_null = pa.compute.any(mask).as_py()
        num_null = pa.compute.sum(mask).as_py()

        if any_null:
            all_null = num_null == len(arrow_list._arrow_data)
            if all_null:
                return ArrowWeaveList(
                    pa.repeat(0, num_null),
                    types.Int(),
                    awl._artifact,
                )
            if pa.types.is_struct(arrow_list._arrow_data.type) or pa.types.is_list(
                arrow_list._arrow_data.type
            ):
                raise NotImplementedError(
                    "Imputing nulls for a struct or a list is not implemented"
                )

            if pa.types.is_string(arrow_list._arrow_data.type):
                replacement = pa.repeat("", num_null)
                new_data = pa.compute.replace_with_mask(
                    arrow_list._arrow_data, mask, replacement
                )
            elif pa.types.is_floating(arrow_list._arrow_data.type):
                min = pa.compute.min(arrow_list._arrow_data).as_py()
                replacement = pa.repeat(
                    min - 1.0, num_null
                )  # greater than all other elements
            elif pa.types.is_integer(arrow_list._arrow_data.type):
                min = pa.compute.min(arrow_list._arrow_data).as_py()
                replacement = pa.repeat(min - 1, num_null)
            else:
                raise NotImplementedError(
                    f"Imputing nulls for type {arrow_list._arrow_data.type} is not implemented"
                )

            new_data = pa.compute.replace_with_mask(
                arrow_list._arrow_data, mask, replacement
            )
            return ArrowWeaveList(
                new_data,
                types.non_none(arrow_list.object_type),
                awl._artifact,
            )

        return None

    return awl.map_column(impute_nones)


def _sort_values_list_array_to_table(
    sort_values: ArrowWeaveList, col_dirs: list[str]
) -> pa.Table:
    flattened = sort_values._arrow_data_asarray_no_tags().flatten()

    columns = (
        []
    )  # this is intended to be a pylist and will be small since it is number of sort fields
    col_len = len(sort_values._arrow_data)
    dir_len = len(col_dirs)
    col_names = [str(i) for i in range(dir_len)]
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

    return pa.Table.from_arrays(columns, names=col_names)


def _arrow_sort_values_to_indices(
    sort_values: pa.Table, col_dirs: list[str]
) -> pa.Array:
    col_names = sort_values.column_names

    order = [
        (col_name, "ascending" if dir_name == "asc" else "descending")
        for col_name, dir_name in zip(col_names, col_dirs)
    ]

    return pc.sort_indices(sort_values, order, null_placement="at_end")


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
    sort_values = _apply_fn_node_with_tag_pushdown(self, comp_fn)
    sort_values = _sort_values_list_array_to_table(sort_values, col_dirs)

    # modify to_compare_safe to preserve numbers
    for i, column_name in enumerate(sort_values.column_names):
        column = sort_values[column_name]
        column = column.combine_chunks()

        # handle unions.

        if pa.types.is_union(column.type):
            if pa.compute.all(
                pa.compute.equal(column.type_codes, column.type_codes[0])
            ).as_py():
                column = column.field(column.type_codes[0].as_py())
            else:
                # have to break out here. we need to convert to a string but
                # pyarrow doesn't support string casting for multi-type unions.
                column = [str(x) if x is not None else x for x in column.to_pylist()]
                column = pa.array(column)

        # quickly refine column type
        column_type = types.TypeRegistry.type_of(column).object_type
        has_nulls = pa.compute.any(pc.is_null(column)).as_py()
        if has_nulls:
            column_type = types.optional(column_type)

        column = ArrowWeaveList(column, column_type, self._artifact)
        column = _impute_nones_for_sort(column)
        column = convert.to_compare_safe(column)
        sort_values = sort_values.set_column(i, column_name, column._arrow_data)

    indices = _arrow_sort_values_to_indices(sort_values, col_dirs)
    return ArrowWeaveList(
        pc.take(self._arrow_data, indices), self.object_type, self._artifact
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
    table = self._arrow_data
    unsafe_group_table_awl = _apply_fn_node_with_tag_pushdown(self, group_by_fn)
    group_table_awl = to_compare_safe(unsafe_group_table_awl.without_tags())
    group_table_as_array_awl_stripped = group_table_awl._arrow_data
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
        {"arr": input_types["self"], "index": input_types["index"]},
        list_type=ArrowWeaveListType,
    ),
)
def index(
    self: ArrowWeaveList,
    index: typing.Optional[typing.Union[int, typing.List[typing.Optional[int]]]],
):
    return self._index(index)


@op(name="ArrowWeaveList-offset", output_type=lambda input_types: input_types["self"])
def offset(self: ArrowWeaveList, offset: int):
    return ArrowWeaveList(
        self._arrow_data.slice(offset), self.object_type, self._artifact
    )


@op(name="ArrowWeaveList-limit", output_type=lambda input_types: input_types["self"])
def limit(self: ArrowWeaveList, limit: int):
    return self._limit(limit)


def explode_table(table: pa.Table, list_columns: list[str]) -> pa.Table:
    other_columns = list(table.schema.names)

    flattened_list_columns: dict[str, pa.ChunkedArray] = {}

    if len(list_columns) == 0:
        return table

    first_column = list_columns[0]
    value_lengths_0 = table[first_column].combine_chunks().value_lengths()

    # only need to calculate this once since all the list columns should have the same shape
    # if they don't, then we raise an error below
    indices: typing.Optional[pa.Array] = None

    for column in list_columns:
        value_lengths = table[column].combine_chunks().value_lengths()
        if not pc.equal(value_lengths, value_lengths_0):
            raise ValueError(
                f"Cannot explode table with list columns of different shapes: {value_lengths} != {value_lengths_0}"
            )
        if pc.any(pc.is_null(table[column])).as_py():
            # Occurs if we have an optional<list> column. Due to the way flatten works, any rows where the
            # list is null will be dropped. So we need to put the null inside a list, which causes flatten
            # to keep it around. This doesn't always work for tables where the list item type is
            # intricate (e.g., struct of dictionary encoded structs), but these are rare cases.
            null_filled = pc.fill_null(table[column], [None])
        else:
            null_filled = table[column]

        flattened = pc.list_flatten(null_filled)
        other_columns.remove(column)
        flattened_list_columns[column] = flattened

        if indices is None:
            indices = pc.list_parent_indices(null_filled)

    if len(other_columns) == 0:
        return pa.table(flattened_list_columns)

    if indices is None:
        raise ValueError("Cannot explode table with no list columns")

    result = table.select(other_columns).take(indices)

    for column in list_columns:
        result = result.append_column(
            pa.field(column, table.schema.field(column).type.value_type),
            flattened_list_columns[column],
        )

    return result


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

    exploded_table = explode_table(arrow_obj, list_cols)

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

    tagged = list(builtin_map(lambda x: arrow_tags.pushdown_list_tags(x), arr))

    # We merge the lists mergesort-style, which is `O(n*log(n))`
    # DO NOT merge the lists reduce-style, which is `O(n^2)`
    return merge_concat(tagged)


def merge_concat(arr: list[ArrowWeaveList]) -> ArrowWeaveList:
    if len(arr) == 0:
        raise ValueError("arr must not be empty")
    if len(arr) == 1:
        return arr[0]
    left, right = merge_concat_split(arr)
    return merge_concat(left).concat(merge_concat(right))


def merge_concat_split(
    arr: list[ArrowWeaveList],
) -> tuple[list[ArrowWeaveList], list[ArrowWeaveList]]:
    if len(arr) < 2:
        raise ValueError("arr must have length of at least 2")
    middle_index = len(arr) // 2
    return arr[:middle_index], arr[middle_index:]


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
    if len(e) == 0:
        return ArrowWeaveList(pa.nones(0), types.UnknownType(), None)
    res = vectorized_container_constructor_preprocessor(e)

    # Use our ArrowWeaveList concat implementation. Its guaranteed to
    # work for all possible AWL types.
    awls = [
        ArrowWeaveList(arr, object_type, None)
        for arr, object_type in zip(res.arrays, res.prop_types.values())
    ]
    result_values = awls[0]
    for next_awl in awls[1:]:
        result_values = result_values.concat(next_awl)

    concatted = result_values._arrow_data

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
        types.List(result_values.object_type),
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


@op(
    name="ArrowWeaveList-randomlyDownsample",
    input_type={
        "self": ArrowWeaveListType(),
        "n": types.Int(),
    },
    output_type=lambda input_types: input_types["self"],
    pure=False,
)
def sample(self, n):
    if n < 0:
        raise ValueError("n must be non-negative")

    elif n >= len(self):
        return self

    arr = np.zeros(len(self), dtype=bool)
    indices = np.random.choice(len(self), n, replace=False)
    arr[indices] = True

    arrow_data = self._arrow_data
    new_arrow_data = arrow_data.filter(pa.array(arr))

    return ArrowWeaveList(
        new_arrow_data,
        self.object_type,
        self._artifact,
    )


def flatten_return_object_type(object_type):
    if types.is_list_like(object_type):
        object_type = object_type.object_type
    return object_type


def flatten_return_type(input_types):
    return ArrowWeaveListType(
        flatten_return_object_type(input_types["arr"].object_type)
    )


@op(
    name="ArrowWeaveList-flatten",
    input_type={"arr": ArrowWeaveListType()},
    output_type=flatten_return_type,
)
def flatten(arr):
    # TODO:
    #   - handle N levels instead of 1

    arrow_data = arr._arrow_data
    if is_list_arrowweavelist(arr):
        # unwrap tags

        tags = None
        if isinstance(arr.object_type, tagged_value_type.TaggedValueType):
            value_awl, tags_awl = (
                arr.tagged_value_value(),
                arr.tagged_value_tag(),
            )

            values = value_awl._arrow_data
            tags = tags_awl._arrow_data

        else:
            values = arrow_data

        assert isinstance(values, pa.ListArray)
        flattened_values = values.flatten()

        if tags is not None:
            list_parent_indices = pc.list_parent_indices(values)
            flattened_tags = tags.take(list_parent_indices)
            flattened_values = arrow_tags.direct_add_arrow_tags(
                flattened_values, flattened_tags
            )

        arrow_data = flattened_values

    return ArrowWeaveList(
        arrow_data,
        flatten_return_object_type(arr.object_type),
        arr._artifact,
    )


def _drop_tags_output_type(input_type):
    from ..op_def import map_type

    return map_type(
        input_type["arr"],
        lambda t: isinstance(t, tagged_value_type.TaggedValueType) and t.value or t,
    )


@op(
    name="ArrowWeaveList-dropTags",
    input_type={"arr": ArrowWeaveListType()},
    output_type=_drop_tags_output_type,
    hidden=True,
)
def drop_tags(arr):
    return arr.without_tags()
