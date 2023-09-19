# W&B API Weave Ops: Runs
#
# Run projection pushdown strategy
# --------------------------------
#
# Its important for performance
# that we only select the run user data (config/summary/history) columns that
# we need. We can use the stitched graph to do that for the relevant ops, any
# pick ops connected to config/summary are used to determine the keys argument
# to the graphql field.
#
# But we also need to consider refinement. There are two different ways
# refinment will happen: explicit where there is a request for a refinement
# op like refine_summary_type in the graph, and implicit, which is all other cases.
# In the explicit case we must fetch all columns so we can produce the full
# type.
#
# The implicit case always happens, because compile refines all ops in the
# graph to fix incoming Weave0 graphs for compatibility with Weave1. But this
# refinement only needs to provide the subset of the type that will be used
# for dispatch. Ie we can compute the type of only the summary fields needed
# by the query.
#
# So the correct strategy is: if a refinement descendent is explicitly requested,
# select all fields. Otherwise, select the fields described by pick descendents.
#
# We do not yet perform projection pushdown for history. Currently to fetch
# specific history columns from the W&B API, you need to use the sampledHistory
# graphql field. But it's incorrect to make a request for one "historySpec"
# containing all the required keys, because the W&B backend will return
# only rows that have all keys present. We can instead request one spec
# for each history key, always also including the _step key, and then zip
# the results back together ourselves. If we do so we'll have to do it unsampled.
# It may be better to just move to the Runs2 strategy where Weave is directly
# responsible for scanning the data instead of using the sampledHistory field.

import json
import typing


from .. import compile_table
from ..input_provider import InputAndStitchProvider
from ..gql_op_plugin import wb_gql_op_plugin
from ..api import op
from .. import weave_types as types
from . import wb_domain_types as wdt
from ..language_features.tagging.make_tag_getter_op import make_tag_getter_op
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    _make_alias,
)


from . import wb_util
from .. import engine_trace
from .run_history import history_op_common


# Important to re-export ops
from .run_history import run_history_v1_legacy_ops
from .run_history import run_history_v2_parquet_media
from .run_history import run_history_v3_parquet_stream_optimized

tracer = engine_trace.tracer()

# number of rows of example data to look at to determine history type
ROW_LIMIT_FOR_TYPE_INTERROGATION = 10

# number of history key metrics to fetch from run history
LIMIT_RUN_HISTORY_KEYS = 100

# Section 1/6: Tag Getters
run_tag_getter_op = make_tag_getter_op("run", wdt.RunType, op_name="tag-run")

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
gql_prop_op(
    "run-jobType",
    wdt.RunType,
    "jobType",
    types.String(),
)

gql_prop_op(
    "run-jobtype",
    wdt.RunType,
    "jobType",
    types.String(),
)

run_name = gql_prop_op(
    "run-name",
    wdt.RunType,
    "displayName",
    types.String(),
)

run_id = gql_prop_op(
    "run-internalId",
    wdt.RunType,
    "id",
    types.String(),
)

gql_prop_op(
    "run-id",
    wdt.RunType,
    "name",
    types.String(),
)

gql_prop_op(
    "run-createdAt",
    wdt.RunType,
    "createdAt",
    types.Timestamp(),
)
gql_prop_op(
    "run-updatedAt",
    wdt.RunType,
    "updatedAt",
    types.Timestamp(),
)
gql_prop_op(
    "_run-historykeyinfo",
    wdt.RunType,
    "historyKeys",
    types.Dict(types.String(), types.Any()),
)

runtime = gql_prop_op(
    "run-runtime",
    wdt.RunType,
    "computeSeconds",
    types.Number(),
)

gql_prop_op(
    "run-heartbeatAt",
    wdt.RunType,
    "heartbeatAt",
    types.Timestamp(),
)

gql_prop_op(
    "run-historyLineCount",
    wdt.RunType,
    "historyLineCount",
    types.Number(),
    hidden=True,
)


def config_to_values(config: dict) -> dict:
    """
    Unfortunately config values from wandb have their data located at the .value
    property inside of the config object.
    """
    return {
        key: value["value"] if isinstance(value, dict) and "value" in value else value
        for key, value in config.items()
    }


@op(
    render_info={"type": "function"},
    hidden=True,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "config"),
)
def refine_config_type(run: wdt.Run) -> types.Type:
    config_field_s = None
    try:
        # If config was explicitly requested, this will be the case.
        config_field_s = run["config"]
    except KeyError:
        # Otherwise we'll be refining implicitly in compile, but we only need
        # to provide the summary requested by the rest of the graph.
        config_field_s = run["configSubset"]
    if not config_field_s:
        config_field_s = "{}"

    return wb_util.process_run_dict_type(config_to_values(json.loads(config_field_s)))


def _make_run_config_gql_field(inputs: InputAndStitchProvider, inner: str):
    # Must be kept in sync with compile_domain:_field_selections_hardcode_merge
    stitch_obj = inputs.stitched_obj
    key_tree = compile_table.get_projection(stitch_obj)
    # we only pushdown the top level keys for now.

    top_level_keys = history_op_common.get_top_level_keys(key_tree)
    if not top_level_keys:
        # If no keys, then we must select the whole object
        return "configSubset: config"
    return f"configSubset: config(keys: {json.dumps(top_level_keys)})"


run_path_fragment = """
    project {
        id
        name
        entity {
            id
            name
        }
    }
    """


def _run_config_plugin(inputs: InputAndStitchProvider, inner: str):
    config_field = _make_run_config_gql_field(inputs, inner)
    return config_field + " " + run_path_fragment


