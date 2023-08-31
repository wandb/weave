import json
from ...gql_op_plugin import wb_gql_op_plugin
from ...api import op
from ... import weave_types as types
from .. import wb_domain_types as wdt
from .. import wb_util
from ... import engine_trace

import pyarrow as pa

from . import history_op_common
from ... import gql_json_cache


tracer = engine_trace.tracer()


@op(
    name="run-refine_history_type",
    render_info={"type": "function"},
    hidden=True,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
)
def refine_history_type(run: wdt.Run) -> types.Type:
    return types.List(history_op_common.refine_history_type(run))


@op(
    name="run-history",
    refine_output_type=refine_history_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=types.List(types.TypedDict({})),
)
def history(run: wdt.Run):
    # We return mock data here since we will be replaced with the `_with_columns`
    # version in a compile pass if specific columns are needed
    return history_op_common.mock_history_rows(run, False)


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    return types.List(
        history_op_common.refine_history_type(
            run, columns=history_op_common.get_full_columns_prefixed(run, history_cols)
        )
    )


@op(
    name="run-history_with_columns",
    refine_output_type=refine_history_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=types.List(types.TypedDict({})),
    hidden=True,
)
def history_with_columns(run: wdt.Run, history_cols: list[str]):
    return _get_history(
        run, history_op_common.get_full_columns_prefixed(run, history_cols)
    )


def _get_history(run: wdt.Run, columns=None):
    with tracer.trace("get_history") as span:
        span.set_tag("history_version", 1)
    # we have fetched some specific rows.
    # download the files from the urls

    with tracer.trace("read_history_parquet"):
        parquet_history = history_op_common.read_history_parquet(
            run, columns=columns
        ) or pa.table([])

    # turn the liveset into an arrow table. the liveset is a list of dictionaries
    live_data = gql_json_cache.use_json(run["sampledParquetHistory"]["liveData"])

    with tracer.trace("liveSet.impute"):
        live_data = [
            {**row, **{colname: None for colname in columns if colname not in row}}
            for row in live_data
        ]

    # get binary fields from history schema - these are serialized json
    binary_fields = [
        field.name for field in parquet_history.schema if pa.types.is_binary(field.type)
    ]

    with tracer.trace("pq.to_pylist"):
        parquet_history = parquet_history.to_pylist()

    # deserialize json
    with tracer.trace("json.loads"):
        # These fields are not cached, beacuse they are read from parquet and not from GQL.
        # So we actually use json.loads here.
        for field in binary_fields:
            for row in parquet_history:
                if row[field] is not None:
                    row[field] = json.loads(row[field])

    # parquet stores step as a float, but we want it as an int
    for row in parquet_history:
        row["_step"] = int(row["_step"])

    history = parquet_history + live_data

    with tracer.trace("process_run_dict_obj"):
        return [
            wb_util.process_run_dict_obj(
                row,
                wb_util.RunPath(
                    run["project"]["entity"]["name"],
                    run["project"]["name"],
                    run["name"],
                ),
            )
            for row in history
        ]
