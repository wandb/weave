import typing
import urllib

from ..gql_op_plugin import wb_gql_op_plugin
from ..api import op
from .. import weave_types as types
from . import wb_domain_types as wdt
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    make_root_op_gql_op_output_type,
)

from .. import errors

# Section 1/6: Tag Getters
# None


# Section 2/6: Root Ops
@op(
    name="root-allArtifactsGQLResolver",
    input_type={"gql_result": types.TypedDict({})},
    output_type=types.List(wdt.ArtifactCollectionType),
    hidden=True,
)
def root_all_artifacts_gql_resolver(gql_result):
    return [
        wdt.ArtifactCollection.from_keys(artifact_collection["node"])
        for artifact_collection in gql_result["instance"]["artifacts_500"]["edges"]
    ]


@op(
    name="root-allArtifacts",
    input_type={},
    output_type=types.List(wdt.ArtifactCollectionType),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
    instance {{
        artifacts_500: artifactSequences(limit: 500) {{
            edges {{
                node {{
                    {wdt.ArtifactCollection.REQUIRED_FRAGMENT}
                    {inner}
                }}
            }}
        }}
    }}
    """,
        is_root=True,
        root_resolver=root_all_artifacts_gql_resolver,
        gql_op_output_type=make_root_op_gql_op_output_type(
            "artifacts_500", lambda inputs: "", wdt.ArtifactCollectionType
        ),
    ),
)
def root_all_artifacts():
    raise errors.WeaveGQLCompileError(
        "root-allArtifacts should not be executed directly. If you see this error, it is a bug in the Weave compiler."
    )


# Section 3/6: Attribute Getters
gql_prop_op(
    "artifact-id",
    wdt.ArtifactCollectionType,
    "id",
    types.String(),
)
artifact_name = gql_prop_op(
    "artifact-name",
    wdt.ArtifactCollectionType,
    "name",
    types.String(),
)
gql_prop_op(
    "artifact-description",
    wdt.ArtifactCollectionType,
    "description",
    types.String(),
)
gql_prop_op(
    "artifact-createdAt",
    wdt.ArtifactCollectionType,
    "createdAt",
    types.Timestamp(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "artifact-type",
    wdt.ArtifactCollectionType,
    "defaultArtifactType",
    wdt.ArtifactTypeType,
)
gql_direct_edge_op(
    "artifact-project",
    wdt.ArtifactCollectionType,
    "project",
    wdt.ProjectType,
)

gql_direct_edge_op(
    "artifact-membershipForAlias",
    wdt.ArtifactCollectionType,
    "artifactMembership",
    wdt.ArtifactCollectionMembershipType,
    {
        "aliasName": types.String(),
    },
    lambda inputs: f'aliasName: {inputs["aliasName"]}',
)

# Section 5/6: Connection Ops
gql_connection_op(
    "artifact-versions",
    wdt.ArtifactCollectionType,
    "artifacts",
    wdt.ArtifactVersionType,
    {},
    lambda inputs: "first: 100",
)
gql_connection_op(
    "artifact-memberships",
    wdt.ArtifactCollectionType,
    "artifactMemberships",
    wdt.ArtifactCollectionMembershipType,
    {},
)
gql_connection_op(
    "artifact-aliases",
    wdt.ArtifactCollectionType,
    "aliases",
    wdt.ArtifactAliasType,
    {},
)


# Section 6/6: Non Standard Business Logic Ops
@op(
    name="artifact-isPortfolio",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: "__typename",
    ),
)
def is_portfolio(artifact: wdt.ArtifactCollection) -> bool:
    return artifact["__typename"] == "ArtifactPortfolio"


@op(
    name="artifact-lastMembership",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
            artifactMemberships_first_1: artifactMemberships(first: 1) {{
                edges {{
                    node {{
                        {wdt.ArtifactCollectionMembership.REQUIRED_FRAGMENT}
                        {inner}
                    }}
                }}
            }}
        """,
        gql_op_output_type=lambda inputs, input_type: types.optional(
            wdt.ArtifactCollectionMembershipType.with_keys(
                typing.cast(typing.Any, input_type)
                .keys["artifactMemberships_first_1"]["edges"]
                .object_type["node"]
                .property_types
            )
        ),
    ),
)
def last_membership(
    artifact: wdt.ArtifactCollection,
) -> typing.Optional[wdt.ArtifactCollectionMembership]:
    edges = artifact["artifactMemberships_first_1"]["edges"]
    if len(edges) == 0:
        return None
    return wdt.ArtifactCollectionMembership.from_keys(edges[0]["node"])


@op(
    name="artifact-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
            defaultArtifactType {
                id
                name
                project {
                    id
                    name
                    entity {
                        id
                        name
                    }
                }
            }
        """,
    ),
)
def link(
    artifact: wdt.ArtifactCollection,
) -> wdt.Link:
    artifact_type = artifact["defaultArtifactType"]
    project = artifact_type["project"]
    entity = project["entity"]
    entity_name = entity["name"]
    project_name = project["name"]
    artifact_type_name = artifact_type["name"]
    artifact_name = artifact["name"]
    return wdt.Link(
        artifact["name"],
        f"/{entity_name}/{project_name}/artifacts/{urllib.parse.quote(artifact_type_name)}/{urllib.parse.quote(artifact_name)}",
    )


@op(
    name="artifact-rawTags",
    output_type=types.List(
        types.TypedDict(
            {
                "id": types.String(),
                "name": types.String(),
                "tagCategoryName": types.String(),
                "attributes": types.String(),
            }
        )
    ),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
        tags {
            edges {
                node {
                    id
                    name
                    tagCategoryName
                    attributes
                }
            }
        }
        """
    ),
)
def raw_tags(artifact: wdt.ArtifactCollection):
    return [n["node"] for n in artifact["tags"]["edges"]]
