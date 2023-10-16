import json
import typing

from ... import graph
from ... import compile
from ... import op_args
from ... import registry_mem
from ... import weave_types as types
from .. import wb_domain_types as wdt
from ...ops_primitives import make_list
from ...ops_arrow.list_ops import concat
from ...ops_arrow import ArrowWeaveList
from ... import util
from ... import errors
from ... import io_service
from ...mappers_arrow import map_to_arrow
from ... import engine_trace
from ...compile_domain import InputAndStitchProvider
from ... import compile_table
from ... import artifact_base
from ...language_features.tagging.tagged_value_type import TaggedValueType

from ...api import use

import pyarrow as pa
from pyarrow import parquet as pq


from .. import wb_util
from .. import table

from ... import artifact_fs
from ...wandb_interface import wandb_stream_table
from ...compile_table import KeyTree
from ...ops_primitives import _dict_utils
from ... import gql_json_cache

tracer = engine_trace.tracer()


class TypeCount(typing.TypedDict):
    type: typing.Optional[str]
    count: int
    keys: dict[str, list["TypeCount"]]  # type: ignore
    items: list["TypeCount"]  # type: ignore
    nested_types: list[str]


def history_key_type_count_to_weave_type(tc: TypeCount) -> types.Type:
    from ..wbmedia import ImageArtifactFileRefType
    from ..trace_tree import WBTraceTree

    tc_type = tc["type"]
    if tc_type == "string":
        return types.String()
    elif tc_type == "number":
        return types.Number()
    elif tc_type == "nil":
        return types.NoneType()
    elif tc_type == "bool":
        return types.Boolean()
    elif tc_type == "map":
        keys = tc["keys"] if "keys" in tc else {}
        return types.TypedDict(
            {
                key: types.union(
                    *[history_key_type_count_to_weave_type(vv) for vv in val]
                )
                for key, val in keys.items()
            }
        )
    elif tc_type == "list":
        if "items" not in tc:
            return types.List(types.UnknownType())
        return types.List(
            types.union(*[history_key_type_count_to_weave_type(v) for v in tc["items"]])
        )
    elif tc_type == "histogram":
        return wb_util.WbHistogram.WeaveType()  # type: ignore
    elif tc_type == "table-file":
        extension = types.Const(types.String(), "json")
        return artifact_fs.FilesystemArtifactFileType(extension, table.TableType())
    elif tc_type == "joined-table":
        extension = types.Const(types.String(), "json")
        return artifact_fs.FilesystemArtifactFileType(
            extension, table.JoinedTableType()
        )
    elif tc_type == "partitioned-table":
        extension = types.Const(types.String(), "json")
        return artifact_fs.FilesystemArtifactFileType(
            extension, table.PartitionedTableType()
        )
    elif tc_type == "image-file":
        return ImageArtifactFileRefType()
    elif tc_type == "wb_trace_tree":
        return WBTraceTree.WeaveType()  # type: ignore
    elif tc_type == "images/separated":
        return types.List(ImageArtifactFileRefType())
    elif isinstance(tc_type, str):
        possible_type = wandb_stream_table.maybe_history_type_to_weave_type(tc_type)
        if possible_type is not None:
            return possible_type

    # Hack: there are circumstances where the user has logged data with a
    # `_type` key. This is nasty... because so much of our logic depends on
    # `_type` being a reserved key. In such circumstances the gorilla history
    # parser will still return the correct keys. This is essentially the same as
    # the `map` case above. This MUST go last however, since we want to properly
    # catch any named types first.
    if "keys" in tc:
        return types.TypedDict(
            {
                key: types.union(
                    *[history_key_type_count_to_weave_type(vv) for vv in val]
                )
                for key, val in tc["keys"].items()
            }
        )
    return types.UnknownType()


def get_top_level_keys(key_tree: KeyTree) -> list[str]:
    top_level_keys = list(
        map(
            _dict_utils.unescape_dots,
            set(
                next(iter(_dict_utils.split_escaped_string(key)))
                for key in key_tree.keys()
            ),
        )
    )
    return top_level_keys


def get_full_columns(columns: typing.Optional[list[str]]):
    if columns is None:
        return None
    return list(set([*columns, "_step"]))


def get_full_columns_prefixed(run: wdt.Run, columns: typing.Optional[list[str]]):
    all_columns = get_full_columns(columns)
    all_paths = list(
        gql_json_cache.use_json(run.get("historyKeys", "{}")).get("keys", {}).keys()
    )
    return _filter_known_paths_to_requested_paths(all_paths, all_columns)


