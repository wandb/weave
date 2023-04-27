import typing

from . import wb_util
from . import table
from .. import weave_types as types
from .. import artifact_fs


class TypeCount(typing.TypedDict):
    type: str
    count: int
    keys: dict[str, list["TypeCount"]]  # type: ignore
    items: list["TypeCount"]  # type: ignore
    nested_types: list[str]


def history_key_type_count_to_weave_type(tc: TypeCount) -> types.Type:
    from .wbmedia import ImageArtifactFileRefType
    from .trace_tree import WBTraceTree

    tc_type = tc["type"]
    if tc_type == "string":
        return types.String()
    elif tc_type == "number":
        return types.Number()
    elif tc_type == "nil":
        return types.NoneType()
    elif tc_type == "bool":
        return types.Boolean()
    elif tc_type == "map":
        return types.TypedDict(
            {
                key: types.union(
                    *[history_key_type_count_to_weave_type(vv) for vv in val]
                )
                for key, val in tc["keys"].items()
            }
        )
    elif tc_type == "list":
        if "items" not in tc:
            return types.List(types.UnknownType())
        return types.List(
            types.union(*[history_key_type_count_to_weave_type(v) for v in tc["items"]])
        )
    elif tc_type == "histogram":
        return wb_util.WbHistogram.WeaveType()  # type: ignore
    elif tc_type == "table-file":
        extension = types.Const(types.String(), "json")
        return artifact_fs.FilesystemArtifactFileType(extension, table.TableType())
    elif tc_type == "joined-table":
        extension = types.Const(types.String(), "json")
        return artifact_fs.FilesystemArtifactFileType(
            extension, table.JoinedTableType()
        )
    elif tc_type == "partitioned-table":
        extension = types.Const(types.String(), "json")
        return artifact_fs.FilesystemArtifactFileType(
            extension, table.PartitionedTableType()
        )
    elif tc_type == "image-file":
        return ImageArtifactFileRefType()
    elif tc_type == "wb_trace_tree":
        return WBTraceTree.WeaveType()  # type: ignore
    return types.UnknownType()
