import contextlib
import dataclasses
import duckdb
import typing
import pyarrow as pa
import pyarrow.compute as pc

from ..ops_primitives import list_ as primitive_list
from .. import weave_types as types
from ..language_features.tagging import tagged_value_type, tag_store
from ..api import op
from .. import graph

from .arrow import arrow_as_array, ArrowWeaveListType, offsets_starting_at_zero
from .util import _to_compare_safe_call
from .vectorize import (
    vectorize,
    _call_vectorized_fn_node_maybe_awl,
    _call_and_ensure_awl,
    _apply_fn_node_with_tag_pushdown,
)
from .arrow_tags import pushdown_list_tags, awl_add_arrow_tags
from .list_ import ArrowWeaveList


@contextlib.contextmanager
def duckdb_con() -> typing.Generator[duckdb.DuckDBPyConnection, None, None]:
    con = duckdb.connect()
    try:
        yield con
    finally:
        con.close()


def _filter_none(arrs: list[typing.Any]) -> list[typing.Any]:
    return [a for a in arrs if a != None]


def _awl_struct_array_to_table(arr: pa.StructArray) -> pa.Table:
    assert pa.types.is_struct(arr.type)
    columns = [f.name for f in arr.type]
    arrays = [arr.field(k) for k in columns]
    return pa.Table.from_arrays(arrays, columns)


def _join_all_output_type(input_types):
    return _joined_all_output_type_of_arrs_type(
        input_types["arrs"].object_type.object_type, input_types["joinFn"].output_type
    )


def _joined_all_output_type_of_arrs_type(
    arr_obj_type: types.TypedDict, join_fn_output_type: types.Type
) -> types.Type:
    inner_type = _joined_all_output_type_inner_type(
        arr_obj_type,
    )
    tag_type = _joined_all_output_type_tag_type(join_fn_output_type)
    tagged_type = tagged_value_type.TaggedValueType(tag_type, inner_type)
    return ArrowWeaveListType(tagged_type)


def _joined_all_output_type_inner_type(
    arr_obj_type: types.TypedDict,
) -> types.TypedDict:
    arr_prop_types = arr_obj_type.property_types
    prop_types: dict[str, types.Type] = {}
    for k in arr_prop_types.keys():
        prop_types[k] = types.List(types.optional(arr_prop_types[k]))
    return types.TypedDict(prop_types)


def _joined_all_output_type_tag_type(
    join_fn_output_type: types.Type,
) -> types.TypedDict:
    return types.TypedDict({"joinObj": join_fn_output_type})


def _custom_join_apply_fn_node(
    awl: ArrowWeaveList, fn: graph.OutputNode
) -> typing.Tuple[ArrowWeaveList, types.Type]:
    called = _call_vectorized_fn_node_maybe_awl(awl, vectorize(fn))
    object_type = typing.cast(types.List, called.type).object_type
    return _call_and_ensure_awl(awl, called), object_type


def _map_nested_arrow_fields(
    array: typing.Union[pa.Array, pa.Table, pa.ChunkedArray],
    fn: typing.Callable[[pa.Array, list[str]], typing.Optional[pa.Array]],
    path: list[str] = [],
) -> pa.Array:
    """
    This function can be used to recursively map over all the fields of an arrow
    array. It will traverse through structs, lists, and dictionaries - providing the
    caller with a chance to return a new array at any level. Once a new array is returned
    the traversal will stop at that level. If the caller returns None, the traversal will
    continue. This is useful for performing inplace transformations.
    """

    # We handle ChunkedArrays and Tables by recursing over their chunks first
    if isinstance(array, pa.ChunkedArray):
        if len(array.chunks) == 0:
            return array
        chunks = [_map_nested_arrow_fields(chunk, fn, path) for chunk in array.chunks]
        return pa.chunked_array(chunks)
    if isinstance(array, pa.Table):
        new_arrays = []
        for field in array.schema:
            new_arrays.append(
                _map_nested_arrow_fields(
                    array.column(field.name), fn, path + [field.name]
                )
            )
        return pa.Table.from_arrays(new_arrays, array.schema.names)

    # get results from user
    user_arr = fn(array, path)

    if user_arr != None and user_arr != array:
        return user_arr
    if pa.types.is_struct(array.type):
        if array.type.num_fields == 0:
            return array
        sub_fields = [
            _map_nested_arrow_fields(array.field(field.name), fn, path + [field.name])
            for field in array.type
        ]
        return pa.StructArray.from_arrays(
            sub_fields, [f.name for f in array.type], mask=array.is_null()
        )
    elif pa.types.is_list(array.type):
        sub_arrays = _map_nested_arrow_fields(array.flatten(), fn, path)
        return pa.ListArray.from_arrays(
            offsets_starting_at_zero(array), sub_arrays, mask=array.is_null()
        )
    elif pa.types.is_dictionary(array.type):
        sub_fields = _map_nested_arrow_fields(array.dictionary, fn, path)
        return pa.DictionaryArray.from_arrays(
            array.indices, sub_fields, mask=array.is_null()
        )
    return array


