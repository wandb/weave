from ..gql_op_plugin import wb_gql_op_plugin
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
entity = gql_root_op(
    "root-entity",
    "entity",
    wdt.EntityType,
    {
        "entityName": types.String(),
    },
    lambda inputs: f'name: {inputs["entityName"]}',
)


# Section 3/6: Attribute Getters
@op(name="entity-name")
def entity_name(entity: wdt.Entity) -> str:
    return entity["name"]


gql_prop_op("entity-internalId", wdt.EntityType, "id", types.String(), True)

gql_prop_op(
    "entity-internalId",
    wdt.EntityType,
    "id",
    types.String(),
)

gql_prop_op(
    "entity-isTeam",
    wdt.EntityType,
    "isTeam",
    types.Boolean(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "entity-org",
    wdt.EntityType,
    "organization",
    wdt.OrgType,
)

# Section 5/6: Connection Ops
gql_connection_op(
    "entity-portfolios",
    wdt.EntityType,
    "artifactCollections",
    wdt.ArtifactCollectionType,
    {},
    lambda inputs: "collectionTypes: [PORTFOLIO]",
)

gql_connection_op(
    "entity-projects",
    wdt.EntityType,
    "projects",
    wdt.ProjectType,
    {},
    # lambda inputs: f"first: 100",
)

gql_connection_op(
    "entity-reports",
    wdt.EntityType,
    "views",
    wdt.ReportType,
    {},
    # lambda inputs: f"first: 100",
)

# Section 6/6: Non Standard Business Logic Ops
@op(name="entity-link")
def entity_link(entity: wdt.Entity) -> wdt.Link:
    return wdt.Link(entity["name"], f"/{entity['name']}")
