import typing
import json
from ..gql_op_plugin import wb_gql_op_plugin
from ..api import op
from . import wb_domain_types as wdt
from ..language_features.tagging.make_tag_getter_op import make_tag_getter_op
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    gql_root_op,
    make_root_op_gql_op_output_type,
)

from .. import weave_types as types
from .. import errors
from .. import input_provider

# Section 1/6: Tag Getters
get_project_tag = make_tag_getter_op("project", wdt.ProjectType, op_name="tag-project")

# Section 2/6: Root Ops
# The output in this case is stored so it can be exported in __init__.py (can probably remove this
# as I believe it is only used in testing)
project = gql_root_op(
    "root-project",
    "project",
    wdt.ProjectType,
    {
        "entityName": types.String(),
        "projectName": types.String(),
    },
    lambda inputs: f'name: {inputs["projectName"]}, entityName: {inputs["entityName"]}',
)


@op(
    name="root-allProjectsGQLResolver",
    input_type={"gql_result": types.TypedDict({})},
    output_type=types.List(wdt.ProjectType),
    hidden=True,
)
def root_all_projects_gql_resolver(gql_result):
    return [
        wdt.Project.from_keys(project["node"])
        for project in gql_result["instance"]["projects_500"]["edges"]
    ]


@op(
    name="root-allProjects",
    input_type={},
    output_type=types.List(wdt.ProjectType),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
    instance {{
        projects_500: projects(limit: 500) {{
            edges {{
                node {{
                    {wdt.Project.REQUIRED_FRAGMENT}
                    {inner}
                }}
            }}
        }}
    }}
    """,
        is_root=True,
        root_resolver=root_all_projects_gql_resolver,
        gql_op_output_type=make_root_op_gql_op_output_type(
            "projects_500", lambda inputs: "", wdt.ProjectType
        ),
    ),
)
def root_all_projects():
    raise errors.WeaveGQLCompileError(
        "root-allProjects should not be executed directly. If you see this error, it is a bug in the Weave compiler."
    )


# Section 3/6: Attribute Getters
name = gql_prop_op("project-name", wdt.ProjectType, "name", types.String())
gql_prop_op(
    "project-createdAt",
    wdt.ProjectType,
    "createdAt",
    types.Timestamp(),
)
gql_prop_op(
    "project-updatedAt",
    wdt.ProjectType,
    "updatedAt",
    types.Timestamp(),
)

gql_prop_op(
    "project-internalId",
    wdt.ProjectType,
    "id",
    types.String(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "project-run",
    wdt.ProjectType,
    "run",
    wdt.RunType,
    {
        "runName": types.String(),
    },
    lambda inputs: f'name: {inputs["runName"]}',
)

gql_direct_edge_op(
    "project-entity",
    wdt.ProjectType,
    "entity",
    wdt.EntityType,
)

gql_direct_edge_op(
    "project-runQueues",
    wdt.ProjectType,
    "runQueues",
    wdt.RunQueueType,
    is_many=True,
)

gql_direct_edge_op(
    "project-artifactType",
    wdt.ProjectType,
    "artifactType",
    wdt.ArtifactTypeType,
    {
        "artifactType": types.String(),
    },
    lambda inputs: f'name: {inputs["artifactType"]}',
)

gql_direct_edge_op(
    "project-artifactVersion",
    wdt.ProjectType,
    "artifact",
    wdt.ArtifactVersionType,
    {
        "artifactName": types.String(),
        "artifactVersionAlias": types.String(),
    },
    lambda inputs: f'name: {json.dumps(inputs.raw["artifactName"] + ":" + inputs.raw["artifactVersionAlias"])}',
)

gql_direct_edge_op(
    "project-artifact",
    wdt.ProjectType,
    "artifactCollection",
    wdt.ArtifactCollectionType,
    {
        "artifactName": types.String(),
    },
    lambda inputs: f'name: {inputs["artifactName"]}',
)

# Section 5/6: Connection Ops
gql_connection_op(
    "project-artifactTypes",
    wdt.ProjectType,
    "artifactTypes",
    wdt.ArtifactTypeType,
    {},
    # lambda inputs: "first: 10",
)

gql_connection_op(
    "project-runs",
    wdt.ProjectType,
    "runs",
    wdt.RunType,
    {},
    lambda inputs: "first: 100",
)


gql_connection_op(
    "project-filteredRuns",
    wdt.ProjectType,
    "runs",
    wdt.RunType,
    {
        "filter": types.String(),
        "order": types.String(),
    },
    lambda inputs: f'first: 100, filters: {inputs["filter"]}, order: {inputs["order"]}',
)


# Section 6/6: Non Standard Business Logic Ops
# Note: with project-link, the gql variables are already part fo the required fragment
# so there is nothing more to do here.
@op(
    name="project-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
            entity {
                id
                name
            }
        """
    ),
)
def link(project: wdt.Project) -> wdt.Link:
    return wdt.Link(project["name"], f"{project['entity']['name']}/{project['name']}")


def _project_artifacts_gql_op_output_type(
    inputs: input_provider.InputProvider, input_type: types.Type
) -> types.Type:
    return types.List(
        wdt.ArtifactCollectionType.with_keys(
            typing.cast(typing.Any, input_type)
            .keys["artifactTypes_100"]["edges"]
            .object_type["node"]["artifactCollections_100"]["edges"]
            .object_type["node"]
            .property_types
        )
    )


@op(
    name="project-artifacts",
    output_type=lambda input_types: types.List(wdt.ArtifactCollectionType),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
            artifactTypes_100: artifactTypes(first: 100) {{
                edges {{
                    node {{
                        id
                        artifactCollections_100: artifactCollections(first: 100) {{
                            edges {{
                                node {{
                                    {wdt.ArtifactCollection.REQUIRED_FRAGMENT}
                                    {inner}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        """,
        gql_op_output_type=_project_artifacts_gql_op_output_type,
    ),
)
def artifacts(
    project: wdt.Project,
):
    return [
        wdt.ArtifactCollection.from_keys(edge["node"])
        for typeEdge in project["artifactTypes_100"]["edges"]
        for edge in typeEdge["node"]["artifactCollections_100"]["edges"]
    ]
