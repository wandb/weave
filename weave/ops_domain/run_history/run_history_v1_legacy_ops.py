import json
import typing
from ...compile_domain import wb_gql_op_plugin
from ...api import op
from ... import weave_types as types
from .. import wb_domain_types as wdt
from ..wandb_domain_gql import (
    _make_alias,
)
from .. import wb_util
from ... import engine_trace


import pyarrow as pa

from . import history_op_common


tracer = engine_trace.tracer()


@op(
    name="run-refine_history_type",
    render_info={"type": "function"},
    hidden=True,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
)
def refine_history_type(run: wdt.Run) -> types.Type:
    return history_op_common.refine_history_type(run, 1)


@op(
    name="run-history",
    refine_output_type=refine_history_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=types.List(types.TypedDict({})),
)
def history(run: wdt.Run):
    return history_op_common.history_body(run, 1, _get_history)


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "historyKeys"),
    hidden=True,
)
def refine_history_with_columns_type(
    run: wdt.Run, history_cols: list[str]
) -> types.Type:
    return history_op_common.refine_history_type(
        run, 1, columns=history_op_common.get_full_columns(history_cols)
    )


@op(
    name="run-history_with_columns",
    refine_output_type=refine_history_with_columns_type,
    plugins=wb_gql_op_plugin(history_op_common.make_run_history_gql_field),
    output_type=types.List(types.TypedDict({})),
    hidden=True,
)
def history_with_columns(run: wdt.Run, history_cols: list[str]):
    return history_op_common.history_body(
        run, 1, _get_history, columns=history_op_common.get_full_columns(history_cols)
    )


def _get_history(run: wdt.Run, columns=None):
    with tracer.trace("get_history") as span:
        span.set_tag("history_version", 1)
    # we have fetched some specific rows.
    # download the files from the urls

    with tracer.trace("read_history_parquet"):
        parquet_history = history_op_common.read_history_parquet(
            run, 1, columns=columns
        ) or pa.table([])

    # turn the liveset into an arrow table. the liveset is a list of dictionaries
    live_data = run.gql["sampledParquetHistory"]["liveData"]

    with tracer.trace("liveSet.impute"):
        for row in live_data:
            for colname in columns:
                if colname not in row:
                    row[colname] = None

    # get binary fields from history schema - these are serialized json
    binary_fields = [
        field.name for field in parquet_history.schema if pa.types.is_binary(field.type)
    ]

    with tracer.trace("pq.to_pylist"):
        parquet_history = parquet_history.to_pylist()

    # deserialize json
    with tracer.trace("json.loads"):
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
                    run.gql["project"]["entity"]["name"],
                    run.gql["project"]["name"],
                    run.gql["name"],
                ),
            )
            for row in history
        ]


def _history_as_of_plugin(inputs, inner):
    min_step = (
        inputs.raw["asOfStep"]
        if "asOfStep" in inputs.raw and inputs.raw["asOfStep"] != None
        else 0
    )
    max_step = min_step + 1
    alias = _make_alias(str(inputs.raw["asOfStep"]), prefix="history")
    return f"{alias}: history(minStep: {min_step}, maxStep: {max_step})"


def _get_history_as_of_step(run: wdt.Run, asOfStep: int):
    alias = _make_alias(str(asOfStep), prefix="history")

    data = run.gql[alias]
    if isinstance(data, list):
        if len(data) > 0:
            data = data[0]
        else:
            data = None
    if data is None:
        return {}
    return json.loads(data)


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(_history_as_of_plugin),
    hidden=True,
)
def _refine_history_as_of_type(run: wdt.Run, asOfStep: int) -> types.Type:
    return wb_util.process_run_dict_type(_get_history_as_of_step(run, asOfStep))


@op(
    name="run-historyAsOf",
    refine_output_type=_refine_history_as_of_type,
    plugins=wb_gql_op_plugin(_history_as_of_plugin),
)
def history_as_of(run: wdt.Run, asOfStep: int) -> dict[str, typing.Any]:
    return _get_history_as_of_step(run, asOfStep)
