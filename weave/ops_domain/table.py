import dataclasses
import json
import typing


from ..api import op, weave_class
from .. import ops_arrow
from .. import weave_types as types
from .. import artifact_fs
from .. import artifact_wandb
from .. import errors
from .. import wandb_util
from .. import weave_internal
from .. import engine_trace
from . import wbmedia


@dataclasses.dataclass(frozen=True)
class TableType(types.ObjectType):
    name = "table"

    def property_types(self):
        return {"_rows": ops_arrow.ArrowWeaveListType(types.TypedDict({}))}


@weave_class(weave_type=TableType)
class Table:
    def __init__(self, _rows):
        self._rows = _rows

    @op(
        name="table-rowsType",
        input_type={"table": TableType()},
        output_type=types.TypeType(),
    )
    def rows_type(table):
        ttype = types.TypeRegistry.type_of(table._rows)
        return ttype

    @op(
        name="table-rows",
        input_type={"table": TableType()},
        output_type=ops_arrow.ArrowWeaveListType(types.TypedDict({})),
        refine_output_type=rows_type,
    )
    def rows(table):
        return table._rows


@dataclasses.dataclass(frozen=True)
class PartitionedTableType(types.ObjectType):
    name = "partitioned-table"

    def property_types(self):
        return {
            "_rows": ops_arrow.ArrowWeaveListType(types.TypedDict({})),
            "_file": artifact_fs.FilesystemArtifactFileType(),
            "partitionedTable": types.TypedDict({"parts_path": types.String()}),
        }


@weave_class(weave_type=PartitionedTableType)
class PartitionedTable:
    def __init__(self, _rows, _file, partitionedTable):
        self._rows = _rows
        self._file = _file
        self.partitionedTable = partitionedTable

    @op(
        name="partitionedtable-file",
        input_type={"partitionedTable": PartitionedTableType()},
        output_type=artifact_fs.FilesystemArtifactFileType(),
    )
    def partitioned_file(partitionedTable):
        return partitionedTable._file

    @op(
        name="partitionedtable-rowsType",
        input_type={"partitionedtable": PartitionedTableType()},
        output_type=types.TypeType(),
    )
    def partitioned_rows_type(partitionedtable):
        ttype = types.TypeRegistry.type_of(partitionedtable._rows)
        return ttype

    @op(
        name="partitionedtable-rows",
        input_type={"partitionedtable": PartitionedTableType()},
        output_type=ops_arrow.ArrowWeaveListType(types.TypedDict({})),
        refine_output_type=partitioned_rows_type,
    )
    def rows(partitionedtable):
        return partitionedtable._rows


@dataclasses.dataclass(frozen=True)
class JoinedTableType(types.ObjectType):
    name = "joined-table"

    def property_types(self):
        return {
            "_rows": ops_arrow.ArrowWeaveListType(types.TypedDict({})),
            "_file": artifact_fs.FilesystemArtifactFileType(),
        }


@weave_class(weave_type=JoinedTableType)
class JoinedTable:
    def __init__(self, _rows, _file):
        self._rows = _rows
        self._file = _file

    @op(
        name="joinedtable-file",
        input_type={"joinedTable": JoinedTableType()},
        output_type=artifact_fs.FilesystemArtifactFileType(),
    )
    def joined_file(joinedTable):
        return joinedTable._file

    @op(
        name="joinedtable-rowsType",
        input_type={"joinedtable": JoinedTableType()},
        output_type=types.TypeType(),
    )
    def joined_rows_type(joinedtable):
        ttype = types.TypeRegistry.type_of(joinedtable._rows)
        return ttype

    @op(
        name="joinedtable-rows",
        input_type={"joinedtable": JoinedTableType()},
        output_type=ops_arrow.ArrowWeaveListType(types.TypedDict({})),
        refine_output_type=joined_rows_type,
    )
    def rows(joinedtable):
        return joinedtable._rows


def _data_is_legacy_run_file_format(data):
    return "columns" in data and "data" in data


def _data_is_weave_file_format(data):
    return "columns" in data and "data" in data and "column_types" in data


def _sample_rows(data: list, max_rows: int = 1000) -> list:
    data_len = len(data)
    if data_len > max_rows:
        split_size = max_rows // 3
        gap_size = (data_len - max_rows) // 2
        start_split = data[:split_size]
        middle_start = split_size + gap_size
        middle_split = data[middle_start : middle_start + split_size]
        end_split = data[-split_size:]
        return start_split + middle_split + end_split
    return data


