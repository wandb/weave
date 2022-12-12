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
# artifact_membership_version_index is written in the plain style
# because the attribute is part of the required fragment
@op(name="artifactMembership-versionIndex")
def artifact_membership_version_index(
    artifactMembership: wdt.ArtifactCollectionMembership,
) -> int:
    return artifactMembership.gql["versionIndex"]


gql_prop_op(
    "artifactMembership-createdAt",
    wdt.ArtifactCollectionMembershipType,
    "createdAt",
    wdt.DateType,
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