@op(
    name="run-config",
    refine_output_type=refine_config_type,
    plugins=wb_gql_op_plugin(_run_config_plugin),
)
def config(run: wdt.Run) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(
        config_to_values(json.loads(run["configSubset"] or "{}")),
        wb_util.RunPath(
            run["project"]["entity"]["name"],
            run["project"]["name"],
            run["name"],
        ),
    )


@op(
    render_info={"type": "function"},
    hidden=True,
    # When refine_summary_type is explicitly requested in the graph, we ask for
    # the entire summaryMetrics field.
    plugins=wb_gql_op_plugin(lambda inputs, inner: "summaryMetrics"),
)
def refine_summary_type(run: wdt.Run) -> types.Type:
    summary_field_s = None
    try:
        # If summary was explicitly requested, this will be the case.
        summary_field_s = run["summaryMetrics"]
    except KeyError:
        # Otherwise we'll be refining implicitly in compile, but we only need
        # to provide the summary requested by the rest of the graph.
        summary_field_s = run["summaryMetricsSubset"]
    if not summary_field_s:
        summary_field_s = "{}"

    return wb_util.process_run_dict_type(json.loads(summary_field_s))


def _make_run_summary_gql_field(inputs: InputAndStitchProvider, inner: str):
    # Must be kept in sync with compile_domain:_field_selections_hardcode_merge

    stitch_obj = inputs.stitched_obj
    key_tree = compile_table.get_projection(stitch_obj)

    # we only pushdown the top level keys for now.
    top_level_keys = history_op_common.get_top_level_keys(key_tree)
    if not top_level_keys:
        # If no keys, then we must select the whole object
        return "summaryMetricsSubset: summaryMetrics"
    return f"summaryMetricsSubset: summaryMetrics(keys: {json.dumps(top_level_keys)})"


def _run_summary_plugin(inputs: InputAndStitchProvider, inner: str):
    summary_field = _make_run_summary_gql_field(inputs, inner)
    return summary_field + " " + run_path_fragment


@op(
    name="run-summary",
    refine_output_type=refine_summary_type,
    plugins=wb_gql_op_plugin(_run_summary_plugin),
)
def summary(run: wdt.Run) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(
        json.loads(run["summaryMetricsSubset"] or "{}"),
        wb_util.RunPath(
            run["project"]["entity"]["name"],
            run["project"]["name"],
            run["name"],
        ),
    )


def _history_as_of_plugin(inputs, inner):
    min_step = (
        inputs.raw["asOfStep"]
        if "asOfStep" in inputs.raw and inputs.raw["asOfStep"] != None
        else 0
    )
    max_step = min_step + 1
    alias = _make_alias(str(inputs.raw["asOfStep"]), prefix="history")
    return f"{alias}: history(minStep: {min_step}, maxStep: {max_step}, maxKeyLimit: {LIMIT_RUN_HISTORY_KEYS})"


def _get_history_as_of_step(
    run: wdt.Run,
    asOfStep: int,
):
    alias = _make_alias(str(asOfStep), prefix="history")

    data = run[alias]
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
def _refine_history_as_of_type(
    run: wdt.Run,
    asOfStep: int,
) -> types.Type:
    return wb_util.process_run_dict_type(_get_history_as_of_step(run, asOfStep))


@op(
    name="run-historyAsOf",
    refine_output_type=_refine_history_as_of_type,
    plugins=wb_gql_op_plugin(_history_as_of_plugin),
)
def history_as_of(
    run: wdt.Run,
    asOfStep: int,
) -> dict[str, typing.Any]:
    return _get_history_as_of_step(run, asOfStep)


# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "run-user",
    wdt.RunType,
    "user",
    wdt.UserType,
)

gql_direct_edge_op(
    "run-project",
    wdt.RunType,
    "project",
    wdt.ProjectType,
)

# Section 5/6: Connection Ops
gql_connection_op(
    "run-usedArtifactVersions",
    wdt.RunType,
    "inputArtifacts",
    wdt.ArtifactVersionType,
    {},
    lambda inputs: "first: 100",
)

gql_connection_op(
    "run-loggedArtifactVersions",
    wdt.RunType,
    "outputArtifacts",
    wdt.ArtifactVersionType,
    {},
    lambda inputs: "first: 100",
)


# Section 6/6: Non Standard Business Logic Ops
@op(
    name="run-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
    displayName
    project {
        id
        name
        entity {
            id
            name
        }
    }
"""
    ),
)
def link(run: wdt.Run) -> wdt.Link:
    return wdt.Link(
        run["displayName"],
        f'/{run["project"]["entity"]["name"]}/{run["project"]["name"]}/runs/{run["name"]}',
    )


def run_logged_artifact_version_gql_plugin(inputs, inner):
    artifact_name = inputs.raw["artifactVersionName"]
    alias = _make_alias(artifact_name, prefix="artifact")
    if ":" not in artifact_name:
        artifact_name += ":latest"
    artifact_name = json.dumps(artifact_name)
    return f"""
    project {{
        {alias}: artifact(name: {artifact_name}) {{
            {wdt.ArtifactVersion.REQUIRED_FRAGMENT}
            {inner}
        }}
    }}"""


@op(
    name="run-loggedArtifactVersion",
    plugins=wb_gql_op_plugin(run_logged_artifact_version_gql_plugin),
)
def run_logged_artifact_version(
    run: wdt.Run, artifactVersionName: str
) -> wdt.ArtifactVersion:
    alias = _make_alias(artifactVersionName, prefix="artifact")
    return wdt.ArtifactVersion.from_keys(run["project"][alias])
