import json
import typing
from ... import weave_types as types
from .. import wb_domain_types as wdt
from . import history_util
from ...ops_primitives import make_list
from ...ops_arrow.list_ops import concat
from ...ops_arrow import ArrowWeaveList, ArrowWeaveListType
from ... import util
from ... import errors
from ... import io_service
from ...mappers_arrow import map_to_arrow
from ... import engine_trace
from ...compile_domain import InputAndStitchProvider
from ... import compile_table

from ...api import use

import pyarrow as pa
from pyarrow import parquet as pq

tracer = engine_trace.tracer()


def get_full_columns(columns: typing.Optional[list[str]]):
    if columns is None:
        return None
    return list(set([*columns, "_step", "_runtime", "_timestamp"]))


def make_run_history_gql_field(inputs: InputAndStitchProvider, inner: str):
    # Must be kept in sync with compile_domain:_field_selections_hardcode_merge

    stitch_obj = inputs.stitched_obj
    key_tree = compile_table.get_projection(stitch_obj)

    # we only pushdown the top level keys for now.
    top_level_keys = history_util.get_top_level_keys(key_tree)

    if not top_level_keys:
        # If no keys, then we cowardly refuse to blindly fetch entire history table
        return "historyKeys"

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
    sampledParquetHistory: parquetHistory(liveKeys: {json.dumps(top_level_keys)}) {{
        liveData
        parquetUrls
    }}
    {project_fragment}
    """


def refine_history_type(
    run: wdt.Run, history_version: int, columns: typing.Optional[list[str]] = None
) -> types.Type:
    prop_types: dict[str, types.Type] = {}

    if "historyKeys" not in run.gql:
        raise ValueError("historyKeys not in run gql")

    historyKeys = run.gql["historyKeys"]["keys"]

    for key, key_details in historyKeys.items():
        if key.startswith("system/") or (columns is not None and key not in columns):
            # skip system metrics for now
            continue

        type_counts: list[history_util.TypeCount] = key_details["typeCounts"]
        wt = types.union(
            *[
                history_util.history_key_type_count_to_weave_type(tc)
                for tc in type_counts
            ]
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

    ListType = ArrowWeaveListType if history_version == 2 else types.List

    return ListType(types.TypedDict(prop_types))


def history_keys(run: wdt.Run, history_version: int) -> list[str]:
    if "historyKeys" not in run.gql:
        raise ValueError("historyKeys not in run gql")
    if "sampledParquetHistory" not in run.gql:
        raise ValueError("sampledParquetHistory not in run gql")
    history_type: types.Type = refine_history_type(run, history_version)
    object_type = typing.cast(
        types.TypedDict, typing.cast(types.List, history_type).object_type
    )

    return list(object_type.property_types.keys())


def read_history_parquet(run: wdt.Run, history_version: int, columns=None):
    io = io_service.get_sync_client()
    object_type = typing.cast(
        types.List, refine_history_type(run, history_version, columns=columns)
    ).object_type
    tables = []
    for url in run.gql["sampledParquetHistory"]["parquetUrls"]:
        local_path = io.ensure_file_downloaded(url)
        if local_path is not None:
            path = io.fs.path(local_path)
            with tracer.trace("pq.read_metadata") as span:
                span.set_tag("path", path)
                meta = pq.read_metadata(path)
            file_schema = meta.schema
            columns_to_read = [
                c for c in columns if c in file_schema.to_arrow_schema().names
            ]
            with tracer.trace("pq.read_table") as span:
                span.set_tag("path", path)
                table = pq.read_table(path, columns=columns_to_read)

            # convert table to ArrowWeaveList
            with tracer.trace("make_awl") as span:
                awl: ArrowWeaveList = ArrowWeaveList(table, object_type=object_type)
            tables.append(awl)
    list = make_list(**{str(i): table for i, table in enumerate(tables)})
    concatted = use(concat(list))
    if isinstance(concatted, ArrowWeaveList):
        rb = pa.RecordBatch.from_struct_array(
            concatted._arrow_data
        )  # this pivots to columnar layout
        parquet_history = pa.Table.from_batches([rb])
    else:
        # empty table
        return None

    # sort the history by step
    with tracer.trace("pq.sort"):
        table_sorted_indices = pa.compute.bottom_k_unstable(
            parquet_history, sort_keys=["_step"], k=len(parquet_history)
        )

    with tracer.trace("pq.take"):
        return parquet_history.take(table_sorted_indices)


def _make_history_result(
    result: typing.Optional[typing.Union[pa.Array, list]],
    history_version: int,
    object_type: types.Type,
) -> typing.Union[ArrowWeaveList, list]:
    if history_version == 1:
        if isinstance(result, (list, ArrowWeaveList)):
            return result
        raise ValueError(
            f"Invalid history result for history version {history_version}"
        )
    elif history_version == 2:
        if isinstance(result, list):
            mapper = map_to_arrow(object_type, None, [])
            result = pa.array(result, type=mapper.result_type())
        return ArrowWeaveList(result, object_type)
    else:
        raise ValueError(f"Invalid history version {history_version}")


def history_body(
    run: wdt.Run,
    history_version: int,
    get_history_fn: typing.Callable[[wdt.Run, typing.Optional[list[str]]], typing.Any],
    columns: typing.Optional[list[str]] = None,
):
    # first check and see if we have actually fetched any history rows. if we have not,
    # we are in the case where we have blindly requested the entire history object.
    # we refuse to fetch that, so instead we will just inspect the historyKeys and return
    # a dummy history object that can bte used as a proxy for downstream ops (e.g., count).

    if columns is None:
        step_type = types.TypedDict({"_step": types.Int()})
        last_step = run.gql["historyKeys"]["lastStep"]
        history_keys = run.gql["historyKeys"]["keys"]
        for key, key_details in history_keys.items():
            if key == "_step":
                type_counts: list[history_util.TypeCount] = key_details["typeCounts"]
                count = type_counts[0]["count"]
                break
        else:
            return _make_history_result([], history_version, step_type)

        # generate fake steps
        steps = [{"_step": i} for i in range(count)]
        steps[-1]["_step"] = last_step
        assert len(steps) == count
        return _make_history_result(steps, history_version, step_type)

    return get_history_fn(run, columns)
