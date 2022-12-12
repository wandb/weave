import json
from ..compile_domain import wb_gql_op_plugin
from ..api import op
from .. import weave_types as types
from . import wb_domain_types as wdt
from ..language_features.tagging.make_tag_getter_op import make_tag_getter_op
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    gql_root_op,
)

import typing
from . import wb_util

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

run_name = gql_prop_op(
    "run-name",
    wdt.RunType,
    "displayName",
    types.String(),
)

gql_prop_op(
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
    wdt.DateType,
)


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "config"),
)
def refine_config_type(run: wdt.Run) -> types.Type:
    return wb_util.process_run_dict_type(json.loads(run.gql["config"] or "{}"))


@op(
    name="run-config",
    refine_output_type=refine_config_type,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "config"),
)
def config(run: wdt.Run) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(json.loads(run.gql["config"] or "{}"))


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(lambda inputs, inner: "summaryMetrics"),
)
def refine_summary_type(run: wdt.Run) -> types.Type:
    return wb_util.process_run_dict_type(json.loads(run.gql["summaryMetrics"] or "{}"))


@op(
    name="run-summary",
    refine_output_type=refine_summary_type,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "summaryMetrics"),
)
def summary(run: wdt.Run) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(json.loads(run.gql["summaryMetrics"] or "{}"))


# Section 4/6: Direct Relationship Ops
# None

# Section 5/6: Connection Ops
gql_connection_op(
    "run-usedArtifactVersions",
    wdt.RunType,
    "inputArtifacts",
    wdt.ArtifactVersionType,
    {},
    lambda inputs: f"first: 50",
)


# Section 6/6: Non Standard Business Logic Ops
@op(name="run-link", plugins=wb_gql_op_plugin(lambda inputs, inner: "displayName"))
def link(run: wdt.Run) -> wdt.Link:
    return wdt.Link(
        run.gql["displayName"],
        f'/{run.gql["project"]["entity"]["name"]}/{run.gql["project"]["name"]}/runs/{run.gql["name"]}',
    )
