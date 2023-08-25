# Very much WIP. An implementation of the read side of the next gen
# W&B runs/table engine.

import itertools
import random
import string
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.parquet as pc
import pyarrow.dataset as ds
import pyarrow.feather as pf
import pyarrow.compute as pc

import typing
import weave
from weave.ops_domain import wb_domain_types

from .. import engine_trace
from ..ops_arrow.arrow import arrow_schema_to_weave_type
from ..ops_arrow.list_ import ArrowWeaveListType


class EmptyTypedDict(typing.TypedDict):
    pass


class Run2(typing.TypedDict):
    id: str
    config: EmptyTypedDict
    summary: EmptyTypedDict


def get_runs_ds_columns(
    config_cols: list[str], summary_cols: list[str]
) -> dict[str, pc.Expression]:
    # TODO: only handles the first level of nesting right now
    cols = {
        "id": ds.field("id"),
    }
    if not config_cols:
        # TODO: can't default to key0, but pyarrow doeesn't like empty values.
        config_cols = ["key0"]
    if not summary_cols:
        # TODO: can't default to key0, but pyarrow doeesn't like empty values.
        summary_cols = ["key0"]
    if config_cols:
        cols["config"] = pc.make_struct(
            *(ds.field("config", k) for k in config_cols), field_names=config_cols
        )
    if summary_cols:
        cols["summary"] = pc.make_struct(
            *(ds.field("summary", k) for k in summary_cols), field_names=summary_cols
        )
    return cols


def read_runs(
    project_name: str, columns=None, limit=None
) -> weave.ops.ArrowWeaveList[Run2]:
    tracer = engine_trace.tracer()

    # Uncomment to use feather format instead
    # with tracer.trace("read_arch"):
    #     # This is the slow part!
    #     arch = ds.dataset(f"/tmp/runs.{project_name}.feather", format='feather').to_table(columns=columns)
    # with tracer.trace("read_live"):
    #     live = ds.dataset(f"/tmp/runs.{project_name}.live.feather", format='feather').to_table(
    #         columns=columns
    #     )
    with tracer.trace("read_arch"):
        # This is the slow part!
        arch = ds.dataset(f"/tmp/runs.{project_name}.parquet").to_table(columns=columns)
    with tracer.trace("read_live"):
        live = ds.dataset(f"/tmp/runs.{project_name}.live.parquet").to_table(
            columns=columns
        )
    import duckdb

    with tracer.trace("ddb_connect"):
        con = duckdb.connect()
    if limit is not None:
        limit = f"LIMIT {limit}"
    else:
        limit = ""
    with tracer.trace("ddb_join"):
        # 'live' and 'arch' refer to tables variables in the local scope!
        joined = con.execute(
            """
            SELECT COALESCE(ls.id, p.id) as id,
                COALESCE(ls.config, p.config) as config,
                COALESCE(ls.summary, p.summary) as summary,
            FROM 'live' as ls
            FULL OUTER JOIN 'arch' as p
            ON ls.id=p.id
            %s
            """
            % limit
        )
    with tracer.trace("ddb_arrow"):
        joined_table = joined.arrow()

    with tracer.trace("to_weave"):
        # TODO: Should this pass an artifact to `weave.ops.ArrowWeaveList`?
        res: weave.ops.ArrowWeaveList[Run2] = weave.ops.ArrowWeaveList(joined_table)
    return res


@weave.op(render_info={"type": "function"}, hidden=True)
def refine_runs2_with_columns_type(
    project: wb_domain_types.Project, config_cols: list[str], summary_cols: list[str]
) -> weave.types.Type:
    # TODO: only reading type from archived runs right now. There is a bunch of logic we need
    # to get this right
    schema = ds.dataset(f"/tmp/runs.{project['name']}.parquet").schema
    full_run_type = typing.cast(
        weave.types.TypedDict, arrow_schema_to_weave_type(schema)
    )
    full_config_type = typing.cast(
        weave.types.TypedDict, full_run_type.property_types["config"]
    )
    full_summary_type = typing.cast(
        weave.types.TypedDict, full_run_type.property_types["config"]
    )
    partial_run_type = weave.types.TypedDict(
        {
            "id": full_run_type.property_types["id"],
            "config": weave.types.TypedDict(
                {k: full_config_type.property_types[k] for k in config_cols}
            ),
            "summary": weave.types.TypedDict(
                {k: full_summary_type.property_types[k] for k in summary_cols}
            ),
        }
    )
    return ArrowWeaveListType(partial_run_type)


@weave.op(
    name="project-runs2_with_columns",
    refine_output_type=refine_runs2_with_columns_type,
)
def runs2_with_columns(
    project: wb_domain_types.Project, config_cols: list[str], summary_cols: list[str]
) -> weave.ops.ArrowWeaveList[Run2]:
    return read_runs(
        project["name"], columns=get_runs_ds_columns(config_cols, summary_cols)
    )


@weave.op(render_info={"type": "function"}, hidden=True)
def refine_runs2_type(project: wb_domain_types.Project) -> weave.types.Type:
    schema = ds.dataset(f"/tmp/runs.{project['name']}.parquet").schema
    return ArrowWeaveListType(arrow_schema_to_weave_type(schema))


@weave.op(name="project-runs2", refine_output_type=refine_runs2_type)
def runs2(project: wb_domain_types.Project) -> weave.ops.ArrowWeaveList[Run2]:
    return read_runs(project["name"])


# Defines a panel with all columns shown for the runs
@weave.op()
def render_table_runs2(runs: weave.Node[list[Run2]]) -> weave.panels.Table:
    run_type = runs.type.object_type  # type: ignore
    config_type = run_type.property_types["config"]
    summary_type = run_type.property_types["summary"]
    columns = []

    def col_key(field, key):
        return lambda run: run[field][key]

    for key in config_type.property_types:
        columns.append(col_key("config", key))
    for key in summary_type.property_types:
        columns.append(col_key("summary", key))
    return weave.panels.Table(runs, columns=columns)


# Data generation for testing
def random_string(n):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def make_runs(n_runs, n_summary, n_config, n_config_value_chars):
    config_choices = [
        "".join(c)
        for c in itertools.combinations(string.ascii_lowercase, n_config_value_chars)
    ]
    ids = [random_string(8) for i in range(n_runs)]
    config_arrays = [np.random.choice(config_choices, n_runs) for i in range(n_config)]
    config_keys = [f"key{i}" for i in range(n_config)]
    config = pa.StructArray.from_arrays(config_arrays, config_keys)
    summary_arrays = [np.random.random(n_runs) for i in range(n_summary)]
    summary_keys = [f"key{i}" for i in range(n_summary)]
    summary = pa.StructArray.from_arrays(summary_arrays, summary_keys)
    return pa.Table.from_arrays([ids, config, summary], ["id", "config", "summary"])


def make_runs2_tables(n_runs, n_summary, n_config, n_config_value_chars, live_set_size):
    runs = make_runs(n_runs, n_summary, n_config, n_config_value_chars)
    arch_runs = runs[: len(runs) - live_set_size]
    liveset_runs = runs[len(runs) - live_set_size :]
    proj_name = f"weavetest-{n_runs}-{n_summary}-{n_config}-{live_set_size}"
    pq.write_table(arch_runs, f"/tmp/runs.{proj_name}.parquet")
    pf.write_feather(arch_runs, f"/tmp/runs.{proj_name}.feather")
    pq.write_table(liveset_runs, f"/tmp/runs.{proj_name}.live.parquet")
    pf.write_feather(liveset_runs, f"/tmp/runs.{proj_name}.live.feather")
