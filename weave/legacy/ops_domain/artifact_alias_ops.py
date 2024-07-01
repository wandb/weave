from weave import weave_types as types
from weave.api import op
from weave.legacy.gql_op_plugin import wb_gql_op_plugin
from weave.legacy.language_features.tagging.make_tag_getter_op import (
    make_tag_getter_op,
)
from weave.legacy.ops_domain import wb_domain_types as wdt
from weave.legacy.ops_domain.wandb_domain_gql import (
    gql_connection_op,
    gql_direct_edge_op,
    gql_prop_op,
    gql_root_op,
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
