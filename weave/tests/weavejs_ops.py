# WeaveJS ops used for testing. These are not used in production.

from ..ops_primitives.file import TableType
from ..ops_domain import wb_domain_types as wbt
from ..ops_primitives._dict_utils import typeddict_pick_output_type
from .. import weave_types as types
from .. import graph
from .. import weave_internal
from ..language_features.tagging import tagged_value_type
from ..language_features.tagging.tagging_op_logic import (
    op_get_tag_type_resolver,
    op_make_type_tagged_resolver,
)


def ensure_node(v):
    if isinstance(v, graph.Node):
        return v
    return weave_internal.const(v)


def weavejs_pick(obj: graph.Node, key: str):
    raw_output_type = typeddict_pick_output_type(
        {"self": obj.type, "key": types.Const(types.String(), key)}
    )
    output_type = op_make_type_tagged_resolver(
        raw_output_type, op_get_tag_type_resolver(obj.type)
    )
    return weave_internal.make_output_node(
        output_type,
        "pick",
        {"obj": obj, "key": graph.ConstNode(types.String(), key)},
    )


def count(arr):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        types.Number(),
        "count",
        {
            "arr": arr_node,
        },
    )


def index(arr, index):
    arr_node = ensure_node(arr)
    index_node = ensure_node(index)
    output_type = op_make_type_tagged_resolver(
        arr_node.type.object_type, op_get_tag_type_resolver(arr_node.type)
    )
    return weave_internal.make_output_node(
        output_type,
        "index",
        {
            "arr": arr_node,
            "index": index_node,
        },
    )


def filter(arr, filterFn):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "filter",
        {
            "arr": arr_node,
            "filterFn": ensure_node(filterFn),
        },
    )


def map(arr, mapFn):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "map",
        {
            "arr": arr_node,
            "mapFn": ensure_node(mapFn),
        },
    )


def sort(arr, compFn, columnDirs):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "sort",
        {
            "arr": arr_node,
            "compFn": ensure_node(compFn),
            "columnDirs": ensure_node(columnDirs),
        },
    )


def groupby(arr, groupByFn):
    arr_node = ensure_node(arr)
    groupByFn_node = ensure_node(groupByFn)
    return weave_internal.make_output_node(
        types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict({"groupKey": groupByFn_node.type.output_type}),
                types.List(arr_node.type.object_type),
            )
        ),
        "groupby",
        {"arr": arr_node, "groupByFn": groupByFn_node},
    )


def offset(arr, offset):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "offset",
        {
            "arr": arr_node,
            "offset": ensure_node(offset),
        },
    )


def limit(arr, limit):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "limit",
        {
            "arr": arr_node,
            "limit": ensure_node(limit),
        },
    )


def file_type(file):
    file_node = ensure_node(file)
    output_type = op_make_type_tagged_resolver(
        types.TypeType(), op_get_tag_type_resolver(file_node.type)
    )
    return weave_internal.make_output_node(
        output_type,
        "file-type",
        {
            "file": file_node,
        },
    )


def root_project(entity_name, project_name):
    return weave_internal.make_output_node(
        wbt.ProjectType,
        "root-project",
        {
            "entityName": ensure_node(entity_name),
            "projectName": ensure_node(project_name),
        },
    )

def project_artifact(project, artifact_name):
    return weave_internal.make_output_node(
        wbt.ArtifactCollectionType,
        "project-artifact",
        {
            "project": project,
            "artifactName": ensure_node(artifact_name),
        },
    )

def artifact_membership_for_alias(artifact_node, alias):
    return weave_internal.make_output_node(
        wbt.ArtifactCollectionMembershipType,
        "artifact-membershipForAlias",
        {
            "artifact": artifact_node,
            "aliasName": ensure_node(alias),
        },
    )

def artifact_membership_artifact_version(artifact_membership):
    return weave_internal.make_output_node(
        wbt.ArtifactVersionType,
        "artifactMembership-artifactVersion",
        {
            "artifactMembership": artifact_membership,
        },
    )

def artifact_version_file(artifact_version, path):
    return weave_internal.make_output_node(
        types.optional(types.FileType()),
        "artifactVersion-file",
        {
            "artifactVersion": artifact_version,
            "path": ensure_node(path)
        },
    )

def file_table(file):
    return weave_internal.make_output_node(
        types.optional(TableType()),
        "file-table",
        {
            "file": file,
        },
    )

def table_rows(table):
    return weave_internal.make_output_node(
        types.List(types.TypedDict()),
        "table-rows",
        {
            "table": table,
        },
    )

def create_index_checkpoint(list_of_dicts):
    return weave_internal.make_output_node(
        types.List(tagged_value_type.TaggedValueType(types.TypedDict({"index": types.Number()}), list_of_dicts.type.object_type)),
        "list-createIndexCheckpointTag",
        {
            "arr": list_of_dicts,
        },
    )
