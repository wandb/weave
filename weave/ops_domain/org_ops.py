from . import wb_domain_types as wdt
from .wandb_domain_gql import (
    gql_prop_op,
    gql_connection_op,
    gql_root_op,
)
from .. import weave_types as types

# Section 1/6: Tag Getters
#

# Section 2/6: Root Ops
org = gql_root_op(
    "root-org",
    "organization",
    wdt.OrgType,
    {
        "orgName": types.String(),
    },
    lambda inputs: f'name: {inputs["orgName"]}',
)

# Section 3/6: Attribute Getters
gql_prop_op("org-name", wdt.OrgType, "name", types.String())


# Section 4/6: Direct Relationship Ops


# Section 5/6: Connection Ops
gql_connection_op(
    "org-projects",
    wdt.OrgType,
    "projects",
    wdt.ProjectType,
    {},
    lambda inputs: "first: 100",
)

gql_connection_op(
    "org-reports",
    wdt.OrgType,
    "views",
    wdt.ReportType,
    {},
    lambda inputs: "first: 100",
)

gql_connection_op(
    "org-artifacts",
    wdt.OrgType,
    "artifactCollections",
    wdt.ArtifactCollectionType,
    {},
    lambda inputs: "first: 100",
)

# Section 6/6: Non Standard Business Logic Ops
#
