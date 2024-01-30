import dataclasses
import json
import logging
import typing
import pyarrow as pa


from ... import artifact_fs
from .context import get_error_on_non_vectorized_history_transform
from ...gql_op_plugin import wb_gql_op_plugin
from ...api import op
from ... import weave_types as types
from .. import trace_tree, wb_domain_types as wdt
from ... import artifact_mem
from .. import wb_util
from ...arrow.list_ import ArrowWeaveList
from ...arrow.list_ import ArrowWeaveListType
from ...arrow import convert
from ...op_def import map_type
from ... import engine_trace
from ... import errors
from ...wandb_interface import wandb_stream_table
from . import history_op_common
from ... import artifact_base, io_service
from .. import wbmedia
from ...ops_domain.table import _patch_legacy_image_file_types
from ...arrow.list_ import (
    weave_arrow_type_check,
    PathType,
    PathItemType,
    make_vec_none,
)
from ... import gql_json_cache


tracer = engine_trace.tracer()


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history3_type(run: wdt.Run) -> types.Type:
    # TODO: Consider merging `_unflatten_history_object_type` into the main path
    return ArrowWeaveListType(
        _unflatten_history_object_type(history_op_common.refine_history_type(run))
    )


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history3_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    # TODO: Consider merging `_unflatten_history_object_type` into the main path
    return ArrowWeaveListType(
        _unflatten_history_object_type(
            history_op_common.refine_history_type(
                run,
                columns=history_op_common.get_full_columns_prefixed(run, history_cols),
            )
        )
    )