def flatten_typed_dicts(type_: types.TypedDict) -> list[str]:
    props = type_.property_types
    paths = []
    for key, val in props.items():
        if types.optional(types.TypedDict({})).assign_type(
            val
        ) and not types.NoneType().assign_type(val):
            subpaths = flatten_typed_dicts(typing.cast(types.TypedDict, val))
            paths += [f"{key}.{path}" for path in subpaths]
        else:
            paths.append(key)
    return list(set(paths))


def _without_tags(type_: types.Type) -> types.Type:
    if isinstance(type_, TaggedValueType):
        return _without_tags(type_.value)
    return type_


def _is_list_like(type_: types.Type) -> bool:
    return hasattr(type_, "object_type")


def _is_dict_like(type_: types.Type) -> bool:
    return hasattr(type_, "property_types")


def _get_key_typed_node(node: graph.Node) -> graph.Node:
    with tracer.trace("run_history_inner_refine") as span:
        # This block will not normally be needed. But in some cases (for example lambdas)
        # we will have to refine the node to get the history type.
        if not isinstance(node, graph.OutputNode):
            raise errors.WeaveWBHistoryTranslationError(
                f"Expected output node, found {type(node)}"
            )
        op = registry_mem.memory_registry._ops[node.from_op.name]
        with compile.enable_compile():
            if not isinstance(op.input_type, op_args.OpNamedArgs):
                raise errors.WeaveWBHistoryTranslationError(
                    f"Expected named args, found {type(op.input_type)}"
                )
            return op.lazy_call(
                **{
                    k: n
                    for k, n in zip(
                        op.input_type.arg_types, node.from_op.inputs.values()
                    )
                }
            )


def _filter_known_paths_to_requested_paths(
    known_paths: list[str], requested_paths: list[str]
) -> list[str]:
    history_cols = []
    for path in known_paths:
        for requested_path in requested_paths:
            if path == requested_path or path.startswith(requested_path + "."):
                history_cols.append(path)
    return history_cols


def _history_node_known_keys(node: graph.Node) -> list[str]:
    node_type = node.type

    # First, we expect the type to be list like
    if not _is_list_like(node_type):
        return []

    node_type = typing.cast(types.List, node_type)
    node_type = node_type.object_type

    # Next, it is possible we have one more layer of list (if the
    # node was mapped)
    if _is_list_like(node_type):
        node_type = typing.cast(types.List, node_type)
        node_type = node_type.object_type

    # Finally, we would expect the node to be dict like and have
    # at least one property.
    if _is_dict_like(node_type):
        node_type = typing.cast(types.TypedDict, node_type)
        if len(node_type.property_types) > 0:
            node_type = typing.cast(types.TypedDict, _without_tags(node_type))
            return flatten_typed_dicts(node_type)

    return []


def make_run_history_gql_field(inputs: InputAndStitchProvider, inner: str):
    # Must be kept in sync with compile_domain:_field_selections_hardcode_merge
    # I moved the column pushdown before the gql step, so we actually have the
    # columns directly available here.... could be possible we need to revisit
    top_level_keys = inputs.raw.get("history_cols")
    if top_level_keys == None:
        stitch_obj = inputs.stitched_obj
        key_tree = compile_table.get_projection(stitch_obj)

        # we only pushdown the top level keys for now.
        top_level_keys = get_top_level_keys(key_tree)

    if not top_level_keys:
        # If no keys, then we cowardly refuse to blindly fetch entire history table
        return "historyKeys"

    # We need to figure out the known history keys. In the vast majority of
    # situations, the node's type will contain this information (by virtue of
    # the refinement step during compilation. There is an edge case with nested
    # lambdas where this will not be the case, and we need to explicitly call
    # `_get_key_typed_node` to get the correctly typed node. Moreover, we need
    # to properly handle mapping here. The fallback is to just use the `_step`
    # key.
    all_known_paths = ["_step"]

    node = inputs.stitched_obj.node
    paths_from_node = _history_node_known_keys(inputs.stitched_obj.node)

    # If we don't have any paths from the node, then we need to refine it.
    if len(paths_from_node) == 0:
        node = _get_key_typed_node(node)
        paths_from_node = _history_node_known_keys(node)

    all_known_paths += paths_from_node

    history_cols = _filter_known_paths_to_requested_paths(
        list(set(all_known_paths)), get_full_columns(top_level_keys)
    )

    project_fragment = """
        project {
        id
        name
        entity {
            id
            name
        }
    }
    """

    return f"""
    historyKeys
    sampledParquetHistory: parquetHistory(liveKeys: {json.dumps(history_cols)}) {{
        liveData
        parquetUrls
    }}
    {project_fragment}
    """


