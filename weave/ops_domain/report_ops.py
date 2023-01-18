import json
import re
import typing
from ..compile_domain import wb_gql_op_plugin
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
import urllib

# Section 1/6: Tag Getters
#

# Section 2/6: Root Ops
# root-allReports
# Since root-allProjects is not a top-level query, we need to write the gql explicitly
# instead of using gql_root_op

# Section 3/6: Attribute Getters
gql_prop_op(
    "report-createdAt",
    wdt.ReportType,
    "createdAt",
    types.Datetime(),
)
gql_prop_op(
    "report-viewcount",
    wdt.ReportType,
    "viewCount",
    types.Number(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "report-project",
    wdt.ReportType,
    "project",
    wdt.ProjectType,
)

gql_direct_edge_op(
    "report-creator",
    wdt.ReportType,
    "user",
    wdt.UserType,
)

# Section 5/6: Connection Ops
#

# Section 6/6: Non Standard Business Logic Ops

# Logic taken exactly from Weave0 / frontend
def make_name_and_id(id: str, name: typing.Optional[str]) -> str:
    id = id.replace("=", "")
    if name is None:
        return id
    name = re.sub(r"\W", "-", name)
    name = re.sub(r"-+", "-", name)
    name = urllib.parse.quote(name)

    return f"{name}--{id}"


@op(
    name="report-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
    id
    displayName
    project {{
        id
        name 
        entity {{
            id
            name
        }}
    }}
"""
    ),
)
def link(report: wdt.Report) -> wdt.Link:
    project = report.gql["project"]
    entity = project["entity"]

    project_name = project["name"]
    entity_name = entity["name"]
    report_id = report.gql["id"]
    report_name = report.gql["displayName"]

    url = f"/{entity_name}/{project_name}/reports/{make_name_and_id(report_id, report_name)}"
    return wdt.Link(report_name, url)