@op(
    name="run-history3_with_columns",
    refine_output_type=refine_history3_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history3_with_columns(run: wdt.Run, history_cols: list[str]):
    return _get_history3(
        run, history_op_common.get_full_columns_prefixed(run, history_cols)
    )


@op(
    name="run-history3",
    refine_output_type=refine_history3_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history3(run: wdt.Run):
    # TODO: This is now equivalent to hist2
    return history_op_common.mock_history_rows(run)


@dataclasses.dataclass
class PathTree:
    children: typing.Dict[PathItemType, "PathTree"] = dataclasses.field(
        default_factory=dict
    )
    data: typing.Optional[typing.Any] = None


def _use_fast_path(flattened_object_type: types.Type) -> bool:
    if isinstance(flattened_object_type, types.TypedDict):
        for k, v in flattened_object_type.property_types.items():
            if not _use_fast_path(v):
                return False
        return True
    elif isinstance(flattened_object_type, types.List):
        return _use_fast_path(flattened_object_type.object_type)
    elif isinstance(flattened_object_type, types.UnionType):
        return all([_use_fast_path(m) for m in flattened_object_type.members])
    elif isinstance(
        flattened_object_type,
        (
            # If the table consists of only these leaf types, then we can use the fast path
            # If you find that you need to expand this list, please talk to
            # Shawn first.
            types.RefType,
            types.NoneType,
            types.Number,
            types.String,
            types.Boolean,
            types.Timestamp,
        ),
    ):
        return True

    # Encountered a type that requires the legacy path
    return False


def _fast_history3_concat(
    raw_history_awl_tables: list[pa.Table],
    live_data: list[dict],
) -> ArrowWeaveList:
    # This is the fast loading path. We only have the types contained in _use_fast_path
    # above.

    # This should be the only path used by StreamTable uses! We don't let users
    # put in the old wandb media types.

    # This path is pure arrow columnar operations, and should never do any
    # kind of python iteration.

    # Note we don't rely on the computed history type. We figure out the type
    # from the arrow types.

    all_awls: list[ArrowWeaveList] = []
    for table in raw_history_awl_tables:
        all_awls.append(ArrowWeaveList(table))

    # OK I lied, to_arrow does python iteration at the moment, but this is only
    # on the live set. If the live set remains smallish (which we can tune)
    # _fast_path should remain fast.
    all_awls.append(convert.to_arrow(live_data))

    # Nothing below here should do python iteration.

    all_converted_awls = []
    for awl in all_awls:

        def _convert_cols(
            awl: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if (
                isinstance(awl.object_type, types.TypedDict)
                and "_val" in awl.object_type.property_types
            ):
                # There are only two kinds of types that look like a _type, _val
                # struct: Timestamp and Ref. Happily, we can distinguish them by
                # looking at the type of the _val field
                val_field = awl._arrow_data.field("_val")
                if isinstance(val_field, (pa.DoubleArray, pa.Int64Array)):
                    # DoubleArray is the always included timestamp field
                    # Int64Array is a user defined timestamp.
                    return ArrowWeaveList(
                        val_field.cast("int64").cast(pa.timestamp("ms", tz="UTC")),
                        types.Timestamp(),
                        awl._artifact,
                    )
                elif isinstance(awl._arrow_data.field("_val"), pa.StringArray):
                    # StringArray is a Ref
                    return ArrowWeaveList(
                        val_field,
                        types.RefType(types.UnknownType()),
                        awl._artifact,
                    )
                else:
                    raise errors.WeaveWBHistoryTranslationError(
                        f"Encountered unexpected type for _val: {type(awl._arrow_data.field('_val'))}"
                    )
            return None

        awl = awl.map_column(fn=lambda x, y: x, pre_fn=_convert_cols)
        all_converted_awls.append(awl)

    return history_op_common.concat_awls(all_converted_awls)


def _check_fast_history3_concat_type(
    orig_expected_type: types.Type, fast_path_type: types.Type, depth: int = 0
) -> str:
    # Check if the output type of fast_history3_concat matches the expected type we get from
    # history type refinement.

    # This encodes business logic for places where we expect mismatches

    # Returns True if match

    if isinstance(orig_expected_type, types.UnionType) or isinstance(
        fast_path_type, types.UnionType
    ):
        # The new type may have nullable where the old didn't. Allow this, by just considering
        # both non_null types.
        orig_nullable, orig_non_null = types.split_none(orig_expected_type)
        fast_path_nullable, fast_non_null = types.split_none(fast_path_type)
        if orig_nullable or fast_path_nullable:
            return _check_fast_history3_concat_type(
                orig_non_null, fast_non_null, depth=depth
            )

    if isinstance(orig_expected_type, types.TypedDict) and isinstance(
        fast_path_type, types.TypedDict
    ):
        result = ""
        for k in set(orig_expected_type.property_types.keys()).union(
            fast_path_type.property_types.keys()
        ):
            sub_result = _check_fast_history3_concat_type(
                orig_expected_type.property_types[k],
                fast_path_type.property_types[k],
                depth=depth + 1,
            )
            if sub_result:
                result += (
                    "  " * depth + f"TypedDict property {k} mismatch:\n" + sub_result
                )
        return result
    elif isinstance(orig_expected_type, types.List) and isinstance(
        fast_path_type, types.List
    ):
        result = _check_fast_history3_concat_type(
            orig_expected_type.object_type, fast_path_type.object_type, depth=depth + 1
        )
        if result:
            return "  " * depth + "List object type mismatch:\n" + result
        return ""

    elif isinstance(orig_expected_type, types.UnionType) and isinstance(
        fast_path_type, types.UnionType
    ):
        result = ""

        # Unions can be out of order, so we check each orig member against
        # each fast_path member
        # We also may have fewer members in the fast_path type, because Refs are always
        # UnknownType, where in the orig type current they may be more specific and not
        # merged into a single RefType.
        for i in range(len(orig_expected_type.members)):
            orig_member = orig_expected_type.members[i]
            for j in range(len(fast_path_type.members)):
                fast_member = fast_path_type.members[j]
                sub_result = _check_fast_history3_concat_type(
                    orig_member, fast_member, depth=depth + 1
                )
                if not sub_result:
                    # A match, go to next orig member
                    break
            else:
                # no remaining fast path member matched the orig member
                result += (
                    "  " * depth
                    + f"Union type member mismatch, original_member: {orig_member} not found in remaining fast_path members\n"
                )
        return result
    elif isinstance(orig_expected_type, types.RefType) and isinstance(
        fast_path_type, types.RefType
    ):
        # The original type may have a full object_type, while in the fast path
        # we always return UnknownType as the object_type. This is expected.
        # So we just don't check object_type here.
        #
        # The original type will also be a more specific, like WandbArtifactRefType
        # but we only have RefType in the fast path. This is also expected.
        return ""
    else:
        if orig_expected_type.assign_type(fast_path_type):
            # For example, if we expect Number but got Float, Float is more specific
            # so that's OK.
            return ""
        if orig_expected_type != fast_path_type:
            orig_expected_str = str(orig_expected_type)
            if len(orig_expected_str) > 50:
                orig_expected_str = orig_expected_str[:50] + "..."
            fast_path_str = str(fast_path_type)
            if len(fast_path_str) > 50:
                fast_path_str = fast_path_str[:50] + "..."
            return (
                "  " * depth + f"Expected {orig_expected_str} but got {fast_path_str}\n"
            )
        return ""


def _get_history3(run: wdt.Run, columns=None):
    # 1. Get the flattened Weave-Type given HistoryKeys
    # 2. Read in the live set
    # 3. Raw-load each parquet file
    # 4. For each flattened column:
    #   a. If it contains a type requiring in-mem processing, then
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

    artifact = artifact_mem.MemArtifact()

    # 1. Get the flattened Weave-Type given HistoryKeys
    flattened_object_type = history_op_common.refine_history_type(run, columns=columns)
    final_type = _unflatten_history_object_type(flattened_object_type)

    # 2. Read in the live set
    raw_live_data = _get_live_data_from_run(run, columns=columns)

    # 3.a: Raw-load each parquet file
    raw_history_awl_tables = _read_raw_history_awl_tables(
        run, columns=columns, artifact=artifact
    )

    # 3.b: Collapse unions
    union_collapsed_awl_tables = [
        _collapse_unions(awl) for awl in raw_history_awl_tables
    ]

    # 4. Process all the data
    raw_history_pa_tables = [
        history_op_common.awl_to_pa_table(awl) for awl in union_collapsed_awl_tables
    ]

    # 5 Now we concat the converted liveset and parquet files
    use_fast_path = _use_fast_path(flattened_object_type)
    if use_fast_path:
        concatted_awl = _fast_history3_concat(raw_history_pa_tables, raw_live_data)
        if len(concatted_awl) == 0:
            return convert.to_arrow([], types.List(final_type), artifact=artifact)
        if not isinstance(concatted_awl.object_type, types.TypedDict):
            raise errors.WeaveWBHistoryTranslationError(
                f"Expected fast_path object_type to be TypedDict, got {concatted_awl.object_type}"
            )

        # Need to get a new final_type, since we don't rely on the flattend_object_type
        # in the fast path.
        new_final_type = _unflatten_history_object_type(concatted_awl.object_type)
        type_mismatch_reason = _check_fast_history3_concat_type(
            final_type, new_final_type
        )
        if type_mismatch_reason:
            # Leaving this in to fire if we get an unexpected type from the fast
            # path. It's probably actually ok if this happens, and we could remove
            # these checks. But I want to understand scenarios in which it happens,
            # so raising here for now. - Shawn
            # raise errors.WeaveWBHistoryTranslationError(
            #     f"Fast path history3 concat produced unexpected type: {type_mismatch_reason}"
            # )
            pass
        final_type = new_final_type
    else:
        # Legacy slow path. This path drops down to python iteration in many
        # cases.
        logging.warning("Using legacy slow path for history3")
        run_path = wb_util.RunPath(
            run["project"]["entity"]["name"],
            run["project"]["name"],
            run["name"],
        )
        (
            live_columns,
            live_columns_already_mapped,
            processed_history_pa_tables,
        ) = _process_all_columns(
            flattened_object_type,
            raw_live_data,
            raw_history_pa_tables,
            run_path,
            artifact,
        )

        live_data_awl = _construct_live_data_awl(
            live_columns,
            live_columns_already_mapped,
            flattened_object_type,
            len(raw_live_data),
            artifact,
        )

        concatted_awl = history_op_common.concat_awls(
            [
                live_data_awl,
                *{
                    ArrowWeaveList(
                        table, object_type=flattened_object_type, artifact=artifact
                    )
                    for table in processed_history_pa_tables
                },
            ]
        )

        if len(concatted_awl) == 0:
            return convert.to_arrow([], types.List(final_type), artifact=artifact)

    sorted_table = history_op_common.sort_history_pa_table(
        history_op_common.awl_to_pa_table(concatted_awl)
    )

    # 6. Finally, unflatten the columns
    final_array = _unflatten_pa_table(sorted_table)

    # 7. Optionally: verify the AWL
    reason = weave_arrow_type_check(final_type, final_array)

    if reason != None:
        raise errors.WeaveWBHistoryTranslationError(
            f"Failed to effectively convert column of Gorilla Parquet History to expected history type: {reason}"
        )
    return ArrowWeaveList(
        final_array,
        final_type,
        artifact=artifact,
    )


def _construct_live_data_awl(
    live_columns: dict[str, list],
    live_columns_already_mapped: dict[str, list],
    flattened_object_type: types.TypedDict,
    num_rows: int,
    artifact: artifact_mem.MemArtifact,
) -> ArrowWeaveList:
    live_columns_to_data = [
        {k: v[i] for k, v in live_columns.items()} for i in range(num_rows)
    ]

    live_columns_already_mapped_to_data = [
        {k: v[i] for k, v in live_columns_already_mapped.items()}
        for i in range(num_rows)
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
    )
    partial_live_data_already_mapped_awl = convert.to_arrow_from_list_and_artifact(
        live_columns_already_mapped_to_data,
        types.TypedDict(
            {
                k: v
                for k, v in flattened_object_type.property_types.items()
                if k in live_columns_already_mapped
            }
        ),
        artifact=artifact,
        py_objs_already_mapped=True,
    )

    field_names = []
    field_arrays = []
    for field_ndx, field in enumerate(partial_live_data_awl._arrow_data.type):
        field_names.append(field.name)
        field_arrays.append(partial_live_data_awl._arrow_data.field(field_ndx))

    for field_ndx, field in enumerate(
        partial_live_data_already_mapped_awl._arrow_data.type
    ):
        field_names.append(field.name)
        field_arrays.append(
            partial_live_data_already_mapped_awl._arrow_data.field(field_ndx)
        )

    return ArrowWeaveList(
        pa.StructArray.from_arrays(field_arrays, field_names),
        flattened_object_type,
        artifact=artifact,
    )


def _pa_table_has_column(pa_table: pa.Table, col_name: str) -> bool:
    return col_name in pa_table.column_names


def _create_empty_column(
    table: pa.Table, col_type: types.Type, artifact: artifact_base.Artifact
) -> pa.Array:
    return convert.to_arrow(
        [None] * len(table), types.List(col_type), artifact=artifact
    )._arrow_data


def _update_pa_table_column(
    table: pa.Table, col_name: str, arrow_col: pa.Array
) -> pa.Table:
    fields = [field.name for field in table.schema]
    return table.set_column(fields.index(col_name), col_name, arrow_col)


def _new_pa_table_column(
    table: pa.Table, col_name: str, arrow_col: pa.Array
) -> pa.Table:
    return table.append_column(col_name, arrow_col)


def _process_all_columns(
    flattened_object_type: types.TypedDict,
    raw_live_data: list[dict],
    raw_history_pa_tables: list[pa.Table],
    run_path: wb_util.RunPath,
    artifact: artifact_mem.MemArtifact,
):
    live_columns = {}
    live_columns_already_mapped = {}
    processed_history_pa_tables = [*raw_history_pa_tables]

    for col_name, col_type in flattened_object_type.property_types.items():
        raw_live_column = _extract_column_from_live_data(raw_live_data, col_name)
        processed_live_column = None
        if _column_contains_legacy_media_image(col_type):
            # If the column contains an image-file type, then we need to figure
            # out a more specific type for the column based on the first few
            # rows. This is an unfortunate side-effect of the fact that we don't
            # store image annotation metadata in the type system. See
            # `_patch_legacy_image_file_types` for more details on how we handle
            # this for older tables. This operation must be done on the liveset
            # and the history parquet tables, and the underlying type must be
            # updated accordingly. Not only that, but mask & box data are
            # variadic in type and sometimes require reading more files from
            # disk to understand the type. This is basically a dead end here -
            # unless we want to literally read the entire history parquet file
            # into memory, and then download all the image annotation data... We
            # have to then propagate back all the type changes... This is
            # horribly inefficient and we should probably just move on from
            # legacy image files
            pass
        if _column_type_requires_in_memory_transformation(col_type):
            _non_vectorized_warning(
                f"Encountered a history column requiring non-vectorized, in-memory processing: {col_name}: {col_type}"
            )
            processed_live_column = _process_column_in_memory(raw_live_column, run_path)
            live_columns[col_name] = processed_live_column

            for table_ndx, table in enumerate(processed_history_pa_tables):
                if not _pa_table_has_column(table, col_name):
                    new_table = _new_pa_table_column(
                        table, col_name, _create_empty_column(table, col_type, artifact)
                    )
                else:
                    new_table = _update_pa_table_column(
                        table,
                        col_name,
                        _process_history_column_in_memory(
                            table[col_name], col_type, run_path, artifact
                        ),
                    )
                processed_history_pa_tables[table_ndx] = new_table

        elif _is_directly_convertible_type(col_type):
            live_columns_already_mapped[col_name] = raw_live_column
            # Important that this runs before the else branch
            continue
        else:
            processed_live_column = _reconstruct_original_live_data_col(raw_live_column)
            live_columns_already_mapped[col_name] = processed_live_column

            for table_ndx, table in enumerate(processed_history_pa_tables):
                if not _pa_table_has_column(table, col_name):
                    new_table = _new_pa_table_column(
                        table, col_name, _create_empty_column(table, col_type, artifact)
                    )
                else:
                    new_col = _drop_types_from_encoded_types(
                        ArrowWeaveList(
                            table[col_name],
                            None,
                            artifact=artifact,
                        )
                    )
                    arrow_col = new_col._arrow_data
                    if types.Timestamp().assign_type(types.non_none(col_type)):
                        arrow_col = arrow_col.cast("int64").cast(
                            pa.timestamp("ms", tz="UTC")
                        )
                    new_table = _update_pa_table_column(table, col_name, arrow_col)
                processed_history_pa_tables[table_ndx] = new_table

    return live_columns, live_columns_already_mapped, processed_history_pa_tables


def _non_vectorized_warning(message: str):
    logging.warning(message)
    if get_error_on_non_vectorized_history_transform():
        raise errors.WeaveWBHistoryTranslationError(message)


def _build_array_from_tree(tree: PathTree) -> pa.Array:
    children_struct_array = []
    if len(tree.children) > 0:
        mask = None
        children_data = {}
        for k, v in tree.children.items():
            children_data[k] = _build_array_from_tree(v)
            child_is_null = _is_null(children_data[k])
            if mask is None:
                mask = child_is_null
            else:
                mask = pa.compute.and_(mask, child_is_null)

        children_struct = pa.StructArray.from_arrays(
            children_data.values(), children_data.keys(), mask=mask
        )
        children_struct_array = [children_struct]
    children_arrays = [*(tree.data or []), *children_struct_array]
    if len(children_arrays) == 0:
        raise errors.WeaveWBHistoryTranslationError(
            "Cannot build array from empty tree"
        )

    children_arrays_nonnull = [
        x for x in children_arrays if not isinstance(x, pa.NullArray)
    ]
    if not children_arrays_nonnull:
        children_arrays = [children_arrays[0]]
    else:
        children_arrays = children_arrays_nonnull

    if len(children_arrays) == 1:
        return children_arrays[0]

    num_rows = len(children_arrays[0])

    return _union_from_column_data(num_rows, children_arrays)


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
        if not isinstance(target.data, list):
            raise errors.WeaveWBHistoryTranslationError(
                f"Encountered unexpected data in PathTree: {type(target.data)}"
            )
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
        arrow_data = awl._arrow_data
        arrow_columns = [c.name for c in arrow_data.type]
        if all([c.startswith("_type_") for c in columns]):
            logging.warning(
                f"Encountered history store union: this requires a non-vectorized transformation on the order of number of rows (but fortunately does not require transforming to python). Path: {path}, Type: {object_type}"
            )
            num_rows = len(arrow_data)
            weave_type_members = []
            for col_name in columns:
                weave_type_members.append(object_type.property_types[col_name])

            union_arr = _union_from_column_data(
                num_rows,
                [
                    arrow_data.field(arrow_columns.index(col_name))
                    for col_name in columns
                ],
            )
            return ArrowWeaveList(
                union_arr, types.union(*weave_type_members), awl._artifact
            )

    return None


def _union_from_column_data(num_rows: int, columns: list[pa.Array]) -> pa.Array:
    type_array = pa.nulls(num_rows, type=pa.int8())
    offset_array = pa.nulls(num_rows, type=pa.int32())
    arrays = []
    for col_ndx, column_data in enumerate(columns):
        if col_ndx == 0:
            # We always take the entire first column, then replace with mask
            # each subsequent column. This approach ensures that rows which have
            # nulls for every single column can be properly represented (ie. by the
            # first column)
            new_data = column_data
            arrays.append(new_data)
            type_array = pa.array([col_ndx] * len(new_data), type=pa.int8())
            offset_array = pa.array(list(range(len(new_data))), type=pa.int32())
            continue
        is_usable = pa.compute.invert(_is_null(column_data))
        new_data = column_data.filter(is_usable)
        arrays.append(new_data)
        type_array = pa.compute.replace_with_mask(
            type_array,
            is_usable,
            pa.array([col_ndx] * len(is_usable), type=pa.int8()),
        )
        offset_array = pa.compute.replace_with_mask(
            offset_array,
            is_usable,
            pa.array(list(range(len(new_data))), type=pa.int32()),
        )

    # TODO: This code tries to add a null we can use, but it makes the
    # union invalid against the weave type. Instead we can just use the first
    # array in the union.
    # TODO: Need to fix this code, it is not correct now, just hacked in the branch
    # arrays.append(pa.nulls(1, type=pa.int8()))
    #
    # Following lines are from weaveflow merge, but i believe this is already fixed
    #
    # type_array = pa.compute.fill_null(type_array, len(arrays) - 1)
    # offset_array = pa.compute.fill_null(offset_array, 0)

    return pa.UnionArray.from_dense(type_array, offset_array, arrays)


def _is_null(array: pa.Array) -> pa.Array:
    if isinstance(array, pa.ChunkedArray):
        array = array.combine_chunks()

    base_truth = pa.compute.is_null(array)

    if pa.types.is_struct(array.type):
        children_nulls = [_is_null(array.field(i)) for i in range(len(array.type))]
        if len(children_nulls) == 0:
            return pa.array([True] * len(array), type=pa.bool_())
        else:
            curr = children_nulls[0]
            for child in children_nulls[1:]:
                curr = pa.compute.and_(curr, child)
            return pa.compute.or_(curr, base_truth)

    return base_truth


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
    return None


def _drop_types_from_encoded_types(awl: ArrowWeaveList) -> ArrowWeaveList:
    return awl.map_column(_drop_types_mapper)


def _get_live_data_from_run(run: wdt.Run, columns=None):
    raw_live_data = run["sampledParquetHistory"]["liveData"]
    if columns is None:
        return raw_live_data
    column_set = set(columns)
    return [
        {k: v for k, v in row.items() if k in column_set}
        for row in gql_json_cache.use_json(raw_live_data)
    ]


def _extract_column_from_live_data(live_data: list[dict], column_name: str):
    return [row.get(column_name, None) for row in live_data]


def _process_column_in_memory(live_column: list, run_path: wb_util.RunPath) -> list:
    return [_process_live_object_in_memory(item, run_path) for item in live_column]


def _process_live_object_in_memory(
    live_data: typing.Any, run_path: wb_util.RunPath
) -> typing.Any:
    if isinstance(live_data, list):
        return [_process_live_object_in_memory(cell, run_path) for cell in live_data]
    if isinstance(live_data, dict):
        if live_data.get("_type") != None:
            return wb_util._process_run_dict_item(live_data, run_path)
        else:
            return {
                key: _process_live_object_in_memory(val, run_path)
                for key, val in live_data.items()
            }
    return live_data


def _process_history_column_in_memory(
    history_column: pa.Array,
    col_type: types.Type,
    run_path: wb_util.RunPath,
    artifact: artifact_base.Artifact,
) -> pa.Array:
    pyobj = history_column.to_pylist()
    processed_data = _process_column_in_memory(pyobj, run_path)
    awl = convert.to_arrow(
        processed_data,
        types.List(col_type),
        artifact=artifact,
    )
    return pa.chunked_array([awl._arrow_data])


# Copy from common - need to merge back
def _read_raw_history_awl_tables(
    run: wdt.Run,
    columns=None,
    artifact: typing.Optional[artifact_base.Artifact] = None,
) -> list[ArrowWeaveList]:
    io = io_service.get_sync_client()
    tables = []
    for url in run["sampledParquetHistory"]["parquetUrls"]:
        local_path = io.ensure_file_downloaded(url)
        if local_path is not None:
            path = io.fs.path(local_path)
            awl = history_op_common.awl_from_local_parquet_path(
                path, None, columns=columns, artifact=artifact
            )
            awl = awl.map_column(_parse_bytes_mapper)
            tables.append(awl)
    return tables

    # return history_op_common.process_history_awl_tables(tables)


def _parse_bytes_to_json(bytes: bytes):
    return json.loads(bytes.decode("utf-8"))


def _parse_bytes_mapper(
    awl: ArrowWeaveList, path: PathType
) -> typing.Optional[ArrowWeaveList]:
    obj_type = types.non_none(awl.object_type)
    if types.Bytes().assign_type(obj_type):
        if len(awl._arrow_data) == awl._arrow_data.null_count:
            return make_vec_none(len(awl._arrow_data))
        _non_vectorized_warning(
            f"Encountered bytes in column {path}, requires in-memory processing"
        )
        data = [
            _parse_bytes_to_json(row) if row is not None else None
            for row in awl._arrow_data.to_pylist()
        ]
        wb_type = types.TypeRegistry.type_of(data)
        if not hasattr(wb_type, "object_type"):
            raise errors.WeaveWBHistoryTranslationError(
                f"Expected type with object_type attribute, got {wb_type}"
            )
        wb_type = typing.cast(types.List, wb_type)
        return convert.to_arrow_from_list_and_artifact(
            data,
            wb_type.object_type,
            artifact=awl._artifact or artifact_mem.MemArtifact(),
            py_objs_already_mapped=True,
        )
    return None


def _column_type_requires_in_memory_transformation(col_type: types.Type):
    return _column_type_requires_in_memory_transformation_recursive(col_type)


def _column_contains_legacy_media_image(col_type: types.Type):
    return _column_contains_legacy_media_image_recursive(col_type)


def _is_directly_convertible_type(col_type: types.Type):
    return _is_directly_convertible_type_recursive(col_type)


_weave_types_requiring_in_memory_transformation = (
    # TODO: We should be able to move some (or all?) of these to
    # a vectorized approach. At a minimum we should be able to do
    # this for ImageArtifactFileRefType - similar to how we do it
    # in history2.
    wbmedia.ImageArtifactFileRefType,  # type: ignore
    wbmedia.AudioArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.BokehArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.VideoArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.Object3DArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.MoleculeArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.HtmlArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.LegacyTableNDArrayType,
    wb_util.WbHistogram,
    trace_tree.WBTraceTree.WeaveType,  # type: ignore
    types.UnknownType,
    artifact_fs.FilesystemArtifactFileType,  # Tables
)


def _column_type_requires_in_memory_transformation_recursive(col_type: types.Type):
    if types.NoneType().assign_type(col_type):
        return False
    non_none_type = types.non_none(col_type)
    if isinstance(non_none_type, types.UnionType):
        return True
    elif isinstance(non_none_type, _weave_types_requiring_in_memory_transformation):
        return True
    elif isinstance(non_none_type, types.List):
        return _column_type_requires_in_memory_transformation_recursive(
            non_none_type.object_type
        )
    elif isinstance(non_none_type, types.TypedDict):
        for k, v in non_none_type.property_types.items():
            if _column_type_requires_in_memory_transformation_recursive(v):
                return True
        return False
    else:
        return False


def _column_contains_legacy_media_image_recursive(col_type: types.Type):
    if types.NoneType().assign_type(col_type):
        return False
    non_none_type = types.non_none(col_type)
    if isinstance(non_none_type, types.UnionType):
        return True
    elif isinstance(non_none_type, wbmedia.ImageArtifactFileRefType):
        return True
    elif isinstance(non_none_type, types.List):
        return _column_type_requires_in_memory_transformation_recursive(
            non_none_type.object_type
        )
    elif isinstance(non_none_type, types.TypedDict):
        for k, v in non_none_type.property_types.items():
            if _column_type_requires_in_memory_transformation_recursive(v):
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


def _reconstruct_original_live_data_col(row: list):
    return [_reconstruct_original_live_data_cell(cell) for cell in row]


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
