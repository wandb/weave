# history2 is depcreated, don't use it. It's only used in RunChain,
# which is just in demo form now. When we go back to working on RunChain
# we'll remove history2

import json
from ...gql_op_plugin import wb_gql_op_plugin
from ...api import op
from ... import weave_types as types
from .. import wb_domain_types as wdt
from ... import artifact_mem
from .. import wb_util
from ...ops_domain import wbmedia
from ...ops_arrow.list_ops import concat
from ...ops_arrow import ArrowWeaveList, ArrowWeaveListType, convert
from ... import engine_trace
from ... import gql_json_cache

from ...api import use

import pyarrow as pa

from . import history_op_common


tracer = engine_trace.tracer()


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history2_type(run: wdt.Run) -> types.Type:
    return ArrowWeaveListType(history_op_common.refine_history_type(run))


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history2_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    return ArrowWeaveListType(
        history_op_common.refine_history_type(
            run, columns=history_op_common.get_full_columns_prefixed(run, history_cols)
        )
    )


@op(
    name="run-history2_with_columns",
    refine_output_type=refine_history2_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history2_with_columns(run: wdt.Run, history_cols: list[str]):
    return _get_history2(
        run, history_op_common.get_full_columns_prefixed(run, history_cols)
    )


# DEPRECATED: see comment at top.
# There is a bug in history2 where we mutate gql results, which is not allowed.
# now that we've removed deepcopy from gql_json_cache.use_json. But that's ok
# because this is deprecated and only used in a demo notebook.
@op(
    name="run-history2",
    refine_output_type=refine_history2_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=ArrowWeaveListType(types.TypedDict({})),
    hidden=True,
)
def history2(run: wdt.Run):
    # We return mock data here since we will be replaced with the `_with_columns`
    # version in a compile pass if specific columns are needed
    return history_op_common.mock_history_rows(run)


def _get_history2(run: wdt.Run, columns=None):
    with tracer.trace("get_history") as span:
        span.set_tag("history_version", 2)
    """Dont read binary columns. Keep everything in arrow. Faster, but not as full featured as get_history"""
    scalar_keys = history_op_common.history_keys(run)
    columns = [c for c in columns if c in scalar_keys]
    parquet_history = history_op_common.read_history_parquet(run, columns=columns)

    _object_type = history_op_common.refine_history_type(run, columns=columns)

    _history_type = types.List(_object_type)

    run_path = wb_util.RunPath(
        run["project"]["entity"]["name"],
        run["project"]["name"],
        run["name"],
    )

    # turn the liveset into an arrow table. the liveset is a list of json objects
    # we read from the cache via use_json()
    live_data = gql_json_cache.use_json(run["sampledParquetHistory"]["liveData"])

    # This is a nono! Mutating the gql results. But that's ok because this is deprecated,
    # see module comment at top.
    for row in live_data:
        for colname in columns:
            if colname not in row:
                row[colname] = None
            else:
                row[colname] = wb_util._process_run_dict_item(row[colname], run_path)

    artifact = artifact_mem.MemArtifact()
    # turn live data into arrow
    if live_data is not None and len(live_data) > 0:
        with tracer.trace("live_data_to_arrow"):
            live_data = convert.to_arrow(live_data, _history_type, artifact=artifact)
    else:
        live_data = []

    # get binary fields from history schema - these are serialized json
    if parquet_history is not None:
        fields = [field.name for field in parquet_history.schema]
        binary_fields = {
            field.name
            for field in parquet_history.schema
            if pa.types.is_binary(field.type)
        }

        # deserialize json if any is present
        with tracer.trace("process_non_basic_fields"):
            for field in columns:
                if field in binary_fields or not (
                    types.optional(types.BasicType()).assign_type(
                        _object_type.property_types[field]  # type: ignore
                    )
                    or wbmedia.ImageArtifactFileRefType().assign_type(
                        _object_type.property_types[field]  # type: ignore
                    )
                ):
                    pq_col = parquet_history[field].to_pylist()
                    for i, item in enumerate(pq_col):
                        if item is not None:
                            pq_col[i] = wb_util._process_run_dict_item(
                                json.loads(item) if field in binary_fields else item,
                                run_path,
                            )

                    awl = convert.to_arrow(
                        pq_col,
                        types.List(_object_type.property_types[field]),
                        artifact=artifact,
                    )
                    new_col = pa.chunked_array([awl._arrow_data])
                    parquet_history = parquet_history.set_column(
                        fields.index(field), field, new_col
                    )

    if parquet_history is not None and len(parquet_history) > 0:
        with tracer.trace("parquet_history_to_arrow"):
            parquet_history = ArrowWeaveList(
                parquet_history,
                _object_type,
                artifact=artifact,
            )
    else:
        parquet_history = []

    if len(live_data) == 0 and len(parquet_history) == 0:
        return ArrowWeaveList(pa.array([]), _object_type, artifact=artifact)
    elif len(live_data) == 0:
        return parquet_history
    elif len(parquet_history) == 0:
        return live_data
    return use(concat([parquet_history, live_data]))