@dataclasses.dataclass
class MultiArrayCommonEncoderResult:
    encoded_arrays: list[pa.Array]
    code_array_to_encoded_array: typing.Callable[[pa.Array], pa.Array]


def _multi_array_common_encoder(
    arrs_keys: list[pa.Array],
) -> MultiArrayCommonEncoderResult:
    """
    Returns a MultiArrayCommonEncoderResult for a list of arrays. Given a list
    of arrays, recursively traverse all the sub fields and replace dictionaries
    with pure integer arrays (the indices) while keeping track of the dictionary
    values. This is useful since duckdb does not handle dictionary encoded
    arrays. Moreover, a function is returned that can be used to convert the
    indices back to dictionary encoded arrays. This is purpose build for Joins,
    but is generally useful for any operation that requires a common encoding of
    multiple arrays.
    """

    # path, new_encoding - note, we could duplicate entries, but that is better
    # than having to perform object equality checks
    all_dictionaries: dict[str, pa.Array] = {}

    def collect_and_recode_dictionaries(array: pa.Array) -> pa.Array:
        def _collect(array: pa.Array, path: list[str]) -> typing.Optional[pa.Array]:
            if pa.types.is_dictionary(array.type):
                path_str = ".".join(path)
                if path_str not in all_dictionaries:
                    offset = 0
                    all_dictionaries[path_str] = array.dictionary
                else:
                    offset = len(all_dictionaries[path_str])
                    all_dictionaries[path_str] = pa.concat_arrays(
                        [all_dictionaries[path_str], array.dictionary]
                    )
                return pc.add(array.indices, offset)
            return None

        return _map_nested_arrow_fields(array, _collect)

    def recode_dictionaries(array: pa.Array) -> typing.Optional[pa.Array]:
        def _record(array: pa.Array, path: list[str]) -> typing.Optional[pa.Array]:
            path_str = ".".join(path)
            if path_str in all_dictionaries:
                return pa.DictionaryArray.from_arrays(array, all_dictionaries[path_str])
            return None

        return _map_nested_arrow_fields(array, _record)

    new_arrs = [collect_and_recode_dictionaries(arr) for arr in arrs_keys]
    return MultiArrayCommonEncoderResult(
        new_arrs,
        recode_dictionaries,
    )


