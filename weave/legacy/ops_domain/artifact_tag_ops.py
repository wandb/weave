from weave import weave_types as types
from weave.api import op

from weave.legacy.ops_domain import wb_domain_types as wdt
from weave.legacy.ops_domain.wandb_domain_gql import gql_prop_op


# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
gql_prop_op("artifactTag-name", wdt.ArtifactTagType, "name", types.String())

# Section 4/6: Direct Relationship Ops
# None

# Section 5/6: Connection Ops
# None

# Section 6/6: Non Standard Business Logic Ops
# None
