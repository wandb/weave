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
)
from .. import weave_types as types

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
