import dataclasses
import datetime
import logging
import typing
import pyarrow.compute as pc
import pyarrow as pa

from weave import io_service
from weave.language_features.tagging.tagged_value_type import TaggedValueType
from weave.ops_domain import wbmedia
from ...ops_arrow.list_ import (
    PathItemList,
    PathItemObjectField,
    PathItemStructField,
    PathItemType,
    PathType,
    weave_arrow_type_check,
)

from ...ref_base import Ref
from ...compile_domain import wb_gql_op_plugin
from ...api import op
from ... import weave_types as types
from .. import wb_domain_types as wdt
from ... import artifact_mem
from .. import wb_util
from ...ops_arrow.list_ops import concat
from ...ops_arrow import ArrowWeaveList, ArrowWeaveListType, convert
from ... import engine_trace
from ... import util
from ... import errors

from ...api import use

import pyarrow as pa
from ...wandb_interface import wandb_stream_table

from . import history_op_common


tracer = engine_trace.tracer()


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history_stream_type(run: wdt.Run) -> types.Type:
    # TODO: Consider merging `_unflatten_history_object_type` into the main path
    return ArrowWeaveListType(
        _unflatten_history_object_type(history_op_common.refine_history_type(run))
    )


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history_stream_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    # TODO: Consider merging `_unflatten_history_object_type` into the main path
    return ArrowWeaveListType(
        _unflatten_history_object_type(
            history_op_common.refine_history_type(
                run, columns=history_op_common.get_full_columns(history_cols)
            )
        )
    )


