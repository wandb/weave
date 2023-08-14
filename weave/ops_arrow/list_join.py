import typing
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from ..ops_primitives import list_ as primitive_list
from .. import weave_types as types
from ..language_features.tagging import tagged_value_type
from ..api import op
from .. import graph
from .. import engine_trace

from . import convert
from .arrow import (
    ArrowWeaveListType,
    safe_coalesce,
)
from .arrow_tags import pushdown_list_tags
from .list_ import ArrowWeaveList, make_vec_dict, make_vec_taggedvalue, awl_zip

tracer = engine_trace.tracer()  # type: ignore


def join_all_zip_impl_lambda(
    arrs: list[ArrowWeaveList], joinFn: graph.OutputNode, outer: bool
):
    # Filter Nones and pushdown tags
    arrs = [pushdown_list_tags(a) for a in arrs if a != None]

    # Get the join key for each list
    join_key_cols = [a.apply(joinFn).untagged() for a in arrs]

    return join_all_zip_impl_vec(arrs, join_key_cols, outer)


def join_all_zip_impl_vec(
    arrs: list[ArrowWeaveList], join_key_cols: list[ArrowWeaveList], outer: bool
):
    # Empty case
    if len(arrs) == 0:
        # TODO: I don't think the arrow type is correct here. Should turn validate on.
        return ArrowWeaveList(pa.array([]), types.TypedDict())

    # Do the join
    if outer:
        join_type = "full outer"
    else:
        join_type = "inner"
    aliases = [f"a{i}" for i in range(len(arrs))]
    join_key_col, join_result = join_all_impl(arrs, join_key_cols, aliases, join_type)

    all_keys = {}
    for a in arrs:
        all_keys.update(dict.fromkeys(a.keys()))

    zipped_cols = []
    for k in all_keys:
        key_cols = [new_arr.column(k) for new_arr in join_result]
        zipped_col = awl_zip(*key_cols)
        zipped_cols.append(zipped_col)

    return make_vec_taggedvalue(
        make_vec_dict(joinObj=join_key_col),
        make_vec_dict(**{k: v for k, v in zip(all_keys, zipped_cols)}),
    )


def join_all_impl(
    arrs: list[ArrowWeaveList],
    join_key_cols: list[ArrowWeaveList],
    aliases: list[str],
    join_type: str,
) -> tuple[ArrowWeaveList, list[ArrowWeaveList]]:
    # Ensure each join key col has the same type
    unified_join_key_cols = convert.unify_types(*join_key_cols)

    join_key_cols = unified_join_key_cols

    # Get the safe join keys
    safe_join_key_cols = [convert.to_compare_safe(a) for a in join_key_cols]

    tables: list[pa.Table] = []
    for i, (arr, safe_join_key_col) in enumerate(zip(arrs, safe_join_key_cols)):
        if pa.types.is_null(safe_join_key_col._arrow_data.type):
            # Special case the type of a null column. Arrow's won't join on it.
            # But nulls can be represented in any type, so we cast to int64. The
            # safe join column is not included in the final output, so we don't
            # need to worry about fixing the type later.
            safe_join_key_col._arrow_data = safe_join_key_col._arrow_data.cast("int64")
        tables.append(
            pa.Table.from_arrays(
                [safe_join_key_col._arrow_data, np.arange(len(arr), dtype="int64")],
                names=["join", f"index_t{i}"],
            ).filter(pc.invert(pc.is_null(safe_join_key_col._arrow_data)))
        )

    joined = tables[0]
    for other in tables[1:]:
        joined = joined.join(
            other,
            ["join"],
            join_type=join_type,
            use_threads=False,
            coalesce_keys=True,
        )

    index_cols = [joined[f"index_t{i}"].combine_chunks() for i in range(len(arrs))]

    final_join_key_col: ArrowWeaveList = ArrowWeaveList(
        safe_coalesce(
            *[
                a._arrow_data.take(index_col)
                for index_col, a in zip(index_cols, join_key_cols)
            ]
        ),
        join_key_cols[0].object_type,
        None,
    )

    new_arrs: list[ArrowWeaveList] = []
    for index_col, arr in zip(index_cols, arrs):
        object_type = types.optional(arr.object_type)
        if object_type == types.UnknownType():
            # it was an empty list, so we'll get a column
            # of None after join.
            object_type = types.NoneType()
        new_arrs.append(
            ArrowWeaveList(
                arr._arrow_data.take(index_col),
                object_type,
                arr._artifact,
            )
        )

    return final_join_key_col, new_arrs


Obj1Type = typing.TypeVar("Obj1Type")
Obj2Type = typing.TypeVar("Obj2Type")


def join2_impl(
    arr1: ArrowWeaveList,
    arr2: ArrowWeaveList,
    join1Fn: graph.OutputNode,
    join2Fn: graph.OutputNode,
    alias1: typing.Optional[str] = None,
    alias2: typing.Optional[str] = None,
    leftOuter: bool = False,
    rightOuter: bool = False,
):
    if alias1 == None:
        alias1 = "a1"
    if alias2 == None:
        alias2 = "a2"

    arr1_raw_join_col = arr1.apply(join1Fn).untagged()
    arr2_raw_join_col = arr2.apply(join2Fn).untagged()

    if leftOuter and rightOuter:
        join_type = "full outer"
    elif leftOuter:
        join_type = "left outer"
    elif rightOuter:
        join_type = "right outer"
    else:
        join_type = "inner"

    join_key_col, [new_arr1, new_arr2] = join_all_impl(
        [arr1, arr2],
        [arr1_raw_join_col, arr2_raw_join_col],
        [alias1, alias2],  # type: ignore
        join_type,
    )

    return make_vec_taggedvalue(
        make_vec_dict(joinObj=join_key_col),
        make_vec_dict(**{alias1: new_arr1, alias2: new_arr2}),  # type: ignore
    )


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
    return join_all_zip_impl_lambda(arrs, joinFn, outer)


def _join_2_output_type(input_types):
    return ArrowWeaveListType(primitive_list._join_2_output_row_type(input_types))


@op(
    name="ArrowWeaveList-join",
    input_type={
        "arr1": ArrowWeaveListType(types.TypedDict({})),
        "arr2": ArrowWeaveListType(types.TypedDict({})),
        "join1Fn": lambda input_types: types.Function(
            {"row": input_types["arr1"].object_type}, types.Any()
        ),
        "join2Fn": lambda input_types: types.Function(
            {"row": input_types["arr2"].object_type}, types.Any()
        ),
        "alias1": types.String(),
        "alias2": types.String(),
        "leftOuter": types.Boolean(),
        "rightOuter": types.Boolean(),
    },
    output_type=_join_2_output_type,
)
def join_2(arr1, arr2, join1Fn, join2Fn, alias1, alias2, leftOuter, rightOuter):
    return join2_impl(
        arr1, arr2, join1Fn, join2Fn, alias1, alias2, leftOuter, rightOuter
    )
