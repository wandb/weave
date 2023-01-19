import os
import dataclasses
import shutil

from . import errors

from ..artifact_wandb import ArtifactVersionFileType
from ..api import op, mutation, weave_class
from .. import weave_types as types
from .. import wandb_util
from .. import ops_arrow
from .. import artifact_wandb

_py_open = open


def path_ext(path):
    return os.path.splitext(path)[1].strip(".")


##### These are actually path ops, but they are called file for legacy reason


@op(
    name="file-dir",
    input_type={"file": types.UnionType(types.DirType(), types.FileType())},
    output_type=types.DirType(),
)
def file_dir(file):
    if not isinstance(file, Dir):
        raise ValueError("Not a dir")
    return file


##### End path ops

file_or_artifact_version_file_type = types.union(
    types.FileType(), ArtifactVersionFileType()
)

#### TODO: Table does not belong here!


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
            "partitionedTable": types.TypedDict({"parts_path": types.String()}),
            "file": ArtifactVersionFileType(),
        }


@weave_class(weave_type=PartitionedTableType)
class PartitionedTable:
    def __init__(self, _rows, partitionedTable, file):
        self._rows = _rows
        self.partitionedTable = partitionedTable
        self.file = file

    @op(
        name="partitionedtable-file",
        input_type={"partitionedTable": PartitionedTableType()},
        output_type=ArtifactVersionFileType(),
    )
    def partitioned_file(partitionedTable):
        return partitionedTable.file

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


def _data_is_legacy_run_file_format(data):
    keys = set(data.keys())
    return keys == {"columns", "data"}


def _data_is_weave_file_format(data):
    return "columns" in data and "data" in data and "column_types" in data


def _get_rows_and_object_type_from_legacy_format(data):
    rows = [dict(zip(data["columns"], row)) for row in data["data"]]
    object_type = types.TypeRegistry.type_of(rows).object_type
    return rows, object_type