@op(
    name="run-history_stream_with_columns",
    refine_output_type=refine_history_stream_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history_stream_with_columns(run: wdt.Run, history_cols: list[str]):
    return _get_history_stream(run, history_op_common.get_full_columns(history_cols))


@op(
    name="run-history_stream",
    refine_output_type=refine_history_stream_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history_stream(run: wdt.Run):
    # TODO: This is now equivalent to hist2
    return history_op_common.mock_history_rows(run)


@dataclasses.dataclass
class PathTree:
    children: typing.Dict[PathItemType, "PathTree"] = dataclasses.field(
        default_factory=dict
    )
    data: typing.Optional[typing.Any] = None


@dataclasses.dataclass
class HistoryToWeaveResult:
    weave_type: types.Type
    encoded_paths: list[list[str]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class HistoryToWeaveFinalResult:
    weave_type: types.TypedDict
    encoded_paths: list[list[str]] = dataclasses.field(default_factory=list)


def _history_key_type_count_to_weave_type(
    tc: history_op_common.TypeCount,
    keyname: str,
) -> HistoryToWeaveResult:
    tc_type = tc["type"]
    if tc_type == "string":
        return HistoryToWeaveResult(types.String())
    elif tc_type == "number":
        return HistoryToWeaveResult(types.Number())
    elif tc_type == "nil":
        return HistoryToWeaveResult(types.NoneType())
    elif tc_type == "bool":
        return HistoryToWeaveResult(types.Boolean())
    elif tc_type == "map":
        props = {}
        paths = []
        for key, val in tc["keys"].items():
            key_type_members = []
            for member in val:
                res = _history_key_type_count_to_weave_type(member, key)
                key_type_members.append(res.weave_type)
                for p in res.encoded_paths:
                    paths.append([keyname, *p])
            props[key] = types.union(*key_type_members)

        return HistoryToWeaveResult(types.TypedDict(props), paths)
    elif tc_type == "list":
        if "items" not in tc:
            return HistoryToWeaveResult(types.List(types.UnknownType()))
        paths = []
        key_type_members = []
        for member in tc["items"]:
            res = _history_key_type_count_to_weave_type(member, "*")
            key_type_members.append(res.weave_type)
            for p in res.encoded_paths:
                paths.append([keyname, *p])

        return HistoryToWeaveResult(types.List(types.union(*key_type_members)), paths)
    elif isinstance(tc_type, str):
        possible_type = wandb_stream_table.maybe_history_type_to_weave_type(tc_type)
        if possible_type is not None:
            return HistoryToWeaveResult(possible_type, [[keyname]])
    return HistoryToWeaveResult(types.UnknownType())


class TopLevelTypeCount(typing.TypedDict):
    typeCounts: list[history_op_common.TypeCount]


def _get_history_stream(run: wdt.Run, columns=None):
    # 1. Get the flattened Weave-Type given HistoryKeys
    # 2. Read in the live set
    # 3. Raw-load each parquet file
    # 4. For each flattened column:
    #   a. If it contains a "poison type" (non simple union, binary, or legacy media), then
    #       i. For liveset -> we must pass each item `_process_run_dict_item`, then use convert.to_arrow
    #       ii. For parquet -> we must extract the pyobj, us `_process_run_dict_item`, convert.to_arrow
    #   b. If the nested type contains a custom type or object type, then we must adjust the structure:
    #       i. For liveset -> we can pass each item to the simplified `_reconstruct_run_item`, then use convert.to_arrow(already_mapped = true)
    #       ii. For parquet -> we need to use the `_correct_awl` to adjust the structure.
    #   c. For all other types
    #       i. For liveset -> we can just use convert.to_arrow
    #       ii. For parquet -> no op
    # 5. Now we concat the converted liveset and parquet files
    # 6. Finally, unflatten the columns and return the result
    # 7. Optionally: verify the AWL

    # 1. Get the flattened Weave-Type given HistoryKeys
    flattened_object_type = history_op_common.refine_history_type(run, columns=columns)

    # 2. Read in the live set
    raw_live_data = _get_live_data_from_run(run, columns=columns)

    # 3. Raw-load each parquet file
    raw_history_awl_tables = _read_raw_history_awl_tables(run, columns=columns)
    artifact = (
        raw_history_awl_tables[0]._artifact
        if len(raw_history_awl_tables) > 0
        else artifact_mem.MemArtifact()
    )

    # # 3.5: Split type structs
    # type_split_awl_tables = [_split_type_structs(awl) for awl in raw_history_awl_tables]

    # 3.75: Collapse unions
    union_collapsed_awl_tables = [
        _collapse_unions(awl) for awl in raw_history_awl_tables
    ]

    # 4. For each flattened column:
    raw_history_pa_tables = [
        history_op_common.awl_to_pa_table(awl) for awl in union_collapsed_awl_tables
    ]

    live_columns = {}
    live_columns_already_mapped = {}
    for col_name, col_type in flattened_object_type.property_types.items():
        raw_live_column = extract_column_from_live_data(raw_live_data, col_name)
        processed_live_column = None
        if _is_poison_type(col_type):
            logging.warning(
                f"Encountered a history column requiring non-vectorized, in-memory processing: {col_name}: {col_type}"
            )
            processed_live_column = _process_poisoned_live_column(
                raw_live_column, col_type
            )
            live_columns[col_name] = processed_live_column
            # set_column_for_live_data(raw_live_data, col_name, processed_live_column)
            for table_ndx, table in enumerate(raw_history_pa_tables):
                fields = [field.name for field in table.schema]
                new_col = _process_poisoned_history_column(table[col_name], col_type)
                raw_history_pa_tables[table_ndx] = table.set_column(
                    fields.index(col_name), col_name, new_col
                )

        elif _is_directly_convertible_type(col_type):
            live_columns_already_mapped[col_name] = raw_live_column
            # Important that this runs before the else branch
            continue
        else:
            processed_live_column = _reconstruct_original_live_data_col(raw_live_column)
            live_columns_already_mapped[col_name] = processed_live_column
            # set_column_for_live_data(raw_live_data, col_name, processed_live_column)
            for table_ndx, table in enumerate(raw_history_pa_tables):
                fields = [field.name for field in table.schema]
                new_col = _drop_types_from_encoded_types(
                    ArrowWeaveList(
                        table[col_name],
                        None,
                        raw_history_awl_tables[table_ndx]._artifact,
                    )
                )
                raw_history_pa_tables[table_ndx] = table.set_column(
                    fields.index(col_name), col_name, new_col._arrow_data
                )

            # raw_history_pa_tables = history_op_common.awl_to_pa_table(
            #     _drop_types_from_encoded_types(ArrowWeaveList(
            #         table[col_name],

            #     ))
            # )

    # 5. Now we concat the converted liveset and parquet files
    live_columns_to_data = [
        {k: v[i] for k, v in live_columns.items()} for i in range(len(raw_live_data))
    ]

    live_columns_already_mapped_to_data = [
        {k: v[i] for k, v in live_columns_already_mapped.items()}
        for i in range(len(raw_live_data))
    ]

    partial_live_data_awl = convert.to_arrow(
        live_columns_to_data,
        types.List(
            types.TypedDict(
                {
                    k: v
                    for k, v in flattened_object_type.property_types.items()
                    if k in live_columns
                }
            )
        ),
        artifact=artifact,
        py_objs_already_mapped=True,
    )
    partial_live_data_already_mapped_awl = convert.to_arrow(
        live_columns_already_mapped_to_data,
        types.List(
            types.TypedDict(
                {
                    k: v
                    for k, v in flattened_object_type.property_types.items()
                    if k in live_columns_already_mapped
                }
            )
        ),
        artifact=artifact,
        py_objs_already_mapped=True,
    )

    field_names = []
    field_arrays = []
    for field in partial_live_data_awl._arrow_data.type:
        field_names.append(field.name)
        field_arrays.append(partial_live_data_awl._arrow_data.field(field.name))

    for field in partial_live_data_already_mapped_awl._arrow_data.type:
        field_names.append(field.name)
        field_arrays.append(
            partial_live_data_already_mapped_awl._arrow_data.field(field.name)
        )

    live_data_awl = ArrowWeaveList(
        pa.StructArray.from_arrays(field_arrays, field_names),
        flattened_object_type,
        artifact=artifact,
    )

    # 5. Now we concat the converted liveset and parquet files
    concatted_awl = history_op_common.concat_awls(
        [
            live_data_awl,
            *{
                ArrowWeaveList(table, object_type=flattened_object_type)
                for table in raw_history_pa_tables
            },
        ]
    )

    sorted_table = history_op_common.sort_history_pa_table(
        history_op_common.awl_to_pa_table(concatted_awl)
    )

    # 6. Finally, unflatten the columns
    final_array = _unflatten_pa_table(sorted_table)
    final_type = _unflatten_history_object_type(flattened_object_type)

    # 7. Optionally: verify the AWL
    reason = weave_arrow_type_check(final_type, final_array)

    if reason != None:
        raise errors.WeaveHistoryDecodingError(
            f"Failed to effectively convert column of Gorilla Parquet History to expected history type: {reason}"
        )
    return ArrowWeaveList(
        final_array,
        final_type,
        artifact,
    )

    # 7. Optionally: verify the AWL


# def _unflatten_mapper(
#     awl: ArrowWeaveList, path: PathType
# ) -> typing.Optional[ArrowWeaveList]:
#     if len(path) == 1:
#         path_part = path[0]
#         assert isinstance(path_part, PathItemStructField)
#         if "." in path_part.key:

#     return None


def _build_array_from_tree(tree: PathTree) -> pa.Array:
    children_struct_array = []
    if len(tree.children) > 0:
        mask = None
        children_data = {}
        for k, v in tree.children.items():
            children_data[k] = _build_array_from_tree(v)
            if mask is None:
                mask = pa.compute.is_null(children_data[k])
            else:
                mask = pa.compute.or_(mask, pa.compute.is_null(children_data[k]))

        children_struct = pa.StructArray.from_arrays(
            children_data.values(), children_data.keys(), mask=pa.compute.invert(mask)
        )
        children_struct_array = [children_struct]
    children_arrays = [*(tree.data or []), *children_struct_array]

    if len(children_arrays) == 0:
        raise errors.WeaveHistoryDecodingError("Cannot build array from empty tree")
    elif len(children_arrays) == 1:
        return children_arrays[0]

    num_rows = len(tree.data[0])
    type_array = pa.nulls(num_rows, type=pa.int8())
    offset_template = pa.array(list(range(num_rows)), type=pa.int8())
    arrays = []
    offsets = []
    for member_ndx, union_member_array in enumerate(children_arrays):
        is_usable = pa.compute.invert(pa.compute.is_null(union_member_array))
        arrays.append(union_member_array.filter(is_usable))
        offsets.extend(offset_template.filter(is_usable).to_pylist())
        type_array = pa.compute.replace_with_mask(
            type_array, is_usable, pa.array([member_ndx], type=pa.int8())
        )

    return pa.UnionArray.from_dense(
        type_array, pa.array(offsets + [0], type=pa.int32()), arrays
    )


def _unflatten_pa_table(array: pa.Table) -> pa.StructArray:
    cols = array.schema.names
    new_tree = PathTree(data=[])
    for col_name in cols:
        path = col_name.split(".")
        target = new_tree
        for part in path:
            if part not in target.children:
                target.children[part] = PathTree(data=[])
            target = target.children[part]
            target.data.append(array[col_name].combine_chunks())

    # Recursively resolve the tree
    return _build_array_from_tree(new_tree)


def _union_collapse_mapper(
    awl: ArrowWeaveList, path: PathType
) -> typing.Optional[ArrowWeaveList]:
    object_type = types.non_none(awl.object_type)
    if types.TypedDict({}).assign_type(object_type):
        object_type = typing.cast(types.TypedDict, object_type)
        columns = list(object_type.property_types.keys())
        if all([c.startswith("_type_") for c in columns]):
            logging.warning(
                f"Encountered history store union: this requires a non-vectorized transformation on the order of number of rows (but fortunately does not require transforming to python). Path: {path}, Type: {object_type}"
            )
            arrow_data = awl._arrow_data
            num_rows = len(arrow_data)
            type_array = pa.nulls(num_rows, type=pa.int8())
            offset_template = pa.array(list(range(num_rows)), type=pa.int8())
            arrays = []
            offsets = []
            weave_type_members = []
            for col_ndx, col_name in enumerate(columns):
                weave_type_members.append(object_type.property_type[col_name])
                column_data = arrow_data.field(col_name)
                is_usable = pa.compute.invert(pa.compute.is_null(column_data))
                arrays.append(column_data.filter(is_usable))
                offsets.append(offset_template.filter(is_usable).to_pylist())
                type_array = pa.compute.replace_with_mask(
                    type_array, is_usable, col_ndx
                )
            union_arr = pa.UnionArray.from_dense(
                type_array, pa.array(offsets + [0], type=pa.int32()), arrays
            )
            return ArrowWeaveList(
                union_arr, types.union(*weave_type_members), awl._artifact
            )

    return None


def _collapse_unions(awl: ArrowWeaveList) -> ArrowWeaveList:
    return awl.map_column(_union_collapse_mapper)


def _drop_types_mapper(
    awl: ArrowWeaveList, path: PathType
) -> typing.Optional[ArrowWeaveList]:
    object_type = types.non_none(awl.object_type)
    if types.TypedDict(
        {"_type": types.optional(types.String()), "_val": types.Any()}
    ).assign_type(object_type):
        return awl.column("_val")


def _drop_types_from_encoded_types(awl: ArrowWeaveList) -> ArrowWeaveList:
    return awl.map_column(_drop_types_mapper)


def _get_live_data_from_run(run: wdt.Run, columns=None):
    raw_live_data = run.gql["sampledParquetHistory"]["liveData"]
    if columns is None:
        return raw_live_data
    column_set = set(columns)
    return [{k: v for k, v in row.items() if k in column_set} for row in raw_live_data]


def extract_column_from_live_data(live_data: list[dict], column_name: str):
    return [row.get(column_name, None) for row in live_data]


def set_column_for_live_data(
    live_data: list[dict], column_name: str, updated_row: list
) -> list[dict]:
    for row, updated_value in zip(live_data, updated_row):
        row[column_name] = updated_value
    return live_data


def _process_poisoned_live_column(live_column: list, col_type: types.Type) -> list:
    return [wb_util._process_run_dict_item(item) for item in live_column]
    # return convert.to_arrow(
    #     processed_data,
    #     types.List(col_type),
    #     artifact=artifact_mem.MemArtifact(),
    # )


def _process_poisoned_history_column(
    history_column: pa.Array, col_type: types.Type
) -> pa.Array:
    pyobj = history_column.to_pylist()
    processed_data = [
        wb_util._process_run_dict_item(item) if item is not None else None
        for item in pyobj
    ]
    awl = convert.to_arrow(
        processed_data,
        types.List(col_type),
        artifact=artifact_mem.MemArtifact(),
    )
    return pa.chunked_array([awl._arrow_data])


# Copy from common - need to merge back
def _read_raw_history_awl_tables(run: wdt.Run, columns=None) -> list[ArrowWeaveList]:
    io = io_service.get_sync_client()
    tables = []
    for url in run.gql["sampledParquetHistory"]["parquetUrls"]:
        local_path = io.ensure_file_downloaded(url)
        if local_path is not None:
            path = io.fs.path(local_path)
            awl = history_op_common.local_path_to_parquet_table(
                path, None, columns=columns
            )
            tables.append(awl)
    return tables

    # return history_op_common.process_history_awl_tables(tables)


def _is_poison_type(col_type: types.Type):
    return _is_poison_type_recursive(col_type)


def _is_directly_convertible_type(col_type: types.Type):
    return _is_directly_convertible_type_recursive(col_type)


non_poison_legacy_types = (wbmedia.ImageArtifactFileRefType,)
poison_legacy_types = (
    wbmedia.AudioArtifactFileRef.WeaveType,
    wbmedia.BokehArtifactFileRef.WeaveType,
    wbmedia.VideoArtifactFileRef.WeaveType,
    wbmedia.Object3DArtifactFileRef.WeaveType,
    wbmedia.MoleculeArtifactFileRef.WeaveType,
    wbmedia.HtmlArtifactFileRef.WeaveType,
    wbmedia.LegacyTableNDArrayType,
)


def _is_poison_type_recursive(col_type: types.Type):
    if types.NoneType().assign_type(col_type):
        return False
    non_none_type = types.non_none(col_type)
    if isinstance(non_none_type, types.UnionType):
        return True
    elif isinstance(poison_legacy_types, poison_legacy_types):
        return True
    elif isinstance(non_none_type, types.List):
        return _is_poison_type_recursive(non_none_type.object_type)
    elif isinstance(non_none_type, types.TypedDict):
        for k, v in non_none_type.property_types.items():
            if _is_poison_type_recursive(v):
                return True
        return False
    else:
        return False


def _is_directly_convertible_type_recursive(col_type: types.Type):
    if types.NoneType().assign_type(col_type):
        return True
    non_none_type = types.non_none(col_type)
    if types.union(
        *[
            types.Number(),
            types.Int(),
            types.Float(),
            types.String(),
            types.Boolean(),
        ]
    ).assign_type(col_type):
        return True
    elif isinstance(non_none_type, types.List):
        return _is_directly_convertible_type_recursive(non_none_type.object_type)
    elif isinstance(non_none_type, types.TypedDict):
        for k, v in non_none_type.property_types.items():
            if not _is_directly_convertible_type_recursive(v):
                return False
        return True
    else:
        return False


# def _get_history_stream(run: wdt.Run, columns=None):
#     final_object_type = _refine_history_type(run, columns=columns)
#     parquet_history = _read_history_parquet(
#         run, final_object_type.weave_type, columns=columns
#     )
#     live_data = run.gql["sampledParquetHistory"]["liveData"]
#     return _get_history_stream_inner(final_object_type, live_data, parquet_history)


def _get_history_stream_inner(
    final_type: HistoryToWeaveFinalResult,
    live_data: list[dict],
    parquet_history: typing.Any,
):
    with tracer.trace("get_history") as span:
        span.set_tag("history_version", 3)
    """Dont read binary columns. Keep everything in arrow. Faster, but not as full featured as get_history"""
    object_type = final_type.weave_type
    live_data = _reconstruct_original_live_data(live_data)

    artifact = artifact_mem.MemArtifact()
    # turn live data into arrow
    if live_data is not None and len(live_data) > 0:
        with tracer.trace("live_data_to_arrow"):
            live_data_processed = convert.to_arrow(
                live_data,
                types.List(object_type),
                artifact=artifact,
                py_objs_already_mapped=True,
            )
    else:
        live_data_processed = []

    if parquet_history is not None and len(parquet_history) > 0:
        with tracer.trace("parquet_history_to_arrow"):
            parquet_history = _gorilla_parquet_table_to_corrected_awl(
                parquet_history, object_type
            )
    else:
        parquet_history = []

    if len(live_data_processed) == 0 and len(parquet_history) == 0:
        return ArrowWeaveList(pa.array([]), object_type, artifact=artifact)
    elif len(live_data_processed) == 0:
        return parquet_history
    elif len(parquet_history) == 0:
        return live_data_processed
    return use(concat([parquet_history, live_data_processed]))


def _reconstruct_original_live_data(live_data: list[dict]):
    # in this function we want to:
    # a) unflatted top-level dictionaries
    # b) reduce the encoded cells to their vals

    return [_reconstruct_original_live_data_row(row) for row in live_data]


def _reconstruct_original_live_data_col(row: list):
    return [_reconstruct_original_live_data_cell(cell) for cell in row]


def _reconstruct_original_live_data_row(row: dict):
    # Handles unflattening the top-level dictionaries
    new_row: dict[str, typing.Any] = {}
    for col, cell in row.items():
        new_cell = _reconstruct_original_live_data_cell(cell)
        target = new_row
        path_parts = col.split(".")
        final_part = path_parts[-1]
        for path in path_parts[:-1]:
            if path not in target:
                target[path] = {}
            target = target[path]
        target[final_part] = new_cell
    return new_row


def _reconstruct_original_live_data_cell(live_data: typing.Any) -> typing.Any:
    if isinstance(live_data, list):
        return [_reconstruct_original_live_data_cell(cell) for cell in live_data]
    if isinstance(live_data, dict):
        if wandb_stream_table.is_weave_encoded_history_cell(live_data):
            return live_data["_val"]
        return {
            key: _reconstruct_original_live_data_cell(val)
            for key, val in live_data.items()
        }
    return live_data


# Damnit ... still didn't do the dot notation...
# Another fundamnetal problem: list length... since list paths have non uniform lengths, we can't query through them in a 1-1 mapping.

# OK, som we need to try a version 4 of the history converter
# Now that we know how to map between the two forms, we can use that information.

# Essentially this approach would map_columns over the gorilla parequet,
# applying transformation rules at the parent level. This feels prone to error
# but the inverse (my current implementation) maps over the ideal array, and
# since the shapes are not exactly the same and list are not static length
# this approach will not work.

# Alternatively: how can we scope this down?
# can we totally change the paradigm?


# TODO: Clean this up - there is a lot of waste from dev work
@dataclasses.dataclass
class TargetAWLSpec:
    arrow_leaf_path: PathItemType
    # weave_leaf_path: PathType  # This type needs some more thought
    remap_path: PathType
    weave_type: types.Type
    arrow_type: pa.DataType
    parent: typing.Optional["TargetAWLSpec"] = None


def _gorilla_parquet_table_to_corrected_awl(
    gorilla_parquet: pa.Table,
    target_object_type: types.TypedDict,
) -> ArrowWeaveList:
    gorilla_awl = ArrowWeaveList(
        gorilla_parquet,
        artifact=artifact_mem.MemArtifact(),
    )
    prototype_awl = _create_prototype_awl_from_object_type(
        target_object_type, len(gorilla_awl)
    )

    target_path_summary: PathSummary = _summarize_awl_paths(prototype_awl)
    # current_path_summary: PathSummary = _summarize_awl_paths(gorilla_awl)

    column_tree: PathTree = PathTree()

    def column_getter(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        nonlocal column_tree
        if path == ():
            return None
        pt = column_tree
        for path_part in path:
            if path_part not in pt.children:
                pt.children[path_part] = PathTree()
            pt = pt.children[path_part]
        pt.data = awl._arrow_data

        return None

    gorilla_awl.map_column(column_getter)

    def column_setter(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        nonlocal target_path_summary
        if path not in target_path_summary.leaf_paths:
            return None
        target_spec = target_path_summary.leaf_paths[path]

        s = target_spec
        source_path_parts = []
        while s != None:
            source_path_parts = [*s.remap_path, *source_path_parts]
            s = s.parent
        source_path = source_path_parts

        tree = column_tree
        for path_part in source_path:
            if path_part in tree.children:
                tree = tree.children[path_part]
            else:
                # Critical injection of union handling
                if tree.data != None and pa.types.is_struct(tree.data.type):
                    union_path = PathItemStructField("_type_struct")
                    if (union_path in tree.children) and path_part in tree.children[
                        union_path
                    ].children:
                        # Awesome! We found the hidden union
                        tree = tree.children[union_path].children[path_part]
                        continue

                raise errors.WeaveHistoryDecodingError(
                    f"Given target type {target_object_type}, attempt to populate arrow column at {target_spec.remap_path}, but failed to find source path {source_path}"
                )

        # Final Union Consideration
        # When to do this? When we are at a gorilla union!
        if len(tree.children) > 0 and all(
            [
                (
                    isinstance(path_part, PathItemStructField)
                    and path_part.key.startswith("_type_")
                )
                for path_part in tree.children.keys()
            ]
        ):
            # float64 | utf8 | bool | struct | list | binary
            self_type = types.non_none(target_spec.weave_type)
            intermediate_union_path = None
            if isinstance(self_type, primitive_types):
                if isinstance(
                    self_type,
                    (
                        types.Number,
                        types.Int,
                        types.Float,
                    ),
                ):
                    intermediate_union_path = PathItemStructField("_type_float64")
                elif isinstance(self_type, (types.Boolean,)):
                    intermediate_union_path = PathItemStructField("_type_bool")
                elif isinstance(self_type, (types.String,)):
                    intermediate_union_path = PathItemStructField("_type_utf8")
                else:
                    raise errors.WeaveHistoryDecodingError(
                        "Programmer Error: Unhandled type"
                    )
            elif isinstance(self_type, union_types):
                raise errors.WeaveHistoryDecodingError(
                    "Programmer Error: Nested Unions not supported"
                )
            elif isinstance(self_type, list_types):
                intermediate_union_path = PathItemStructField("_type_list")
            elif isinstance(self_type, dict_types):
                intermediate_union_path = PathItemStructField("_type_struct")
            elif isinstance(self_type, object_types):
                intermediate_union_path = PathItemStructField("_type_struct")
            elif isinstance(self_type, custom_types):
                intermediate_union_path = PathItemStructField("_type_utf8")

            else:
                raise errors.WeaveHistoryDecodingError(
                    "Programmer Error: Unhandled type"
                )

            if (
                intermediate_union_path != None
                and intermediate_union_path in tree.children
            ):
                tree = tree.children[intermediate_union_path]

        if tree.data == None:
            raise errors.WeaveHistoryDecodingError(
                "Missing data in column tree path {source_path}"
            )

        data_array = tree.data
        reason = weave_arrow_type_check(target_spec.weave_type, data_array)

        if reason != None:
            raise errors.WeaveHistoryDecodingError(
                f"Failed to effectively convert column of Gorilla Parquet History to expected history type: {reason}"
            )
        return ArrowWeaveList(
            data_array,
            target_spec.weave_type,
            awl._artifact,
        )

    corrected_awl = prototype_awl.map_column(column_setter, is_full_replacement=False)

    reason = weave_arrow_type_check(target_object_type, corrected_awl._arrow_data)

    if reason != None:
        errors.WeaveHistoryDecodingError(
            f"Failed to effectively convert  Gorilla Parquet History to expected history type: {reason}"
        )

    return corrected_awl


# 6 Cases to handle:
## 1) The current spec is a primitive type
primitive_types = (
    types.Number,
    types.Int,
    types.Float,
    types.Boolean,
    types.String,
)
## 2) The current spec is a non-simple union
union_types = (types.UnionType,)
## 3) The current spec is a list
list_types = (types.List,)
## 4) The current spec is a dict
dict_types = (types.TypedDict,)
## 5) The current spec is an object
object_types = (types.ObjectType,)
## 6) The current spec is a custom type
custom_types = (types.Type,)


@dataclasses.dataclass
class PathSummary:
    all_paths: dict[PathType, TargetAWLSpec] = dataclasses.field(default_factory=dict)
    leaf_paths: dict[PathType, TargetAWLSpec] = dataclasses.field(default_factory=dict)


def _summarize_awl_paths(prototype_awl: ArrowWeaveList) -> list[TargetAWLSpec]:
    path_summary = PathSummary()

    def path_accumulator(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional["ArrowWeaveList"]:
        nonlocal path_summary
        if path == ():
            return None
        if path in path_summary.all_paths:
            return None

        final_path = path[-1]
        weave_type = awl.object_type
        self_type = types.non_none(weave_type)
        arrow_type = awl._arrow_data.type
        # weave_leaf_path = PathItemOuterList
        self_path = (final_path,)
        parent_spec = None
        # TODO: It really feels like this can be collapsed into the below switch

        extra_path = ()
        if isinstance(
            self_type, primitive_types + union_types + list_types + dict_types
        ):
            self_path = (final_path,)
        elif isinstance(self_type, object_types + custom_types):
            extra_path = (
                PathItemStructField("_val"),
                PathItemStructField("_val"),
            )
        else:
            raise errors.WeaveHistoryDecodingError("Programmer Error: Unhandled type")

        if len(path) > 1:
            parent_path = tuple(path[:-1])
            if parent_path not in path_summary.all_paths:
                raise errors.WeaveHistoryDecodingError(
                    "Programmer Error: Expected to visit parent path before child path"
                )
            parent_spec = path_summary.all_paths[parent_path]
            if parent_path in path_summary.leaf_paths:
                parent_spec = path_summary.leaf_paths.pop(parent_path)

            # Construct weave_leaf_path from parent.
            # PathItemStructField,
            # PathItemList,
            parent_weave_type = types.non_none(parent_spec.weave_type)
            if isinstance(parent_weave_type, primitive_types):
                raise errors.WeaveHistoryDecodingError(
                    "Unexpectedly encountered primitive parent type in path"
                )
            elif isinstance(parent_weave_type, union_types):
                # float64 | utf8 | bool | struct | list | binary
                if isinstance(self_type, primitive_types):
                    if isinstance(
                        self_type,
                        (
                            types.Number,
                            types.Int,
                            types.Float,
                        ),
                    ):
                        self_path = (PathItemStructField("_type_float64"),)
                    elif isinstance(self_type, (types.Boolean,)):
                        self_path = (PathItemStructField("_type_bool"),)
                    elif isinstance(self_type, (types.String,)):
                        self_path = (PathItemStructField("_type_utf8"),)
                    else:
                        raise errors.WeaveHistoryDecodingError(
                            "Programmer Error: Unhandled type"
                        )
                elif isinstance(self_type, union_types):
                    raise errors.WeaveHistoryDecodingError(
                        "Programmer Error: Nested Unions not supported"
                    )
                elif isinstance(self_type, list_types):
                    self_path = (PathItemStructField("_type_list"),)
                elif isinstance(self_type, dict_types):
                    self_path = (PathItemStructField("_type_struct"),)
                elif isinstance(self_type, object_types):
                    self_path = (PathItemStructField("_type_struct"),)
                elif isinstance(self_type, custom_types):
                    self_path = (PathItemStructField("_type_struct"),)
                else:
                    raise errors.WeaveHistoryDecodingError(
                        "Programmer Error: Unhandled type"
                    )
            elif isinstance(parent_weave_type, list_types):
                self_path = (PathItemList(),)
            elif isinstance(parent_weave_type, dict_types):
                assert isinstance(final_path, PathItemStructField)
                # No-op
                self_path = (final_path,)
                # remap_path = (final_path,)
            elif isinstance(parent_weave_type, object_types):
                assert isinstance(final_path, PathItemObjectField)
                # FIXME: Ugg this double _val is a bit of a hack.
                self_path = (
                    # PathItemStructField("_val"),
                    # PathItemStructField("_val"),
                    PathItemStructField(final_path.attr),
                )
            elif isinstance(parent_weave_type, custom_types):
                raise errors.WeaveHistoryDecodingError(
                    "Custom type parents not yet implemented"
                )
            else:
                raise errors.WeaveHistoryDecodingError(
                    "Programmer Error: Unhandled type"
                )

        path_summary.all_paths[path] = TargetAWLSpec(
            arrow_leaf_path=final_path,
            remap_path=(*self_path, *extra_path),
            # weave_leaf_path=weave_leaf_path,
            weave_type=weave_type,
            arrow_type=arrow_type,
            parent=parent_spec,
        )

        path_summary.leaf_paths[path] = path_summary.all_paths[path]

        return None

    # We want to visit parents before children, so
    # we use the pre-order traversal.
    prototype_awl.map_column(fn=lambda x, y: None, pre_fn=path_accumulator)

    return path_summary


def _create_prototype_awl_from_object_type(
    target_object_type: types.TypedDict,
    length: int = 0,
) -> ArrowWeaveList:
    artifact = artifact_mem.MemArtifact()
    return convert.to_arrow(
        # Sad... can we do this any differently?
        [{}] * length,
        # pa.nulls(length),
        types.List(target_object_type),
        artifact=artifact,
    )


def _unflatten_history_object_type(obj_type: types.TypedDict) -> types.TypedDict:
    # Need to combine top-level maps. Note: this is not a recursive function
    # since the flattening only happens top level in gorilla.
    dict_keys: dict[str, types.Type] = {}
    for key, val in obj_type.property_types.items():
        path_parts = key.split(".")
        prop_types = dict_keys

        for part in path_parts[:-1]:
            found = False
            prop_types_inner: dict[str, types.Type] = {}
            default_dict = types.TypedDict(prop_types_inner)
            if part not in prop_types:
                prop_types[part] = default_dict
                prop_types = prop_types_inner
            elif part in prop_types:
                prop_type = prop_types[part]
                if isinstance(prop_type, types.TypedDict):
                    prop_types = prop_type.property_types
                    found = True
                elif isinstance(prop_type, types.UnionType):
                    for member in prop_type.members:
                        if isinstance(member, types.TypedDict):
                            prop_types = member.property_types
                            found = True
                            break

                if not found:
                    prop_types[part] = types.union(prop_type, default_dict)
                    prop_types = prop_types_inner

        final_part = path_parts[-1]
        if final_part not in prop_types:
            prop_types[final_part] = val
        else:
            prop_types[final_part] = types.union(val, prop_types[final_part])

    return types.TypedDict(dict_keys)