def _infer_type_from_cell(cell: typing.Any) -> types.Type:
    if isinstance(cell, dict) and "_type" in cell and isinstance(cell["_type"], str):
        maybe_type = types.type_name_to_type(cell["_type"])
        if maybe_type is not None:
            return maybe_type()
    return types.TypeRegistry.type_of(cell)


def _infer_type_from_row_dict(row: dict) -> types.Type:
    return types.TypedDict({k: _infer_type_from_cell(v) for k, v in row.items()})


def _infer_type_from_col_list(row: list) -> types.Type:
    running_type: types.Type = types.UnknownType()
    for cell in row:
        running_type = types.merge_types(running_type, _infer_type_from_cell(cell))
    return running_type


def _infer_type_from_row_dicts(rows: list[dict]) -> types.Type:
    running_type: types.Type = types.UnknownType()
    for row in rows:
        running_type = types.merge_types(running_type, _infer_type_from_row_dict(row))
    return running_type


def _get_rows_and_object_type_from_legacy_format(data: dict) -> tuple[list, types.Type]:
    # W&B dataframe columns are ints, we always want strings
    data["columns"] = [str(c) for c in data["columns"]]
    rows = [dict(zip(data["columns"], row)) for row in data["data"]]
    object_type = _infer_type_from_row_dicts(_sample_rows(rows))
    return rows, object_type


def _get_rows_and_object_type_from_weave_format(
    data: typing.Any, file: artifact_fs.FilesystemArtifactFile
) -> tuple[list, types.Type]:
    rows = []
    artifact = file.artifact
    if not isinstance(artifact, artifact_wandb.WandbArtifact):
        raise errors.WeaveInternalError(
            "Weave table file format is only supported for wandb artifacts"
        )
    row_data = data["data"]
    column_types = data["column_types"]
    converted_object_type = wandb_util.weave0_type_json_to_weave1_type(column_types)
    if not isinstance(converted_object_type, types.TypedDict):
        raise errors.WeaveInternalError(
            "Weave table file format only supports typed dicts"
        )
    # Fix two things:
    # 1. incoming table column names may not match the order of column_types
    # 2. if we had an unknown (happens when old type is "PythonObjectType")
    #    we need to manually detect the type.
    obj_prop_types = {}
    for i, key in enumerate(data["columns"]):
        if key not in converted_object_type.property_types:
            # Since when a WB table is saved with a numeric column name, it is
            # stored as a number in `columns` but a string in the keys of
            # `properties`. This patch is to handle that case. A similar case
            # had to be handled in Weave0
            if str(key) in converted_object_type.property_types:
                key = str(key)
            else:
                raise errors.WeaveTableDeserializationError(
                    f"Column name {key} not found in column_types"
                )
        col_type = converted_object_type.property_types[key]
        if col_type.assign_type(types.UnknownType()):
            # Sample some data to detect the type. Otherwise this
            # can be very expensive. This could cause down-stream crashes,
            # for example if we don't realize that a column is union of string
            # and int, saving to arrow will crash.
            unknown_col_example_data = [row[i] for row in _sample_rows(row_data)]
            obj_prop_types[key] = _infer_type_from_col_list(unknown_col_example_data)
        else:
            obj_prop_types[key] = col_type
    object_type = types.TypedDict(obj_prop_types)

    # TODO: this will need to recursively convert dicts to Objects in some
    # cases.
    for data_row in row_data:
        row: dict[str, typing.Any] = {}
        for col_name, val in zip(data["columns"], data_row):
            if isinstance(val, dict) and "_type" in val and "path" in val:
                file_path = val["path"]
                if val["_type"] == "image-file":
                    val = wbmedia.ImageArtifactFileRef(
                        artifact=file.artifact,
                        path=file_path,
                        format=val["format"],
                        height=val["height"],
                        width=val["width"],
                        sha256=val["sha256"],
                    )
                elif val["_type"] in [
                    "audio-file",
                    "bokeh-file",
                    "video-file",
                    "object3D-file",
                    "molecule-file",
                    "html-file",
                ]:
                    type_cls = types.type_name_to_type(val["_type"])
                    if type_cls is not None and type_cls.instance_class is not None:
                        val = type_cls.instance_class(file.artifact, file_path)
            row[str(col_name)] = val
        rows.append(row)
    return rows, object_type