def _get_rows_and_object_type_from_weave_format(data, file):
    rows = []
    wb_artifact = None
    if hasattr(file, "artifact") and isinstance(
        file.artifact, artifact_wandb.WandbArtifact
    ):
        wb_artifact = file.artifact._saved_artifact
    row_data = data["data"]
    column_types = data["column_types"]
    converted_object_type = wandb_util.weave0_type_json_to_weave1_type(
        column_types, wb_artifact
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
            unknown_col_example_data = [row[i] for row in row_data]
            detected_type = types.TypeRegistry.type_of(unknown_col_example_data)
            obj_prop_types[key] = detected_type.object_type
        else:
            obj_prop_types[key] = col_type
    object_type = types.TypedDict(obj_prop_types)

    # TODO: this will need to recursively convert dicts to Objects in some
    # cases.
    for data_row in row_data:
        row = {}
        for col_name, val in zip(data["columns"], data_row):
            row[col_name] = val
        rows.append(row)
    return rows, object_type


@weave_class(weave_type=types.FileType)
class File:
    @op(
        name="file-table",
        input_type={"file": file_or_artifact_version_file_type},
        output_type=TableType(),
    )
    def table(file):
        local_path = file.get_local_path()
        import json

        with _py_open(local_path) as f:
            data = json.load(f)

        rows = []
        object_type = None

        if _data_is_legacy_run_file_format(data):
            rows, object_type = _get_rows_and_object_type_from_legacy_format(data)
        elif _data_is_weave_file_format(data):
            rows, object_type = _get_rows_and_object_type_from_weave_format(data, file)
        else:
            raise errors.WeaveInternalError("Unknown table file format for data")

        res = ops_arrow.to_arrow_from_list_and_artifact(
            rows, object_type, file.artifact
        )
        # I Don't think I need Table now. We won't parse again
        return Table(res)

    @op(
        name="file-partitionedTable",
        input_type={"file": file_or_artifact_version_file_type},
        output_type=PartitionedTableType(),
    )
    def partitioned_table(file):
        local_path = file.get_local_path()
        import json

        with _py_open(local_path) as f:
            data = json.load(f)

        parts_path_root = data["parts_path"]

        all_rows = []
        all_object_type = types.UnknownType()
        for entry_path in file.artifact._saved_artifact.manifest.entries.keys():
            if entry_path.startswith(parts_path_root) and entry_path.endswith(
                ".table.json"
            ):
                local_part_path = file.artifact.path(entry_path)
                with _py_open(local_part_path) as part_file:
                    part_data = json.load(part_file)
                if _data_is_legacy_run_file_format(part_data):
                    rows, object_type = _get_rows_and_object_type_from_legacy_format(
                        part_data
                    )
                elif _data_is_weave_file_format(part_data):
                    rows, object_type = _get_rows_and_object_type_from_weave_format(
                        part_data, file
                    )
                else:
                    raise errors.WeaveInternalError(
                        "Unknown table file format for data"
                    )
                all_rows.extend(rows)
                all_object_type = types.merge_types(all_object_type, object_type)
        arrow_rows = ops_arrow.to_arrow_from_list_and_artifact(
            all_rows, all_object_type, file.artifact
        )
        return PartitionedTable(arrow_rows, data, file)

    @op(
        name="file-directUrlAsOf",
        input_type={
            "file": file_or_artifact_version_file_type,
            "asOf": types.Int(),
        },
        output_type=types.String(),
    )
    def direct_url_as_of(file, asOf):
        # TODO: This should depend on whether its local or an artifact
        #    etc
        local_path = os.path.abspath(file.get_local_path())
        return "/__weave/file/%s" % local_path

    @op(
        name="file-size", input_type={"file": types.FileType()}, output_type=types.Int()
    )
    def file_size(file):
        # file is an artifact manifest entry for now.
        return 10
        return file.size

    @mutation
    def file_contents_set(self, val):
        return self._file_contents_set(val)

    @op(
        setter=file_contents_set,
        name="file-contents",
        input_type={"file": types.FileType()},
        output_type=types.String(),
    )
    def file_contents(file):
        return file._contents()


types.FileType.instance_class = File
types.FileType.instance_classes = File


# Question, should all tables be lazy? That would mean we can serialize
#     and hand them between processes.... How would the user choose to
#     save a serialized version of a given table?


@op(
    name="file-type",
    input_type={"file": types.UnionType(types.FileType(), types.DirType())},
    output_type=types.TypeType(),
)
def file_type(file):
    if isinstance(file, Dir):
        return {"type": "dir"}
    # file is an artifact manifest entry for now.
    path = file.path
    parts = path.split(".")
    extension = None
    if len(parts) > 1:
        extension = parts[-1]
    result_type = {"type": "file", "extension": extension}
    if len(parts) > 2 and extension == "json":
        # TODO: validate. I'm sure there is existing logic for this in wandb
        result_type["wbObjectType"] = {
            "type": parts[-2],
        }
    return result_type


@weave_class(weave_type=types.SubDirType)
class SubDir(object):
    def __init__(self, fullPath, size, dirs, files):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files


types.SubDirType.instance_classes = SubDir
types.SubDirType.instance_class = SubDir


@op(
    name="dir-pathReturnType",
    input_type={"dir": types.DirType(), "path": types.String()},
    output_type=types.TypeType(),
)
def path_return_type(dir, path):
    return dir._path_return_type(path)


@weave_class(weave_type=types.DirType)
class Dir:
    def __init__(self, fullPath, size, dirs, files):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files

    def get_local_path(self):
        return self.path

    @op(name="dir-size", input_type={"dir": types.DirType()}, output_type=types.Int())
    def size(dir):
        return dir.size

    @op(
        name="dir-path",
        input_type={"dir": types.DirType(), "path": types.String()},
        output_type=types.UnionType(types.FileType(), types.DirType(), types.none_type),
        refine_output_type=path_return_type,
    )
    def open(dir, path):
        return dir._path(path)


types.DirType.instance_classes = Dir
types.DirType.instance_class = Dir

#### VersionedDir is a directory that will automatically be saved to
# an artifact when it is used.
# TODO: the File/Dir/Artifact/Local/VersionedDir design needs to be
#    reworked. File/Dir are more like Refs...


class VersionedDirType(types.Type):
    def save_instance(self, obj, artifact, name):
        with artifact.new_dir(f"{name}") as dirpath:
            shutil.copytree(obj.path, dirpath, dirs_exist_ok=True)

    def load_instance(self, artifact, name, extra=None):
        return VersionedDir(artifact.path(name))


@weave_class(weave_type=VersionedDirType)
@dataclasses.dataclass
class VersionedDir:
    path: str


VersionedDirType.instance_classes = VersionedDir