@op(
    name="ArrowWeaveList-joinAll",
    input_type={
        "arrs": types.List(types.optional(ArrowWeaveListType(types.TypedDict({})))),
        "joinFn": lambda input_types: types.Function(
            {"row": input_types["arrs"].object_type.object_type}, types.Any()
        ),
    },
    output_type=_join_all_output_type,
)
def join_all(arrs, joinFn, outer: bool):
    safe_join_fn = _to_compare_safe_call(joinFn)
    # This is a pretty complicated op. See list.ts for the original implementation
    outer_tags = None
    if tag_store.is_tagged(arrs):
        outer_tags = tag_store.get_tags(arrs)

    def maybe_tag(arr):
        if outer_tags is not None:
            return pushdown_list_tags(tag_store.add_tags(arr, outer_tags))
        else:
            return arr

    # First, filter out Nones
    arrs = _filter_none(arrs)

    # If nothing remains, simply return.
    if len(arrs) == 0:
        return ArrowWeaveList(pa.array([]), types.TypedDict({}))

    pushed_arrs = [pushdown_list_tags(arr) for arr in arrs]

    key_types = []
    tagged_arrs_keys = []
    untagged_arrs_keys = []
    for arr in pushed_arrs:
        maybe_tagged_arr = maybe_tag(arr)
        arr_res, key_type = _custom_join_apply_fn_node(maybe_tagged_arr, safe_join_fn)
        untagged_arrs_keys.append(arr_res._arrow_data_asarray_no_tags())

        if safe_join_fn is joinFn:
            full_keys = arrow_as_array(arr_res._arrow_data)
            tagged_key_type = key_type
        else:
            unsafe_arr_res, unsafe_key_type = _custom_join_apply_fn_node(
                maybe_tagged_arr, joinFn
            )
            tagged_key_type = unsafe_key_type
            full_keys = arrow_as_array(unsafe_arr_res._arrow_data)

        key_types.append(tagged_key_type)
        tagged_arrs_keys.append(full_keys)

    arrs_keys = untagged_arrs_keys

    # Get the union of all the keys of all the elements
    arr_keys = []
    all_element_keys: set[str] = set([])
    for arr in pushed_arrs:
        keys = set(typing.cast(types.TypedDict, arr.object_type).property_types.keys())
        arr_keys.append(keys)
        all_element_keys = all_element_keys.union(keys)
    raw_key_to_safe_key = {key: f"c_{ndx}" for ndx, key in enumerate(all_element_keys)}
    safe_key_to_raw_key = {v: k for k, v in raw_key_to_safe_key.items()}
    safe_element_keys = list(raw_key_to_safe_key.values())
    join_key_col_name = "__joinobj__"
    join_tag_key_col_name = "__joinobj_tag__"

    duck_ready_tables = []
    for i, (arr, arrs_keys) in enumerate(zip(pushed_arrs, arrs_keys)):
        if isinstance(arr.object_type, tagged_value_type.TaggedValueType):
            # here, we need to add the row tag to each element.
            tag_arr = arr._arrow_data.field("_tag")
            val_arr = arr._arrow_data.field("_value")
            new_fields = []
            field_names = []
            for field in val_arr.type:
                field_names.append(field.name)
                curr_field = val_arr.field(field.name)
                if isinstance(
                    typing.cast(types.TypedDict, arr.object_type.value).property_types[
                        field.name
                    ],
                    tagged_value_type.TaggedValueType,
                ):

                    curr_field_tag = curr_field.field("_tag")
                    curr_field_val = curr_field.field("_value")
                    combined_field_names = []
                    combined_fields = []
                    for sub_field in tag_arr.type:
                        combined_field_names.append(sub_field.name)
                        combined_fields.append(tag_arr.field(sub_field.name))
                    for sub_field in curr_field_tag.type:
                        if sub_field.name not in combined_field_names:
                            combined_field_names.append(sub_field.name)
                            combined_fields.append(curr_field_tag.field(sub_field.name))
                    tag_field = pa.StructArray.from_arrays(
                        combined_fields, names=combined_field_names
                    )
                    inner_curr_field = curr_field_val
                else:
                    tag_field = tag_arr
                    inner_curr_field = curr_field

                new_fields.append(
                    pa.StructArray.from_arrays(
                        [inner_curr_field, tag_field], names=["_value", "_tag"]
                    )
                )
            array_with_untagged_rows = pa.StructArray.from_arrays(
                new_fields, names=field_names
            )
        else:
            array_with_untagged_rows = arr._arrow_data

        table = _awl_struct_array_to_table(array_with_untagged_rows)
        safe_named_table = table.rename_columns(
            [raw_key_to_safe_key[lookup_name] for lookup_name in table.column_names]
        )
        raw_keyed_table = safe_named_table.add_column(0, join_key_col_name, arrs_keys)
        tagged_table = raw_keyed_table

        tagged_arr_key = tagged_arrs_keys[i]
        if tagged_arr_key != None:
            tagged_table = tagged_table.add_column(
                1, join_tag_key_col_name, tagged_arr_key
            )
        else:
            tagged_table = tagged_table.add_column(
                1, join_tag_key_col_name, pc.scalar(None)
            )

        filtered_table = tagged_table.filter(
            pc.invert(pc.is_null(pc.field(join_key_col_name)))
        )
        duck_ready_tables.append(filtered_table)

    join_type = "full outer" if outer else "inner"

    query = "SELECT COALESCE(%s) as %s" % (
        ", ".join(f"t{i}.{join_key_col_name}" for i in range(len(duck_ready_tables))),
        join_key_col_name,
    )
    query += ", COALESCE(%s) as %s" % (
        ", ".join(
            f"t{i}.{join_tag_key_col_name}" for i in range(len(duck_ready_tables))
        ),
        join_tag_key_col_name,
    )
    for k in safe_element_keys:
        raw_key = safe_key_to_raw_key[k]
        query += ", list_value(%s) as %s" % (
            ", ".join(
                f"t{i}.{k}"
                for i in range(len(duck_ready_tables))
                if raw_key in arr_keys[i]
            ),
            k,
        )

    query += "\nFROM t0"
    for t_ndx in range(1, len(duck_ready_tables)):
        query += f" {join_type} join t{t_ndx} ON t0.{join_key_col_name} = t{t_ndx}.{join_key_col_name}"

    encoder_result = _multi_array_common_encoder(duck_ready_tables)
    encoded_db_tables = encoder_result.encoded_arrays
    with duckdb_con() as con:
        for i, keyed_table in enumerate(encoded_db_tables):
            con.register(f"t{i}", keyed_table)
        res = con.execute(query)
        duck_res_table = res.arrow()
    recorded_table = encoder_result.code_array_to_encoded_array(duck_res_table)
    join_obj_tagged = recorded_table.column(join_tag_key_col_name).combine_chunks()

    final_table = recorded_table.drop(
        [join_key_col_name, join_tag_key_col_name]
    ).rename_columns(all_element_keys)

    merged_obj_types = types.merge_many_types([arr.object_type for arr in pushed_arrs])
    if not types.TypedDict({}).assign_type(merged_obj_types):
        raise ValueError("Can only join ArrowWeaveLists of TypedDicts")
    inner_type = _joined_all_output_type_inner_type(
        typing.cast(types.TypedDict, merged_obj_types),
    )
    tag_type = _joined_all_output_type_tag_type(types.union(*key_types))

    untagged_result: ArrowWeaveList = ArrowWeaveList(
        final_table,
        inner_type,
        arrs[0]._artifact,
    )
    result_tags = pa.StructArray.from_arrays([join_obj_tagged], names=["joinObj"])

    return awl_add_arrow_tags(
        untagged_result,
        result_tags,
        tag_type,
    )


