import re
import typing
from ..gql_op_plugin import wb_gql_op_plugin
from ..api import op
from . import wb_domain_types as wdt
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
)
from .. import weave_types as types
import urllib
from .. import errors

# Section 1/6: Tag Getters
#


# Section 2/6: Root Ops
@op(
    name="root-allReportsGQLResolver",
    input_type={"gql_result": types.TypedDict({})},
    output_type=types.List(wdt.ReportType),
    hidden=True,
)
def root_all_reports_gql_resolver(gql_result):
    return [
        wdt.Report.from_keys(report["node"])
        for report in gql_result["instance"]["views_500"]["edges"]
        if report["node"]["type"] == "runs"  # yes, this is how we filter to Reports!?
    ]


@op(
    name="root-allReports",
    input_type={},
    output_type=types.List(wdt.ReportType),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
        instance {{
            views_500: views(limit: 500) {{
                edges {{
                    node {{
                        type
                        {wdt.Report.REQUIRED_FRAGMENT}
                        {inner}
                    }}
                }}
            }}
        }}""",
        is_root=True,
        root_resolver=root_all_reports_gql_resolver,
    ),
)
def root_all_reports():
    raise errors.WeaveGQLCompileError(
        "root-allReports should not be executed directly. If you see this error, it is a bug in the Weave compiler."
    )


# Section 3/6: Attribute Getters
gql_prop_op("report-internalId", wdt.ReportType, "id", types.String(), True)
gql_prop_op(
    "report-name",
    wdt.ReportType,
    "displayName",
    types.String(),
)
gql_prop_op(
    "report-internalId",
    wdt.ReportType,
    "id",
    types.String(),
)
gql_prop_op(
    "report-name",
    wdt.ReportType,
    "displayName",
    types.String(),
)
gql_prop_op(
    "report-createdAt",
    wdt.ReportType,
    "createdAt",
    types.Timestamp(),
)
gql_prop_op(
    "report-updatedAt",
    wdt.ReportType,
    "updatedAt",
    types.Timestamp(),
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
        lambda inputs, inner: """
    id
    displayName
    project {
        id
        name 
        entity {
            id
            name
        }
    }
"""
    ),
)
def link(report: wdt.Report) -> wdt.Link:
    project = report["project"]
    entity = project["entity"]

    project_name = project["name"]
    entity_name = entity["name"]
    report_id = report["id"]
    report_name = report["displayName"]

    url = f"/{entity_name}/{project_name}/reports/{make_name_and_id(report_id, report_name)}"
    return wdt.Link(report_name, url)
