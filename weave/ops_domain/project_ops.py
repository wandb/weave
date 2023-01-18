import json
from ..compile_domain import wb_gql_op_plugin
from ..api import op
from . import wb_domain_types as wdt
from ..language_features.tagging.make_tag_getter_op import make_tag_getter_op
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    gql_root_op,
)
from .. import weave_types as types

# Section 1/6: Tag Getters
make_tag_getter_op("project", wdt.ProjectType, op_name="tag-project")

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

# Section 3/6: Attribute Getters
gql_prop_op("project-name", wdt.ProjectType, "name", types.String())
gql_prop_op(
    "project-createdAt",
    wdt.ProjectType,
    "createdAt",
    types.Datetime(),
)

# Section 4/6: Direct Relationship Ops
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
    lambda inputs: f"first: 50",
)

gql_connection_op(
    "project-runs",
    wdt.ProjectType,
    "runs",
    wdt.RunType,
    {},
    lambda inputs: f"first: 50",
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
    lambda inputs: f'first: 50, filters: {inputs["filter"]}, order: {inputs["order"]}',
)


# Section 6/6: Non Standard Business Logic Ops
# Note: with project-link, the gql variables are already part fo the required fragment
# so there is nothing more to do here.
@op(name="project-link")
def link(project: wdt.Project) -> wdt.Link:
    return wdt.Link(
        project.gql["name"], f"{project.gql['entity']['name']}/{project.gql['name']}"
    )


@op(
    name="project-artifacts",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
            artifactTypes(first: 50) {{
                edges {{
                    node {{
                        id
                        artifactCollections(first: 50) {{
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
    ),
)
def artifacts(
    project: wdt.Project,
) -> list[wdt.ArtifactCollection]:
    return [
        wdt.ArtifactCollection.from_gql(edge["node"])
        for typeEdge in project.gql["artifactTypes"]["edges"]
        for edge in typeEdge["node"]["artifactCollections"]["edges"]
    ]
