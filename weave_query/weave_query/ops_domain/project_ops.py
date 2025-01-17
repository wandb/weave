import json
import typing

from weave_query import errors
from weave_query import weave_types as types
from weave_query import ops_arrow
from weave_query.wandb_trace_server_api import get_wandb_trace_api
from weave_query.api import op
from weave_query import input_provider
from weave_query.gql_op_plugin import wb_gql_op_plugin
from weave_query.language_features.tagging.make_tag_getter_op import (
    make_tag_getter_op,
)
from weave_query.ops_domain import wb_domain_types as wdt
from weave_query.ops_domain.wandb_domain_gql import (
    gql_connection_op,
    gql_direct_edge_op,
    gql_prop_op,
    gql_root_op,
    make_root_op_gql_op_output_type,
)

# Section 1/6: Tag Getters
get_project_tag = make_tag_getter_op("project", wdt.ProjectType, op_name="tag-project")

# Section 2/6: Root Ops
# The output in this case is stored so it can be exported in __init__.py (can probably remove this
# as I believe it is only used in testing)
project = gql_root_op(
    "root-project",
    "project",
    wdt.ProjectType,
    {
        "entityName": types.String(),
        "projectName": types.String(),
    },
    lambda inputs: f'name: {inputs["projectName"]}, entityName: {inputs["entityName"]}',
)


@op(
    name="root-allProjectsGQLResolver",
    input_type={"gql_result": types.TypedDict({})},
    output_type=types.List(wdt.ProjectType),
    hidden=True,
)
def root_all_projects_gql_resolver(gql_result):
    return [
        wdt.Project.from_keys(project["node"])
        for project in gql_result["instance"]["projects_500"]["edges"]
    ]


@op(
    name="root-allProjects",
    input_type={},
    output_type=types.List(wdt.ProjectType),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
    instance {{
        projects_500: projects {{
            edges {{
                node {{
                    {wdt.Project.REQUIRED_FRAGMENT}
                    {inner}
                }}
            }}
        }}
    }}
    """,
        is_root=True,
        root_resolver=root_all_projects_gql_resolver,
        gql_op_output_type=make_root_op_gql_op_output_type(
            "projects_500", lambda inputs: "", wdt.ProjectType
        ),
    ),
)
def root_all_projects():
    raise errors.WeaveGQLCompileError(
        "root-allProjects should not be executed directly. If you see this error, it is a bug in the Weave compiler."
    )


# Section 3/6: Attribute Getters
name = gql_prop_op("project-name", wdt.ProjectType, "name", types.String())
gql_prop_op(
    "project-createdAt",
    wdt.ProjectType,
    "createdAt",
    types.Timestamp(),
)
gql_prop_op(
    "project-updatedAt",
    wdt.ProjectType,
    "updatedAt",
    types.Timestamp(),
)

gql_prop_op(
    "project-internalId",
    wdt.ProjectType,
    "id",
    types.String(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "project-run",
    wdt.ProjectType,
    "run",
    wdt.RunType,
    {
        "runName": types.String(),
    },
    lambda inputs: f'name: {inputs["runName"]}',
)

gql_direct_edge_op(
    "project-entity",
    wdt.ProjectType,
    "entity",
    wdt.EntityType,
)

gql_direct_edge_op(
    "project-runQueues",
    wdt.ProjectType,
    "runQueues",
    wdt.RunQueueType,
    is_many=True,
)

gql_direct_edge_op(
    "project-artifactType",
    wdt.ProjectType,
    "artifactType",
    wdt.ArtifactTypeType,
    {
        "artifactType": types.String(),
    },
    lambda inputs: f'name: {inputs["artifactType"]}',
)

gql_direct_edge_op(
    "project-artifactVersion",
    wdt.ProjectType,
    "artifact",
    wdt.ArtifactVersionType,
    {
        "artifactName": types.String(),
        "artifactVersionAlias": types.String(),
    },
    lambda inputs: f'name: {json.dumps(inputs.raw["artifactName"] + ":" + inputs.raw["artifactVersionAlias"])}',
)

gql_direct_edge_op(
    "project-artifact",
    wdt.ProjectType,
    "artifactCollection",
    wdt.ArtifactCollectionType,
    {
        "artifactName": types.String(),
    },
    lambda inputs: f'name: {inputs["artifactName"]}',
)

# Section 5/6: Connection Ops
gql_connection_op(
    "project-artifactTypes",
    wdt.ProjectType,
    "artifactTypes",
    wdt.ArtifactTypeType,
    {},
    # lambda inputs: "first: 10",
)

gql_connection_op(
    "project-runs",
    wdt.ProjectType,
    "runs",
    wdt.RunType,
    {},
    lambda inputs: "first: 100",
)


gql_connection_op(
    "project-filteredRuns",
    wdt.ProjectType,
    "runs",
    wdt.RunType,
    {
        "filter": types.String(),
        "order": types.String(),
    },
    lambda inputs: f'first: 100, filters: {inputs["filter"]}, order: {inputs["order"]}',
)


# Section 6/6: Non Standard Business Logic Ops
# Note: with project-link, the gql variables are already part fo the required fragment
# so there is nothing more to do here.
@op(
    name="project-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
            entity {
                id
                name
            }
        """
    ),
)
def link(project: wdt.Project) -> wdt.Link:
    return wdt.Link(project["name"], f"{project['entity']['name']}/{project['name']}")


