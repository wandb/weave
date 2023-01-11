import typing

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

# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

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
    types.Datetime(),
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
    lambda inputs: f"first: 50",
)
gql_connection_op(
    "artifact-memberships",
    wdt.ArtifactCollectionType,
    "artifactMemberships",
    wdt.ArtifactCollectionMembershipType,
    {},
    lambda inputs: f"first: 50",
)
gql_connection_op(
    "artifact-aliases",
    wdt.ArtifactCollectionType,
    "aliases",
    wdt.ArtifactAliasType,
    {},
    lambda inputs: f"first: 50",
)

# Section 6/6: Non Standard Business Logic Ops
@op(
    name="artifact-isPortfolio",
    plugins=wb_gql_op_plugin(lambda inputs, inner: "__typename"),
)
def is_portfolio(artifact: wdt.ArtifactCollection) -> bool:
    return artifact.gql["__typename"] == "ArtifactPortfolio"


@op(
    name="artifact-lastMembership",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
            artifactMemberships(first: 1) {{
                edges {{
                    node {{
                        {wdt.ArtifactCollectionMembership.REQUIRED_FRAGMENT}
                        {inner}
                    }}
                }}
            }}
        """,
    ),
)
def last_membership(
    artifact: wdt.ArtifactCollection,
) -> typing.Optional[wdt.ArtifactCollectionMembership]:
    edges = artifact.gql["artifactMemberships"]["edges"]
    if len(edges) == 0:
        return None
    return wdt.ArtifactCollectionMembership.from_gql(edges[0]["node"])