def refine_history_type(
    run: wdt.Run,
    columns: typing.Optional[list[str]] = None,
) -> types.TypedDict:
    if "historyKeys" not in run.keys:
        raise ValueError("historyKeys not in run gql")

    historyKeys = gql_json_cache.use_json(run["historyKeys"])["keys"]

    return _refine_history_type_inner(historyKeys, columns)


def _refine_history_type_inner(
    historyKeys: dict[str, dict],
    columns: typing.Optional[list[str]] = None,
) -> types.TypedDict:
    prop_types: dict[str, types.Type] = {}
    for key, key_details in historyKeys.items():
        if key.startswith("system/") or (columns is not None and key not in columns):
            # skip system metrics for now
            continue

        type_counts: list[TypeCount] = key_details["typeCounts"]
        wt = types.union(
            *[history_key_type_count_to_weave_type(tc) for tc in type_counts]
        )

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

    return types.TypedDict(prop_types)


def history_keys(run: wdt.Run) -> list[str]:
    if "historyKeys" not in run.keys:
        raise ValueError("historyKeys not in run gql")
    if "sampledParquetHistory" not in run.keys:
        raise ValueError("sampledParquetHistory not in run gql")
    object_type = refine_history_type(run)

    return list(object_type.property_types.keys())


def awl_from_local_parquet_path(
    path: str,
    object_type: typing.Optional[types.TypedDict],
    columns: list[str] = [],
    artifact: typing.Optional[artifact_base.Artifact] = None,
) -> ArrowWeaveList:
    with tracer.trace("pq.read_metadata") as span:
        span.set_tag("path", path)
        meta = pq.read_metadata(path)
    file_schema = meta.schema
    columns_to_read = [c for c in columns if c in file_schema.to_arrow_schema().names]
    with tracer.trace("pq.read_table") as span:
        span.set_tag("path", path)
        table = pq.read_table(path, columns=columns_to_read)

    # convert table to ArrowWeaveList
    with tracer.trace("make_awl") as span:
        awl: ArrowWeaveList = ArrowWeaveList(
            table, object_type=object_type, artifact=artifact
        )
    return awl


def process_history_awl_tables(tables: list[ArrowWeaveList]):
    concatted = concat_awls(tables)
    if isinstance(concatted, ArrowWeaveList):
        parquet_history = awl_to_pa_table(concatted)
    else:
        # empty table
        return None

    return sort_history_pa_table(parquet_history)


def concat_awls(awls: list[ArrowWeaveList]):
    list = make_list(**{str(i): table for i, table in enumerate(awls)})
    with compile.disable_compile():
        return use(concat(list))


def awl_to_pa_table(awl: ArrowWeaveList):
    rb = pa.RecordBatch.from_struct_array(
        awl._arrow_data
    )  # this pivots to columnar layout
    return pa.Table.from_batches([rb])


def sort_history_pa_table(table: pa.Table):
    with tracer.trace("pq.sort"):
        table_sorted_indices = pa.compute.bottom_k_unstable(
            table, sort_keys=["_step"], k=len(table)
        )

    with tracer.trace("pq.take"):
        return table.take(table_sorted_indices)


def read_history_parquet(run: wdt.Run, columns=None):
    io = io_service.get_sync_client()
    object_type = refine_history_type(run, columns=columns)
    tables = []
    for url in run["sampledParquetHistory"]["parquetUrls"]:
        local_path = io.ensure_file_downloaded(url)
        if local_path is not None:
            path = io.fs.path(local_path)
            awl = awl_from_local_parquet_path(path, object_type, columns=columns)
            tables.append(awl)
    if len(tables) == 0:
        return None
    return process_history_awl_tables(tables)


def mock_history_rows(
    run: wdt.Run, use_arrow: bool = True
) -> typing.Union[ArrowWeaveList, list]:
    # we are in the case where we have blindly requested the entire history object.
    # we refuse to fetch that, so instead we will just inspect the historyKeys and return
    # a dummy history object that can bte used as a proxy for downstream ops (e.g., count).

    step_type = types.TypedDict({"_step": types.Int()})
    steps: typing.Union[ArrowWeaveList, list] = []
    history_keys = gql_json_cache.use_json(run["historyKeys"])

    last_step = history_keys["lastStep"]
    keys = history_keys["keys"]
    for key, key_details in keys.items():
        if key == "_step":
            type_counts: list[TypeCount] = key_details["typeCounts"]
            count = type_counts[0]["count"]
            # generate fake steps
            steps = [{"_step": i} for i in range(count)]
            steps[-1]["_step"] = last_step
            assert len(steps) == count
            break

    if use_arrow:
        mapper = map_to_arrow(step_type, None, [])
        result = pa.array(steps, type=mapper.result_type())
        steps = ArrowWeaveList(result, step_type)

    return steps
