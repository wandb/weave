import json
import logging
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
    _make_alias,
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
    types.Datetime(),
)
gql_prop_op(
    "_run-historykeyinfo",
    wdt.RunType,
    "historyKeys",
    types.Dict(types.String(), types.Any()),
)

gql_prop_op(
    "run-runtime",
    wdt.RunType,
    "computeSeconds",
    types.Number(),
)

gql_prop_op(
    "run-heartbeatAt",
    wdt.RunType,
    "heartbeatAt",
    types.Datetime(),
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
    return wb_util.process_run_dict_obj(
        json.loads(run.gql["config"] or "{}"),
        wb_util.RunPath(
            run.gql["project"]["entity"]["name"],
            run.gql["project"]["name"],
            run.gql["name"],
        ),
    )


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
    return wb_util.process_run_dict_obj(
        json.loads(run.gql["summaryMetrics"] or "{}"),
        wb_util.RunPath(
            run.gql["project"]["entity"]["name"],
            run.gql["project"]["name"],
            run.gql["name"],
        ),
    )


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: "historyKeys, first_10_history_rows: history(minStep: 0, maxStep: 10)"
    ),
)
def _refine_history_type(run: wdt.Run) -> types.Type:
    # The Weave0 implementation loads the entire history & the historyKeys. This
    # is very inefficient and actually incomplete. Here, for performance
    # reasons, we will simply scan the first 10 rows and use that to determine
    # the type. This means that some columns will not be perfectly typed. Once
    # we have fully implemented a mapping from historyKeys to Weave types, we
    # can remove the history scan. Critically, Table types could be artifact
    # tables or run tables. In Weave0 we need to figure this out eagerly.
    # However, i think we can defer this and that will be the last thing to
    # remove needing to read any history.
    prop_types: dict[str, types.Type] = {}
    historyKeys = run.gql["historyKeys"]["keys"]
    example_history_rows = run.gql["first_10_history_rows"]
    keys_needing_type = set()

    for key, key_details in historyKeys.items():
        key_types = [tc["type"] for tc in key_details["typeCounts"]]
        if len(key_types) == 1:
            if key_types[0] == "number":
                prop_types[key] = types.Number()
                continue
            elif key_types[0] == "string":
                prop_types[key] = types.String()
                continue
        # TODO: We need to finish the historyKeys -> Weave type mapping
        logging.warning(
            f"Unable to determine history key type for key {key} with types {key_types}"
        )
        keys_needing_type.add(key)

    if len(keys_needing_type) > 0:
        example_row_types = [
            wb_util.process_run_dict_type(json.loads(row or "{}")).property_types
            for row in example_history_rows
        ]
        for key in keys_needing_type:
            cell_types = []
            for row_type in example_row_types:
                if key in row_type:
                    cell_types.append(row_type[key])
                else:
                    cell_types.append(types.NoneType())
            prop_types[key] = types.union(*cell_types)

    return types.List(types.TypedDict(prop_types))


@op(
    name="run-history",
    refine_output_type=_refine_history_type,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "history"),
)
def history(run: wdt.Run) -> list[dict[str, typing.Any]]:
    return [
        wb_util.process_run_dict_obj(
            json.loads(row),
            wb_util.RunPath(
                run.gql["project"]["entity"]["name"],
                run.gql["project"]["name"],
                run.gql["name"],
            ),
        )
        for row in run.gql["history"]
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


@op(
    render_info={"type": "function"},
    plugins=wb_gql_op_plugin(_history_as_of_plugin),
)
def _refine_history_as_of_type(run: wdt.Run, asOfStep: int) -> types.Type:
    alias = _make_alias(str(asOfStep), prefix="history")
    return wb_util.process_run_dict_type(json.loads(run.gql[alias] or "{}"))


@op(
    name="run-historyAsOf",
    refine_output_type=_refine_history_as_of_type,
    plugins=wb_gql_op_plugin(_history_as_of_plugin),
)
def history_as_of(run: wdt.Run, asOfStep: int) -> dict[str, typing.Any]:
    alias = _make_alias(str(asOfStep), prefix="history")
    return json.loads(run.gql[alias] or "{}")


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
    lambda inputs: f"first: 50",
)

gql_connection_op(
    "run-loggedArtifactVersions",
    wdt.RunType,
    "outputArtifacts",
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
    return wdt.ArtifactVersion(run.gql["project"][alias])
