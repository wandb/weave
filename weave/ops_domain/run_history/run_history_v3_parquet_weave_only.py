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
        if key in ["_step"]:
            prop_types[key] = types.Int()
        elif key in ["_runtime", "_timestamp"]:
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
                # if path_part in tree.children:
                #     tree = tree.children[path_part]
                #     continue

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

    corrected_awl = prototype_awl.map_column(column_setter, retain_masks=False)

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
class PathTree:
    children: typing.Dict[PathItemType, "PathTree"] = dataclasses.field(
        default_factory=dict
    )
    data: typing.Optional[pa.Array] = None


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
