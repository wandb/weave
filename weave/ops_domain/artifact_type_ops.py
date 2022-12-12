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
# op_artifact_type_name is written in the plain style
# because the attribute is part of the required fragment
@op(name="artifactType-name")
def op_artifact_type_name(artifactType: wdt.ArtifactType) -> str:
    return artifactType.gql["name"]


# Section 4/6: Direct Relationship Ops
# None

# Section 5/6: Connection Ops
gql_connection_op(
    "artifactType-artifacts",
    wdt.ArtifactTypeType,
    "artifactCollections",
    wdt.ArtifactCollectionType,
    {},
    lambda inputs: f"first: 50",
)

# Section 6/6: Non Standard Business Logic Ops
# None