@dataclasses.dataclass
class _TableLikeAWLFromFileResult:
    awl: ops_arrow.ArrowWeaveList
    data: dict


def _get_table_like_awl_from_file(
    file: typing.Union[
        artifact_fs.FilesystemArtifactFile, artifact_fs.FilesystemArtifactDir, None
    ],
) -> _TableLikeAWLFromFileResult:
    tracer = engine_trace.tracer()
    if file is None or isinstance(file, artifact_fs.FilesystemArtifactDir):
        raise errors.WeaveInternalError("File is None or a directory")
    with file.open() as f:
        with tracer.trace("get_table:jsonload"):
            data = json.load(f)

    if file.path.endswith(".joined-table.json"):
        awl = _get_joined_table_awl_from_file(data, file)
    elif file.path.endswith(".partitioned-table.json"):
        awl = _get_partitioned_table_awl_from_file(data, file)
    elif file.path.endswith(".table.json"):
        awl = _get_table_awl_from_file(data, file)
    else:
        raise errors.WeaveInternalError(
            f"Unknown table file format for path: {file.path}"
        )
    return _TableLikeAWLFromFileResult(awl, data)


def _get_table_awl_from_file(
    data: dict, file: artifact_fs.FilesystemArtifactFile
) -> "ops_arrow.ArrowWeaveList":
    tracer = engine_trace.tracer()
    rows: list = []
    object_type = None

    with tracer.trace("get_table:get_rows_and_object_type"):
        if _data_is_weave_file_format(data):
            rows, object_type = _get_rows_and_object_type_from_weave_format(data, file)
        elif _data_is_legacy_run_file_format(data):
            rows, object_type = _get_rows_and_object_type_from_legacy_format(data)
        else:
            raise errors.WeaveInternalError("Unknown table file format for data")

    with tracer.trace("get_table:to_arrow"):
        return ops_arrow.to_arrow_from_list_and_artifact(
            rows, object_type, file.artifact
        )


def _get_partitioned_table_awl_from_file(
    data: dict, file: artifact_fs.FilesystemArtifactFile
) -> ops_arrow.ArrowWeaveList:
    parts_path_root = data["parts_path"]

    all_aws: list[ops_arrow.ArrowWeaveList] = []
    part_dir = file.artifact.path_info(parts_path_root)
    if isinstance(part_dir, artifact_fs.FilesystemArtifactDir):
        for file in part_dir.files.values():
            all_aws.append(_get_table_like_awl_from_file(file).awl)
    arrow_weave_list = ops_arrow.list_.concat.raw_resolve_fn(all_aws)
    return arrow_weave_list


def _get_joined_table_awl_from_file(
    data: dict, file: artifact_fs.FilesystemArtifactFile
) -> ops_arrow.ArrowWeaveList:
    join_key = data["join_key"]

    table_1_path = data["table1"]
    table_2_path = data["table2"]

    awl_1 = _get_table_like_awl_from_file(file.artifact.path_info(table_1_path)).awl
    awl_2 = _get_table_like_awl_from_file(file.artifact.path_info(table_2_path)).awl

    join_fn_1 = weave_internal.define_fn(
        {"row": awl_1.object_type}, lambda row: row[join_key]
    )
    join_fn_2 = weave_internal.define_fn(
        {"row": awl_2.object_type}, lambda row: row[join_key]
    )

    # Note: in WeaveJS, we allow the user to specify the join type, but
    # in practice it is always a full-outer join. If we want to parameterize that
    # then we need to filter out the unneeded rows in joinedTable-rows since we
    # eagerly construct the rows here.
    arrow_weave_list = ops_arrow.list_.join_2.raw_resolve_fn(
        awl_1, awl_2, join_fn_1.val, join_fn_2.val, "0", "1", True, True
    )
    return arrow_weave_list


@op(name="file-table")
def file_table(file: artifact_fs.FilesystemArtifactFile) -> Table:
    return Table(_get_table_like_awl_from_file(file).awl)


@op(name="file-partitionedTable")
def partitioned_table(file: artifact_fs.FilesystemArtifactFile) -> PartitionedTable:
    res = _get_table_like_awl_from_file(file)
    return PartitionedTable(res.awl, file, res.data)


@op(name="file-joinedTable")
def joined_table(file: artifact_fs.FilesystemArtifactFile) -> JoinedTable:
    return JoinedTable(_get_table_like_awl_from_file(file).awl, file)
