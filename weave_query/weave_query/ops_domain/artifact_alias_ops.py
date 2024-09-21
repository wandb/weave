from weave_query.weave_query import weave_types as types
from weave_query.weave_query.ops_domain import wb_domain_types as wdt
from weave_query.weave_query.ops_domain.wandb_domain_gql import (
    gql_direct_edge_op,
    gql_prop_op,
)

# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
gql_prop_op("artifactAlias-alias", wdt.ArtifactAliasType, "alias", types.String())

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "artifactAlias-artifact",
    wdt.ArtifactAliasType,
    "artifactCollection",
    wdt.ArtifactCollectionType,
)

# Section 5/6: Connection Ops
# None

# Section 6/6: Non Standard Business Logic Ops
# None
