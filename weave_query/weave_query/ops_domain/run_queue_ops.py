from weave_query.weave_query import weave_types as types
from weave_query.weave_query.ops_domain import wb_domain_types as wdt
from weave_query.weave_query.ops_domain.wandb_domain_gql import (
    gql_prop_op,
)

# Section 1/6: Tag Getters
#

# Section 2/6: Root Ops
#

# Section 3/6: Attribute Getters
gql_prop_op(
    "runQueue-id",
    wdt.RunQueueType,
    "id",
    types.String(),
)

# Section 5/6: Connection Ops
#

# Section 6/6: Non Standard Business Logic Ops
#
