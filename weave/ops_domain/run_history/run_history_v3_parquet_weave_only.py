import dataclasses
import json
import typing
from ...compile_domain import wb_gql_op_plugin
from ...api import op
from ... import weave_types as types
from .. import wb_domain_types as wdt
from ... import artifact_mem
from .. import wb_util
from ...ops_domain import wbmedia
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
def refine_weave_history_type(run: wdt.Run) -> types.Type:
    return ArrowWeaveListType(_refine_history_type(run).weave_type)


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_weave_history_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    return ArrowWeaveListType(
        _refine_history_type(
            run, columns=list(set([*history_cols, "_step"]))
        ).weave_type
    )


@op(
    name="run-weave_history_with_columns",
    refine_output_type=refine_weave_history_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def weave_history_with_columns(run: wdt.Run, history_cols: list[str]):
    _get_weave_history(run, list(set([*history_cols, "_step"])))


@op(
    name="run-weave_history",
    refine_output_type=refine_weave_history_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def weave_history(run: wdt.Run):
    # We return mock data here since we will be replaced with the `_with_columns`
    # version in a compile pass if specific columns are needed
    return history_op_common.mock_history_rows(run)


@dataclasses.dataclass
class HistoryToWeaveResult:
    weave_type: types.Type
    encoded_paths: set[list[str]] = dataclasses.field(default_factory=set)


@dataclasses.dataclass
class HistoryToWeaveFinalResult:
    weave_type: types.TypedDict
    encoded_paths: set[list[str]] = dataclasses.field(default_factory=set)


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
        paths = set([])
        for key, val in tc["keys"].items():
            key_type_members = []
            for member in val:
                res = _history_key_type_count_to_weave_type(member, key)
                key_type_members.append(res.weave_type)
                for p in res.encoded_paths:
                    paths.add([keyname, *p])
            props[key] = types.union(*key_type_members)

        return HistoryToWeaveResult(types.TypedDict(props), paths)
    elif tc_type == "list":
        if "items" not in tc:
            return HistoryToWeaveResult(types.List(types.UnknownType()))
        paths = set([])
        key_type_members = []
        for member in tc["items"]:
            res = _history_key_type_count_to_weave_type(member, "*")
            key_type_members.append(res.weave_type)
            for p in res.encoded_paths:
                paths.add([keyname, *p])

        return HistoryToWeaveResult(types.List(types.union(*key_type_members)), paths)
    elif isinstance(tc_type, str):
        possible_type = wandb_stream_table.maybe_history_type_to_weave_type(tc_type)
        if possible_type is not None:
            return HistoryToWeaveResult(possible_type, set([[keyname]]))
    return HistoryToWeaveResult(types.UnknownType())


def _refine_history_type(
    run: wdt.Run,
    columns: typing.Optional[list[str]] = None,
) -> HistoryToWeaveFinalResult:
    prop_types: dict[str, types.Type] = {}

    if "historyKeys" not in run.gql:
        raise ValueError("historyKeys not in run gql")

    historyKeys = run.gql["historyKeys"]["keys"]

    encoded_paths: set[list[str]] = set([])

    for key, key_details in historyKeys.items():
        if key.startswith("system/") or (columns is not None and key not in columns):
            # skip system metrics for now
            continue

        type_counts: list[history_op_common.TypeCount] = key_details["typeCounts"]
        type_members = []
        for tc in type_counts:
            res = _history_key_type_count_to_weave_type(tc, key)
            type_members.append(res.weave_type)
            encoded_paths.update(encoded_paths)
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

    encoded_paths_final = set([])
    for path in encoded_paths:
        if len(encoded_paths) > 0:
            if "." in path[0]:
                new_path = [*path[0].split("."), *path[1:]]
                encoded_paths_final.add(new_path)
            else:
                encoded_paths_final.add(path)

    return HistoryToWeaveFinalResult(types.TypedDict(prop_types), encoded_paths_final)


def _process_run_dict_item(val, run_path: typing.Optional[wb_util.RunPath] = None):
    if isinstance(val, dict) and "_type" in val:
        if wandb_stream_table.is_weave_encoded_history_cell(val):
            return wandb_stream_table.from_weave_encoded_history_cell(val)
        return None

    return val


def _get_weave_history(run: wdt.Run, columns=None):
    with tracer.trace("get_history") as span:
        span.set_tag("history_version", 3)
    """Dont read binary columns. Keep everything in arrow. Faster, but not as full featured as get_history"""
    final_object_type = _refine_history_type(run, columns=columns)

    scalar_keys = list(final_object_type.weave_type.property_types.keys())

    columns = [c for c in columns if c in scalar_keys]
    parquet_history = history_op_common.read_history_parquet(run, columns=columns)

    # turn the liveset into an arrow table. the liveset is a list of dictionaries
    live_data = run.gql["sampledParquetHistory"]["liveData"]
    for row in live_data:
        for colname in columns:
            if colname not in row:
                row[colname] = None
            else:
                row[colname] = _process_run_dict_item(row[colname])

    artifact = artifact_mem.MemArtifact()
    # turn live data into arrow
    if live_data is not None and len(live_data) > 0:
        with tracer.trace("live_data_to_arrow"):
            live_data = convert.to_arrow(
                live_data,
                types.List(final_object_type.weave_type),
                artifact=artifact,
            )
    else:
        live_data = []

    # THIS IS THE HARD PART: HAVE TO WRITE A TRANSLATION BETWEEN GORILLA AND WEAVE!
    # get binary fields from history schema - these are serialized json

    # if parquet_history is not None:
    #     fields = [field.name for field in parquet_history.schema]
    #     binary_fields = {
    #         field.name
    #         for field in parquet_history.schema
    #         if pa.types.is_binary(field.type)
    #     }

    #     # deserialize json if any is present
    #     with tracer.trace("process_non_basic_fields"):
    #         for field in columns:
    #             if field in binary_fields or not (
    #                 types.optional(types.BasicType()).assign_type(
    #                     final_object_type.weave_type.property_types[field]  # type: ignore
    #                 )
    #                 or wbmedia.ImageArtifactFileRefType().assign_type(
    #                     final_object_type.weave_type.property_types[field]  # type: ignore
    #                 )
    #             ):
    #                 pq_col = parquet_history[field].to_pylist()
    #                 for i, item in enumerate(pq_col):
    #                     if item is not None:
    #                         pq_col[i] = wb_util._process_run_dict_item(
    #                             json.loads(item) if field in binary_fields else item,
    #                             run_path,
    #                         )

    #                 awl = convert.to_arrow(
    #                     pq_col,
    #                     types.List(final_object_type.weave_type.property_types[field]),
    #                     artifact=artifact,
    #                 )
    #                 new_col = pa.chunked_array([awl._arrow_data])
    #                 parquet_history = parquet_history.set_column(
    #                     fields.index(field), field, new_col
    #                 )

    if parquet_history is not None and len(parquet_history) > 0:
        with tracer.trace("parquet_history_to_arrow"):
            parquet_history = ArrowWeaveList(
                parquet_history,
                final_object_type.weave_type,
                artifact=artifact,
            )
    else:
        parquet_history = []

    if len(live_data) == 0 and len(parquet_history) == 0:
        return ArrowWeaveList(
            pa.array([]), final_object_type.weave_type, artifact=artifact
        )
    elif len(live_data) == 0:
        return parquet_history
    elif len(parquet_history) == 0:
        return live_data
    return use(concat([parquet_history, live_data]))