def _project_artifacts_gql_op_output_type(
    inputs: input_provider.InputProvider, input_type: types.Type
) -> types.Type:
    return types.List(
        wdt.ArtifactCollectionType.with_keys(
            typing.cast(typing.Any, input_type)
            .keys["artifactTypes_100"]["edges"]
            .object_type["node"]["artifactCollections_100"]["edges"]
            .object_type["node"]
            .property_types
        )
    )


@op(
    name="project-artifacts",
    output_type=lambda input_types: types.List(wdt.ArtifactCollectionType),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
            artifactTypes_100: artifactTypes(first: 100) {{
                edges {{
                    node {{
                        id
                        artifactCollections_100: artifactCollections(first: 100) {{
                            edges {{
                                node {{
                                    {wdt.ArtifactCollection.REQUIRED_FRAGMENT}
                                    {inner}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        """,
        gql_op_output_type=_project_artifacts_gql_op_output_type,
    ),
)
def artifacts(
    project: wdt.Project,
):
    return [
        wdt.ArtifactCollection.from_keys(edge["node"])
        for typeEdge in project["artifactTypes_100"]["edges"]
        for edge in typeEdge["node"]["artifactCollections_100"]["edges"]
    ]

def _get_project_traces(project, payload):
    project_id = f'{project["entity"]["name"]}/{project["name"]}'
    filter = None
    limit = None 
    offset = None
    sort_by = None
    query = None
    if payload is not None:
        filter = payload.get("filter")
        limit = payload.get("limit") 
        offset = payload.get("offset")
        sort_by = payload.get("sort_by")
        query = payload.get("query")
    trace_api = get_wandb_trace_api()
    return trace_api.query_calls_stream(project_id, filter=filter, limit=limit, offset=offset, sort_by=sort_by, query=query)

traces_filter_property_types = {
    "op_names": types.optional(types.List(types.String())),
    "input_refs": types.optional(types.List(types.String())),
    "output_refs": types.optional(types.List(types.String())),
    "parent_ids": types.optional(types.List(types.String())),
    "trace_ids": types.optional(types.List(types.String())),
    "call_ids": types.optional(types.List(types.String())),
    "trace_roots_only": types.optional(types.Boolean()),
    "wb_user_ids": types.optional(types.List(types.String())),
    "wb_run_ids": types.optional(types.List(types.String())),
}

traces_input_types = {
    "project": wdt.ProjectType,
    "payload": types.optional(types.TypedDict(property_types={
        "filter": types.optional(types.TypedDict(property_types=traces_filter_property_types, not_required_keys=set(traces_filter_property_types.keys()))),
        "limit": types.optional(types.Number()),
        "offset": types.optional(types.Number()),
        "sort_by": types.optional(types.List(types.TypedDict(property_types={"field": types.String(), "direction": types.String()}))),
        "query": types.optional(types.Dict())
    }, not_required_keys=set(['filter', 'limit', 'offset', 'sort_by', 'query'])))
}

traces_output_type = types.TypedDict(property_types={
    "id": types.String(),
    "project_id": types.String(),
    "op_name": types.String(),
    "display_name": types.optional(types.String()),
    "trace_id": types.String(),
    "parent_id": types.optional(types.String()),
    "started_at": types.Timestamp(),
    "attributes": types.Dict(types.String(), types.Any()),
    "inputs": types.Dict(types.String(), types.Any()),
    "ended_at": types.optional(types.Timestamp()),
    "exception": types.optional(types.String()),
    "output": types.optional(types.Any()),
    "summary": types.optional(types.Any()),
    "wb_user_id": types.optional(types.String()),
    "wb_run_id": types.optional(types.String()),
    "deleted_at": types.optional(types.Timestamp()) 
})

@op(
    name="project-tracesType",
    input_type=traces_input_types,
    output_type=types.TypeType(),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
            entity {
                id
                name
            }
        """
    ),
    hidden=True
)
def traces_type(project, payload):
    res = _get_project_traces(project, payload)
    if res:
        return types.TypeRegistry.type_of(res)
    else:
        return types.TypeRegistry.type_of([])

@op(
    name="project-traces",
    input_type=traces_input_types,
    output_type=ops_arrow.ArrowWeaveListType(traces_output_type),
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: """
            entity {
                id
                name
            }
        """
    ),
    refine_output_type=traces_type,
    hidden=True
)
def traces(project, payload):
    res = _get_project_traces(project, payload)
    if res:
        return ops_arrow.to_arrow(res)
    else:
        return ops_arrow.to_arrow([])