def _join_2_output_type(input_types):
    return ArrowWeaveListType(primitive_list._join_2_output_row_type(input_types))


@op(
    name="ArrowWeaveList-join",
    input_type={
        "arr1": ArrowWeaveListType(types.TypedDict({})),
        "arr2": ArrowWeaveListType(types.TypedDict({})),
        "joinFn1": lambda input_types: types.Function(
            {"row": input_types["arr1"].object_type}, types.Any()
        ),
        "joinFn2": lambda input_types: types.Function(
            {"row": input_types["arr2"].object_type}, types.Any()
        ),
        "alias1": types.String(),
        "alias2": types.String(),
        "leftOuter": types.Boolean(),
        "rightOuter": types.Boolean(),
    },
    output_type=_join_2_output_type,
)
def join_2(arr1, arr2, joinFn1, joinFn2, alias1, alias2, leftOuter, rightOuter):
    # This is a pretty complicated op. See list.ts for the original implementation
    safe_join_fn_1 = _to_compare_safe_call(joinFn1)
    safe_join_fn_2 = _to_compare_safe_call(joinFn2)

    table1 = _awl_struct_array_to_table(arr1._arrow_data)
    table2 = _awl_struct_array_to_table(arr2._arrow_data)

    # Execute the joinFn on each of the arrays
    table1_safe_join_keys = arrow_as_array(
        _apply_fn_node_with_tag_pushdown(arr1, safe_join_fn_1)._arrow_data
    )
    table2_safe_join_keys = arrow_as_array(
        _apply_fn_node_with_tag_pushdown(arr2, safe_join_fn_2)._arrow_data
    )

    if safe_join_fn_1 is joinFn1:
        table1_raw_join_keys = table1_safe_join_keys
    else:
        table1_raw_join_keys = arrow_as_array(
            _apply_fn_node_with_tag_pushdown(arr1, joinFn1)._arrow_data
        )

    if safe_join_fn_2 is joinFn2:
        table2_raw_join_keys = table2_safe_join_keys
    else:
        table2_raw_join_keys = arrow_as_array(
            _apply_fn_node_with_tag_pushdown(arr2, joinFn2)._arrow_data
        )

    raw_join_obj_type = types.optional(types.union(joinFn1.type, joinFn2.type))

    table1_columns_names = arr1.object_type.property_types.keys()
    table2_columns_names = arr2.object_type.property_types.keys()

    table1_safe_column_names = [f"c_{ndx}" for ndx in range(len(table1_columns_names))]
    table2_safe_column_names = [f"c_{ndx}" for ndx in range(len(table2_columns_names))]

    table1_safe_alias = "a_1"
    table2_safe_alias = "a_2"

    safe_join_key_col_name = "__joinobj__"
    raw_join_key_col_name = "__raw_joinobj__"

    with duckdb_con() as con:

        def create_keyed_table(
            table_name, table, safe_keys, raw_keys, safe_column_names
        ):
            keyed_table = (
                table.add_column(0, safe_join_key_col_name, safe_keys)
                .add_column(1, raw_join_key_col_name, raw_keys)
                .filter(pc.invert(pc.is_null(pc.field(safe_join_key_col_name))))
                .rename_columns(
                    [safe_join_key_col_name, raw_join_key_col_name] + safe_column_names
                )
            )
            con.register(table_name, keyed_table)
            return keyed_table

        create_keyed_table(
            "t1",
            table1,
            table1_safe_join_keys,
            table1_raw_join_keys,
            table1_safe_column_names,
        )
        create_keyed_table(
            "t2",
            table2,
            table2_safe_join_keys,
            table2_raw_join_keys,
            table2_safe_column_names,
        )

        if leftOuter and rightOuter:
            join_type = "full outer"
        elif leftOuter:
            join_type = "left outer"
        elif rightOuter:
            join_type = "right outer"
        else:
            join_type = "inner"

        query = f"""
        SELECT 
            COALESCE(t1.{safe_join_key_col_name}, t2.{safe_join_key_col_name}) as {safe_join_key_col_name},
            COALESCE(t1.{raw_join_key_col_name}, t2.{raw_join_key_col_name}) as {raw_join_key_col_name},
            CASE WHEN t1.{safe_join_key_col_name} IS NULL THEN NULL ELSE
                struct_pack({
                    ", ".join(f'{col} := t1.{col}' for col in table1_safe_column_names)
                })
            END as {table1_safe_alias},
            CASE WHEN t2.{safe_join_key_col_name} IS NULL THEN NULL ELSE
                struct_pack({
                    ", ".join(f'{col} := t2.{col}' for col in table2_safe_column_names)
                })
            END as {table2_safe_alias},
        FROM t1 {join_type} JOIN t2 ON t1.{safe_join_key_col_name} = t2.{safe_join_key_col_name}
        """

        res = con.execute(query)

        # If we have any array columns goto pandas first then back to arrow otherwise
        # we segfault: https://github.com/duckdb/duckdb/issues/6004
        if any(pa.types.is_list(c.type) for c in table1.columns) or any(
            pa.types.is_list(c.type) for c in table2.columns
        ):
            duck_table = pa.Table.from_pandas(res.df())
        else:
            duck_table = res.arrow()
    join_obj = duck_table.column(raw_join_key_col_name).combine_chunks()
    duck_table = duck_table.drop([safe_join_key_col_name, raw_join_key_col_name])
    alias_1_res = duck_table.column(table1_safe_alias).combine_chunks()
    alias_1_renamed = pa.StructArray.from_arrays(
        [alias_1_res.field(col_name) for col_name in table1_safe_column_names],
        table1_columns_names,
        mask=alias_1_res.is_null(),
    )
    alias_2_res = duck_table.column(table2_safe_alias).combine_chunks()
    alias_2_renamed = pa.StructArray.from_arrays(
        [alias_2_res.field(col_name) for col_name in table2_safe_column_names],
        table2_columns_names,
        mask=alias_2_res.is_null(),
    )
    final_table = pa.StructArray.from_arrays(
        [alias_1_renamed, alias_2_renamed],
        [alias1, alias2],
    )

    final_type = primitive_list._join_2_output_row_type(
        {
            "arr1": ArrowWeaveListType(arr1.object_type),
            "arr2": ArrowWeaveListType(arr2.object_type),
            "joinFn1": types.Function({"row": arr1.object_type}, joinFn1.type),
            "joinFn2": types.Function({"row": arr2.object_type}, joinFn2.type),
            "alias1": types.Const(types.String(), alias1),
            "alias2": types.Const(types.String(), alias2),
            "leftOuter": types.Const(types.Boolean(), leftOuter),
            "rightOuter": types.Const(types.Boolean(), rightOuter),
        }
    )

    untagged_result: ArrowWeaveList = ArrowWeaveList(
        final_table,
        final_type,
        arr1._artifact,
    )

    res = awl_add_arrow_tags(
        untagged_result,
        pa.StructArray.from_arrays([join_obj], names=["joinObj"]),
        types.TypedDict({"joinObj": raw_join_obj_type}),
    )
    return res
