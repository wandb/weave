import dataclasses
import datetime
import typing
import pyarrow.compute as pc
import pyarrow as pa

from weave import io_service
from weave.language_features.tagging.tagged_value_type import TaggedValueType
from ...ops_arrow.list_ import (
    PathItemList,
    PathItemObjectField,
    PathItemOuterList,
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
    return ArrowWeaveListType(_refine_history_type(run).weave_type)


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history_stream_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    return ArrowWeaveListType(
        _refine_history_type(
            run, columns=list(set([*history_cols, "_step"]))
        ).weave_type
    )


@op(
    name="run-history_stream_with_columns",
    refine_output_type=refine_history_stream_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history_stream_with_columns(run: wdt.Run, history_cols: list[str]):
    return _get_history_stream(run, list(set([*history_cols, "_step"])))


@op(
    name="run-history_stream",
    refine_output_type=refine_history_stream_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history_stream(run: wdt.Run):
    # We return mock data here since we will be replaced with the `_with_columns`
    # version in a compile pass if specific columns are needed
    return history_op_common.mock_history_rows(run)


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


def _refine_history_type(
    run: wdt.Run,
    columns: typing.Optional[list[str]] = None,
) -> HistoryToWeaveFinalResult:
    if "historyKeys" not in run.gql:
        raise ValueError("historyKeys not in run gql")

    historyKeys = run.gql["historyKeys"]["keys"]
    return _refine_history_type_inner(historyKeys, columns=columns)


class TopLevelTypeCount(typing.TypedDict):
    typeCounts: list[history_op_common.TypeCount]


# split out for testing
def _refine_history_type_inner(
    historyKeys: dict[str, TopLevelTypeCount],
    columns: typing.Optional[list[str]] = None,
) -> HistoryToWeaveFinalResult:
    prop_types: dict[str, types.Type] = {}
    encoded_paths: list[list[str]] = []

    for key, key_details in historyKeys.items():
        if key.startswith("system/") or (columns is not None and key not in columns):
            # skip system metrics for now
            continue

        type_counts: list[history_op_common.TypeCount] = key_details["typeCounts"]
        type_members = []
        for tc in type_counts:
            res = _history_key_type_count_to_weave_type(tc, key)
            type_members.append(res.weave_type)
            encoded_paths.extend(res.encoded_paths)
        wt = types.union(*type_members)

        if wt == types.UnknownType():
            util.capture_exception_with_sentry_if_available(
                errors.WeaveTypeWarning(
                    f"Unable to determine history key type for key {key} with types {type_counts}"
                ),
                (str([tc["type"] for tc in type_counts]),),
            )
            wt = types.NoneType()

        # _step is a special key that is always guaranteed to be a nonnull number.
        # other keys may be undefined at particular steps so we make them optional.
        if key in ["_step", "_runtime", "_timestamp"]:
            prop_types[key] = wt
        else:
            prop_types[key] = types.optional(wt)

    # Need to combine top-level maps. Note: this is not a recursive function
    # since the flattening only happens top level in gorilla.
    dict_keys: dict[str, types.Type] = {}
    for key, val in prop_types.items():
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

    encoded_paths_final = []
    for path in encoded_paths:
        if len(encoded_paths) > 0:
            if "." in path[0]:
                new_path = [*path[0].split("."), *path[1:]]
                encoded_paths_final.append(new_path)
            else:
                encoded_paths_final.append(path)

    return HistoryToWeaveFinalResult(types.TypedDict(dict_keys), encoded_paths_final)


# Copy from common - need to merge back
def _read_history_parquet(run: wdt.Run, object_type, columns=None):
    io = io_service.get_sync_client()
    tables = []
    # FIXME: according to MinYoung, the tables MAY have different schemas before
    # compaction. Need to move _convert_gorilla_parquet_to_weave_arrow  to this
    # loop. This will require modifying tests too
    for url in run.gql["sampledParquetHistory"]["parquetUrls"]:
        local_path = io.ensure_file_downloaded(url)
        if local_path is not None:
            path = io.fs.path(local_path)
            awl = history_op_common.local_path_to_parquet_table(
                path, None, columns=columns
            )
            tables.append(awl)
    return history_op_common.process_history_awl_tables(tables)


def _get_history_stream(run: wdt.Run, columns=None):
    final_object_type = _refine_history_type(run, columns=columns)
    parquet_history = _read_history_parquet(
        run, final_object_type.weave_type, columns=columns
    )
    live_data = run.gql["sampledParquetHistory"]["liveData"]
    return _get_history_stream_inner(final_object_type, live_data, parquet_history)


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
            # parquet_history = pa.StructArray.from_arrays(
            #     # TODO: we shouldn't need to combine chunks, we can produce this in the
            #     # original chunked form for zero copy
            #     [c.combine_chunks() for c in parquet_history.columns],
            #     names=parquet_history.column_names,
            # )
            # parquet_history = _convert_gorilla_parquet_to_weave_arrow(
            #     parquet_history, object_type, artifact
            # )
    else:
        parquet_history = []

    if len(live_data_processed) == 0 and len(parquet_history) == 0:
        return ArrowWeaveList(pa.array([]), object_type, artifact=artifact)
    elif len(live_data_processed) == 0:
        return parquet_history
    elif len(parquet_history) == 0:
        return live_data_processed
    return use(concat([parquet_history, live_data_processed]))


def _convert_gorilla_parquet_to_weave_arrow(
    gorilla_parquet, target_object_type, artifact
):
    # Note: this arrow Weave List is NOT properly constructed. We blindly create it from the gorilla parquet
    gorilla_awl = ArrowWeaveList(
        gorilla_parquet,
        artifact=artifact,
    )

    prototype_awl = convert.to_arrow(
        [],
        types.List(target_object_type),
        artifact=artifact,
    )

    target_path_types = {}

    def path_accumulator(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional["ArrowWeaveList"]:
        nonlocal target_path_types
        target_path_types[path] = awl.object_type
        return None

    prototype_awl.map_column(path_accumulator)

    def pre_mapper(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional["ArrowWeaveList"]:
        if path == ():  # root
            return None

        # Here we want to:
        # a) unflatten the top-level dictionaries (i believe gorilla will have them dot-separated)
        # b) reduce the encoded cells to their vals (this should only be Object and Custom Types)
        # c) Modify non-simple unions to our union structure
        if path not in target_path_types:
            raise ValueError(f"Path {path} not found in target path types")

        target_type = target_path_types[path]
        if types.is_optional(target_type):
            target_type = types.non_none(target_type)
        current_type = awl.object_type
        if types.is_optional(current_type):
            current_type = types.non_none(current_type)

        # If the types are the same, we don't need to do anything! That is the happy state
        if types.optional(target_type).assign_type(current_type):
            return None

        # If both types are list-like, then we can handle the differences on the next loop
        base_list_type = types.optional(types.List())
        if base_list_type.assign_type(target_type) and base_list_type.assign_type(
            current_type
        ):
            return None

        # If both types are unions, we are in trouble. Have to somehow map the union types from gorilla
        # to the union types in weave. This is a hard problem.
        # if isinstance(target_type, types.UnionType) and isinstance(current_type, types.UnionType):

        # TODO: Unions...
        # TODO: Generalize this to not blindly assume _val
        # TODO: This double val goes away
        data = awl._arrow_data.field("_val").field("_val")

        if target_type.assign_type(types.Timestamp()):
            data = (
                pc.floor(data)
                .cast("int64")
                .cast(pa.timestamp("ms", tz=datetime.timezone.utc))
            )

        return ArrowWeaveList(
            data,
            target_type,
            awl._artifact,
        )
        return None

    def post_mapper(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional["ArrowWeaveList"]:
        return None

    corrected_awl = gorilla_awl.map_column(post_mapper, pre_mapper)

    reason = weave_arrow_type_check(target_object_type, corrected_awl._arrow_data)

    if reason != None:
        raise ValueError(
            f"Failed to effectively convert Gorilla Parquet History to expected history type: {reason}"
        )

    return corrected_awl


def _reconstruct_original_live_data(live_data: list[dict]):
    # in this function we want to:
    # a) unflatted top-level dictionaries
    # b) reduce the encoded cells to their vals

    return [_reconstruct_original_live_data_row(row) for row in live_data]


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


# list(zip(parquet_history.schema.names, parquet_history.schema.types))

# Plan:
## 1) convert history keys to weave type
## 2) convert weave type to arrow type (target type)
## 3) for each path (leaf column) in the target arrow type,
#           map to the weave type leaf path (pretty sure i can this)
#           map from the weave type leaf path to the gorilla parquet leaf path ()
#           copy the gorilla parquet leaf path to the target arrow type leaf path


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

    column_map: dict[PathType, pa.Array] = {}

    def column_getter(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        nonlocal column_map
        column_map[path] = awl._arrow_data
        return None

    gorilla_awl.map_column(column_getter)

    def column_setter(
        awl: ArrowWeaveList, path: PathType
    ) -> typing.Optional[ArrowWeaveList]:
        nonlocal target_path_summary
        if path not in target_path_summary.leaf_paths:
            return None
        target_spec = target_path_summary.leaf_paths[path]
        source_path = target_spec.remap_path
        if source_path not in column_map:
            raise ValueError(f"Failed to find source path {source_path}")
        data_array = column_map[source_path]
        reason = weave_arrow_type_check(target_spec.weave_type, data_array)

        if reason != None:
            raise ValueError(
                f"Failed to effectively convert Gorilla Parquet History to expected history type: {reason}"
            )
        return ArrowWeaveList(
            data_array,
            target_spec.weave_type,
            awl._artifact,
        )

    corrected_awl = prototype_awl.map_column(column_setter)
    # for target_spec in target_path_summary.leaf_paths.values():
    #     source_path: PathType = _target_awl_spec_to_gorilla_path(target_spec, current_path_summary.all_paths)
    #     data_array = _get_data_at_path(gorilla_parquet, source_path)
    #     _update_data_at_path(final_awl, target_spec.arrow_leaf_path, data_array)

    reason = weave_arrow_type_check(target_object_type, corrected_awl._arrow_data)

    if reason != None:
        raise ValueError(
            f"Failed to effectively convert Gorilla Parquet History to expected history type: {reason}"
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


# @dataclasses.dataclass
# class PathTree:
#     children: typing.Dict[PathItemType, "PathTree"] = dataclasses.field(default_factory=dict)
#     data: TargetAWLSpec


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
        final_path = path[-1]
        weave_type = awl.object_type
        arrow_type = awl._arrow_data.type
        # weave_leaf_path = PathItemOuterList
        remap_path = path
        if len(path) > 1:
            parent_path = tuple(path[:-1])
            if parent_path not in path_summary.all_paths:
                raise ValueError("Programmer Error: Path tree is not complete")
            parent_spec = path_summary.leaf_paths.pop(parent_path)

            # Construct weave_leaf_path from parent.
            # 6 Cases to handle:
            # PathItemStructField,
            # PathItemList,

            # PathItemOuterList,
            # PathItemUnionEntry,
            # PathItemObjectField,
            # PathItemTaggedValueTag,
            # PathItemTaggedValueValue,
            parent_weave_type = types.non_none(parent_spec.weave_type)
            if isinstance(parent_weave_type, primitive_types):
                raise ValueError("Parent weave type cannot be primitive")
            elif isinstance(parent_weave_type, union_types):
                # float64 | utf8 | bool | struct | list | binary
                self_type = type.non_none(weave_type)
                if isinstance(self_type, primitive_types):
                    if isinstance(
                        self_type,
                        (
                            types.Number,
                            types.Int,
                            types.Float,
                        ),
                    ):
                        remap_path = (PathItemStructField("_type_float64"),)
                    elif isinstance(self_type, (types.Boolean,)):
                        remap_path = (PathItemStructField("_type_bool"),)
                    elif isinstance(self_type, (types.String,)):
                        remap_path = (PathItemStructField("_type_utf8"),)
                    else:
                        raise ValueError("Programmer Error: Unhandled primitive type")
                elif isinstance(self_type, union_types):
                    raise ValueError("Programmer Error: Unhandled union type")
                elif isinstance(self_type, list_types):
                    remap_path = (PathItemStructField("_type_list"),)
                elif isinstance(self_type, dict_types):
                    remap_path = (PathItemStructField("_type_struct"),)
                elif isinstance(self_type, object_types):
                    remap_path = (PathItemStructField("_type_struct"),)
                elif isinstance(self_type, custom_types):
                    remap_path = (
                        PathItemStructField("_type_struct"),
                        PathItemStructField("_type_val"),
                    )
                else:
                    raise ValueError("Programmer Error: Unhandled type")
            elif isinstance(parent_weave_type, list_types):
                remap_path = (PathItemList("element"),)
            elif isinstance(parent_weave_type, dict_types):
                assert isinstance(final_path, PathItemStructField)
                remap_path = (final_path,)
            elif isinstance(parent_weave_type, object_types):
                assert isinstance(final_path, PathItemObjectField)
                remap_path = (PathItemStructField(final_path.attr),)
            elif isinstance(parent_weave_type, custom_types):
                raise ValueError("Programmer Error: Unhandled type")
            else:
                raise ValueError("Programmer Error: Unhandled type")

        path_summary.all_paths[path] = TargetAWLSpec(
            arrow_leaf_path=final_path,
            remap_path=remap_path,
            # weave_leaf_path=weave_leaf_path,
            weave_type=weave_type,
            arrow_type=arrow_type,
        )

        path_summary.leaf_paths[path] = path_summary.all_paths[path]

        return None

    prototype_awl.map_column(path_accumulator)

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


# def _target_awl_spec_to_gorilla_path(spec: TargetAWLSpec, gorilla_paths: dict[PathType, TargetAWLSpec]) -> PathType:
#     # First, assemble a path from the root to the leaf
#     target_spec_path: list[TargetAWLSpec] = []
#     curr_spec = spec
#     while curr_spec is not None:
#         target_spec_path.append(curr_spec)
#         curr_spec = curr_spec.parent
#     target_spec_path.reverse()


#     # Work backwards from the root to the leaf
#     # gorilla_path: list[PathItemType] = []

#     current_spec: typing.Optional[TargetAWLSpec] = spec


#     child_spec: typing.Optional[TargetAWLSpec] = None
#     while current_spec is not None:
#         # 6 Cases to handle:
#         weave_type = current_spec.weave_type

#         # Step 0: Break off the Nones - they are not needed.
#         if isinstance(current_spec.weave_type, types.UnionType):
#             weave_type = types.non_none(weave_type)

#         # Step 1: Check if the weave type is a primitive type
#         if isinstance(weave_type, primitive_types):
#             pass  # There is nothing to do here

#         # Step 2: Check if the weave type is a non-simple union
#         if isinstance(weave_type, union_types):
#             # When we hit a union, we would expect

#         child_spec = current_spec
#         current_spec = current_spec.parent


#     return tuple(gorilla_path[::-1])


def _reconstruct_awl_from_gorilla_parquet_outer(
    gorilla_parquet: pa.Array,
    target_object_type: types.TypedDict,
) -> pa.Array:
    artifact = artifact_mem.MemArtifact()
    prototype_awl = convert.to_arrow(
        [],
        types.List(target_object_type),
        artifact=artifact,
    )
    return _recursively_reconstruct_awl_from_gorilla_parquet(
        gorilla_parquet,
        target_object_type,
        prototype_awl._arrow_data.type,
    )


def _recursively_reconstruct_awl_from_gorilla_parquet(
    gorilla_parquet: pa.Array,
    target_object_type: types.TypedDict,
    target_pyarrow_type: pa.DataType,
) -> pa.Array:
    # arrays: list[pa.Array] = []
    current_pyarrow_type: pa.DataType = gorilla_parquet.type

    if target_pyarrow_type == current_pyarrow_type:
        return gorilla_parquet

    if (
        isinstance(target_object_type, types.UnionType)
        and target_object_type.is_simple_nullable()
    ):
        nonnull_type = [
            m for m in target_object_type.members if m.type != types.NoneType()
        ][0]

        return _recursively_reconstruct_awl_from_gorilla_parquet(
            gorilla_parquet,
            nonnull_type,
        )
    elif pa.types.is_null(target_pyarrow_type):
        # Here we want to extract just the nulls from the gorilla parquet
        return pa.array(
            pa.nulls(len(gorilla_parquet)),
            type=target_pyarrow_type,
        )
    elif pa.types.is_struct(target_pyarrow_type):
        keys: list[str] = []
        # keeps track of null values so that we can null entries at the struct level
        mask: list[bool] = []

        assert isinstance(
            target_object_type, (types.TypedDict, TaggedValueType, types.ObjectType)
        )

        # handle empty struct case - the case where the struct has no fields
        if len(target_pyarrow_type) == 0:
            return pa.array(py_objs, type=target_pyarrow_type)

        for i, field in enumerate(target_pyarrow_type):
            data: list[typing.Any] = []
            if isinstance(
                mapper,
                mappers_arrow.TypedDictToArrowStruct,
            ):
                for py_obj in py_objs:
                    if py_obj is None:
                        data.append(None)
                    else:
                        data.append(py_obj.get(field.name, None))
                    if i == 0:
                        mask.append(py_obj is None)

                array = _recursively_reconstruct_awl_from_gorilla_parquet(
                    data,
                    field.type,
                    mapper._property_serializers[field.name],
                    py_objs_already_mapped,
                )
            if isinstance(
                mapper,
                mappers_arrow.ObjectToArrowStruct,
            ):
                for py_obj in py_objs:
                    if py_obj is None:
                        data.append(None)
                    elif py_objs_already_mapped:
                        if isinstance(py_obj, dict) and "_val" in py_obj:
                            py_obj = py_obj["_val"]
                        data.append(py_obj.get(field.name, None))
                    else:
                        data.append(getattr(py_obj, field.name, None))
                    if i == 0:
                        mask.append(py_obj is None)

                array = _recursively_reconstruct_awl_from_gorilla_parquet(
                    data,
                    field.type,
                    mapper._property_serializers[field.name],
                    py_objs_already_mapped,
                )

            elif isinstance(mapper, mappers_arrow.TaggedValueToArrowStruct):
                if field.name == "_tag":
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        else:
                            data.append(tag_store.get_tags(py_obj))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = _recursively_reconstruct_awl_from_gorilla_parquet(
                        data,
                        field.type,
                        mapper._tag_serializer,
                        py_objs_already_mapped,
                    )
                else:
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        else:
                            data.append(box.unbox(py_obj))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = _recursively_reconstruct_awl_from_gorilla_parquet(
                        data,
                        field.type,
                        mapper._value_serializer,
                        py_objs_already_mapped,
                    )

            arrays.append(array)
            keys.append(field.name)
        return pa.StructArray.from_arrays(
            arrays, keys, mask=pa.array(mask, type=pa.bool_())
        )
    elif pa.types.is_union(target_pyarrow_type):
        assert isinstance(mapper, mappers_arrow.UnionToArrowUnion)
        type_codes: list[int] = [
            0
            if o == None
            else target_object_type_code_of_obj(o, py_objs_already_mapped)
            for o in py_objs
        ]
        offsets: list[int] = []
        py_data: list[list] = []
        for _ in range(len(target_pyarrow_type)):
            py_data.append([])

        for row_index, type_code in enumerate(type_codes):
            offsets.append(len(py_data[type_code]))
            py_data[type_code].append(py_objs[row_index])

        for i, raw_py_data in enumerate(py_data):
            array = _recursively_reconstruct_awl_from_gorilla_parquet(
                raw_py_data,
                target_pyarrow_type.field(i).type,
                mapper.mapper_of_type_code(i),
                py_objs_already_mapped,
            )
            arrays.append(array)

        return pa.UnionArray.from_dense(
            pa.array(type_codes, type=pa.int8()),
            pa.array(offsets, type=pa.int32()),
            arrays,
        )
    elif pa.types.is_list(target_pyarrow_type):
        assert isinstance(mapper, mappers_arrow.ListToArrowArr)
        offsets = [0]
        flattened_objs = []
        mask = []
        for obj in py_objs:
            mask.append(obj == None)
            if obj == None:
                obj = []
            offsets.append(offsets[-1] + len(obj))
            flattened_objs += obj
        new_objs = _recursively_reconstruct_awl_from_gorilla_parquet(
            flattened_objs,
            target_pyarrow_type.value_type,
            mapper._object_type,
            py_objs_already_mapped,
        )
        return pa.ListArray.from_arrays(
            offsets, new_objs, mask=pa.array(mask, type=pa.bool_())
        )

    if py_objs_already_mapped:
        return pa.array(
            [p["_val"] if isinstance(p, dict) and "_val" in p else p for p in py_objs],
            target_pyarrow_type,
        )

    values = [mapper.apply(o) if o is not None else None for o in py_objs]

    # These are plain values.

    if target_object_type == types.Number():
        # Let pyarrow infer this type.
        # This covers the case where a Weave0 table includes a Number column that
        # contains integers that are too large for float64. We map Number to float64,
        # but allow it to be int64 as well in our ArrowWeaveList.validate method.
        res = pa.array(values)
        if pa.types.is_null(res.type):
            res = res.cast(pa.int64())
    else:
        res = pa.array(values, type=target_pyarrow_type)
    return res
