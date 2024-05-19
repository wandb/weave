from ..api import op
from .. import weave_types as types
from . import wb_domain_types as wdt
from ..gql_op_plugin import wb_gql_op_plugin
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
)

import urllib


# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
gql_prop_op(
    "artifactMembership-versionIndex",
    wdt.ArtifactCollectionMembershipType,
    "versionIndex",
    types.Int(),
)


gql_prop_op(
    "artifactMembership-createdAt",
    wdt.ArtifactCollectionMembershipType,
    "createdAt",
    types.Timestamp(),
)

gql_prop_op(
    "artifactMembership-commitHash",
    wdt.ArtifactCollectionMembershipType,
    "commitHash",
    types.String(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "artifactMembership-collection",
    wdt.ArtifactCollectionMembershipType,
    "artifactCollection",
    wdt.ArtifactCollectionType,
)

gql_direct_edge_op(
    "artifactMembership-artifactVersion",
    wdt.ArtifactCollectionMembershipType,
    "artifact",
    wdt.ArtifactVersionType,
)

gql_direct_edge_op(
    "artifactMembership-aliases",
    wdt.ArtifactCollectionMembershipType,
    "aliases",
    wdt.ArtifactAliasType,
    is_many=True,
)

# Section 5/6: Connection Ops
# None

# Section 6/6: Non Standard Business Logic Ops
# None


@op(
    name="artifactMembership-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
            versionIndex
            artifactCollection {
                id 
                name 
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
            }
        """,
    ),
)
def artifact_membership_link(
    artifactMembership: wdt.ArtifactCollectionMembership,
) -> wdt.Link:
    return wdt.Link(
        name=f"{artifactMembership['artifactCollection']['name']}:v{artifactMembership['versionIndex']}",
        url=f"/{artifactMembership['artifactCollection']['defaultArtifactType']['project']['entity']['name']}/"
        f"{artifactMembership['artifactCollection']['defaultArtifactType']['project']['name']}/"
        f"artifacts/{urllib.parse.quote(artifactMembership['artifactCollection']['defaultArtifactType']['name'])}/"
        f"{urllib.parse.quote(artifactMembership['artifactCollection']['name'])}"
        f"/v{artifactMembership['versionIndex']}",
    )
