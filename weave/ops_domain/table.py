import dataclasses
import json
import datetime
import logging
import typing
import asyncio


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
from .. import timestamp as weave_timestamp
from .. import io_service
from .. import util
from ..ops_domain import trace_tree


@dataclasses.dataclass(frozen=True)
class TableType(types.ObjectType):
    name = "table"

    def property_types(self):
        return {
            "_rows": ops_arrow.ArrowWeaveListType(types.TypedDict({})),
        }


@weave_class(weave_type=TableType)
class Table:
    def __init__(self, _rows):
        self._rows = _rows

    @op(
        name="table-rowsType",
        input_type={"table": types.optional(TableType())},
        output_type=types.TypeType(),
        hidden=True,
    )
    def rows_type(table):
        if table == None:
            return types.NoneType()
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
        hidden=True,
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
        hidden=True,
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


def _infer_type_from_cell(cell: typing.Any) -> types.Type:
    if isinstance(cell, dict) and "_type" in cell and isinstance(cell["_type"], str):
        maybe_type = types.type_name_to_type(cell["_type"])
        if maybe_type is not None:
            return maybe_type()
    return types.TypeRegistry.type_of(cell)


def _infer_type_from_row_dict(row: dict) -> types.Type:
    return types.TypedDict({k: _infer_type_from_cell(v) for k, v in row.items()})


def _infer_type_from_col_list(row: list) -> types.Type:
    if len(row) == 0:
        return types.NoneType()
    running_type: types.Type = types.UnknownType()
    for cell in row:
        running_type = types.merge_types(running_type, _infer_type_from_cell(cell))
    return running_type


def _infer_type_from_row_dicts(rows: list[dict]) -> types.TypedDict:
    if len(rows) == 0:
        return types.TypedDict({})
    running_type: types.Type = types.UnknownType()
    for row in rows:
        running_type = types.merge_types(running_type, _infer_type_from_row_dict(row))
    if not isinstance(running_type, types.TypedDict):
        raise errors.WeaveInternalError(
            f"Expected running_type to be a TypedDict, but got {running_type}"
        )
    return running_type


@dataclasses.dataclass
class PeerTableReader:
    """
    Provides a simple interface for reading rows from a peer table. Peer tables
    can be read via index - which is straight forward. Peer tables can be read
    via a column key - which we want to return the first row which matches this
    value (think of it like a join but just getting the first value.) We can
    optimize this by saving the reverse index map while reading and only read
    the necessary rows. This means we will only visit each "cell" in the table
    at most 1 time.
    """

    peer_rows: list[dict]
    peer_object_type: types.TypedDict
    lookup_map: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    scan_loc: dict[str, int] = dataclasses.field(default_factory=dict)

    def row_at_index(self, index: int) -> dict:
        return self.peer_rows[index]

    def row_at_key(self, column: str, key: str) -> typing.Optional[dict]:
        # First, we create a default index map for this column if it doesn't
        # exist.
        if column not in self.lookup_map:
            self.lookup_map[column] = {}
            self.scan_loc[column] = 0
        index_map = self.lookup_map[column]

        # If we have already seen this key, we can just return the row
        if key in index_map:
            return self.peer_rows[index_map[key]]

        # Otherwise, we scan the table until we find the key
        # creating a reverse index map as we go. This allows
        # us to break early, and continue the scan later if needed.
        while self.scan_loc[column] < len(self.peer_rows):
            curr_row = self.peer_rows[self.scan_loc[column]]
            cell_val = curr_row[column]
            if cell_val not in index_map:
                index_map[cell_val] = self.scan_loc[column]
            if cell_val == key:
                return curr_row
            self.scan_loc[column] += 1
        return None


def _in_place_join_in_linked_tables(
    rows: list[dict],
    object_type: types.TypedDict,
    column_types: wandb_util.Weave0TypeJson,
    file: artifact_fs.FilesystemArtifactFile,
) -> typing.Tuple[list[dict], types.TypedDict]:
    """
    This function will join in any peer linked tables. This is done by replacing
    the column with the source table's index (or key) with the peer table's row.
    This is done in place, and the object type is updated to reflect the new
    column types.

    Note: We are currently doing this "eagerly". However, it is reasonable to
    assume that once we can read table types quickly, we can differ this
    calculate in the form of a ref.
    """
    type_map = column_types["params"]["type_map"]
    for column_name, column_type in type_map.items():
        col_wb_type = column_type["wb_type"]
        if (
            col_wb_type in wandb_util.foreign_key_type_names
            or col_wb_type in wandb_util.foreign_index_type_names
        ):
            peer_file = file.artifact.path_info(column_type["params"]["table"])
            if peer_file is None:
                # if is none, then the file doesn't exist, so we can't join.
                # We will just set the column to an empty dict. This is preferred
                # over failing.
                peer_object_type = types.TypedDict({})
                # Update the row values
                for row in rows:
                    row[column_name] = {}
            elif isinstance(peer_file, artifact_fs.FilesystemArtifactDir):
                raise errors.WeaveInternalError("Peer file is a directory")
            else:
                with peer_file.open() as f:
                    tracer = engine_trace.tracer()
                    with tracer.trace("peer_table:jsonload"):
                        peer_data = json.load(f)
                (
                    peer_rows,
                    peer_object_type,
                ) = _get_rows_and_object_type_from_weave_format(peer_data, peer_file)
                peer_reader = PeerTableReader(peer_rows, peer_object_type)

                # Update the row values
                for row in rows:
                    if col_wb_type in wandb_util.foreign_index_type_names:
                        row[column_name] = peer_reader.row_at_index(row[column_name])
                    else:
                        row[column_name] = peer_reader.row_at_key(
                            column_type["params"]["col_name"], row[column_name]
                        )

            # update the object type
            object_type.property_types[column_name] = peer_object_type

    return rows, object_type


def _make_type_non_none(t: types.Type) -> types.Type:
    non_none_type = types.non_none(t)
    if isinstance(non_none_type, types.List):
        return types.List(_make_type_non_none(non_none_type.object_type))
    elif isinstance(non_none_type, types.TypedDict):
        return types.TypedDict(
            {k: _make_type_non_none(v) for k, v in non_none_type.property_types.items()}
        )
    return non_none_type


possible_media_type_classes = (
    wbmedia.LegacyImageArtifactFileRefType,
    wbmedia.ImageArtifactFileRefType,
    wbmedia.AudioArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.BokehArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.VideoArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.Object3DArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.MoleculeArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.HtmlArtifactFileRef.WeaveType,  # type: ignore
    wbmedia.LegacyTableNDArrayType,
)


def _table_data_to_weave1_objects(
    row_data: list[dict],
    file: artifact_fs.FilesystemArtifactFile,
    row_type: types.TypedDict,
) -> list[dict]:
    def _create_media_type_for_cell(cell: dict) -> typing.Any:
        file_type = cell["_type"]
        file_path = cell["path"]
        if file_type == "image-file":
            return wbmedia.ImageArtifactFileRef(
                artifact=file.artifact,
                path=file_path,
                format=cell["format"],
                height=cell.get("height", 0),
                width=cell.get("width", 0),
                sha256=cell.get("sha256", file_path),
                boxes=cell.get("boxes", {}),  # type: ignore
                masks=cell.get("masks", {}),  # type: ignore
                classes=cell.get("classes"),  # type: ignore
            )
        elif file_type in [
            "audio-file",
            "bokeh-file",
            "video-file",
            "object3D-file",
            "molecule-file",
            "html-file",
        ]:
            type_cls = types.type_name_to_type(file_type)
            if type_cls is not None and type_cls.instance_class is not None:
                return type_cls.instance_class(
                    file.artifact, file_path, cell.get("sha256", file_path)
                )
        else:
            raise errors.WeaveTableDeserializationError(
                f"Unsupported media type {file_type}"
            )

    def _process_cell_value(cell: typing.Any, cell_type: types.Type) -> typing.Any:
        if (
            isinstance(cell, list)
            and isinstance(cell_type, types.List)
            # We want to avoid recursing into the list if the list element type is basic,
            # since it will be a relatively expensive `O(n)` no-op.
            and not isinstance(cell_type.object_type, types.BasicType)
        ):
            cell = [_process_cell_value(c, cell_type.object_type) for c in cell]

        elif isinstance(cell, dict) and isinstance(cell_type, types.TypedDict):
            cell = {
                k: _process_cell_value(v, cell_type.property_types[str(k)])
                for k, v in cell.items()
            }
        # this is needed because tables store timestamps as unix epochs in ms, but the deserialized
        # representation in weave1 is a datetime object. we do the conversion here to ensure deserialized
        # timestamps all expose a common interface to weave1 callers.
        elif isinstance(cell_type, types.Timestamp):
            if cell is not None:
                cell = weave_timestamp.ms_to_python_datetime(
                    weave_timestamp.unitless_int_to_inferred_ms(cell)
                )
        elif isinstance(cell, dict):
            if isinstance(cell_type, possible_media_type_classes):
                cell = _create_media_type_for_cell(cell)
            elif isinstance(cell_type, trace_tree.WBTraceTree.WeaveType):  # type: ignore
                copy = {**cell}
                copy.pop("_type")
                cell = trace_tree.WBTraceTree(**copy)

        return cell

    non_null_prop_types = _make_type_non_none(row_type)
    non_null_prop_types = typing.cast(types.TypedDict, non_null_prop_types)

    rows: list[dict] = []
    for data_row in row_data:
        new_row = {
            k: _process_cell_value(v, non_null_prop_types.property_types[str(k)])
            for k, v in data_row.items()
        }
        rows.append(new_row)

    return rows


def _patch_legacy_image_file_types(
    rows: list[dict],
    object_type: types.TypedDict,
    file: artifact_fs.FilesystemArtifactFile,
    assume_legacy: bool = False,
):
    """
    This is a patch to make up for image files born before Oct 2021. Before then, we did not encode the
    full box and mask type information in the type system and unfortunately requires looking at the data.
    We will only look at the first 10 examples, however. This is a rewrite of the same patch function found here:
    https://github.com/wandb/core/blob/30d6d9eeb125904c00066f023ac404c957bf6bf7/lib/js/cg/src/ops/domain/table.ts#LL51C29-L51C29

    Note: this does not work for lists of images!
    """
    return_prop_types = {}
    class_types = (
        (wbmedia.LegacyImageArtifactFileRefType,)
        if not assume_legacy
        else (wbmedia.LegacyImageArtifactFileRefType, wbmedia.ImageArtifactFileRefType)
    )
    for col_name, col_type in object_type.property_types.items():
        return_prop_types[col_name] = col_type
        other_members = []

        # If the type is a union, we need to check if the union contains a legacy image type
        # If it does, we keep track of the peer types so we can re-create the union
        if isinstance(col_type, types.UnionType):
            found = False
            for member in col_type.members:
                if not isinstance(member, class_types):
                    other_members.append(member)
                else:
                    found = True
            if not found:
                continue

        # If the type is not a union, we need to check if it is a legacy image type
        elif not isinstance(col_type, class_types):
            continue

        # We will look at the first 10 rows of the table to determine the type.
        non_null_rows_evaluated = 0
        mask_keys_set: dict[str, bool] = {}
        box_keys_set: dict[str, bool] = {}
        box_score_key_set: dict[str, bool] = {}
        class_map: dict[int, str] = {}
        for row in rows:
            image_example = row[col_name]
            if image_example is None:
                continue
            image_example = typing.cast(wbmedia.ImageArtifactFileRef, image_example)

            # Add the mask keys to the running set
            if image_example.masks is not None:
                mask_keys_set.update(dict.fromkeys(image_example.masks.keys()))

            # Add the box keys to the running set
            if image_example.boxes is not None:
                box_keys_set.update(dict.fromkeys(image_example.boxes.keys()))

                # Add the box score keys to the running set
                for box_set in image_example.boxes.values():
                    for box in box_set:
                        if "scores" in box and box["scores"] is not None:
                            box_score_key_set.update(
                                dict.fromkeys(box["scores"].keys())
                            )

            # Fetch the class data (requires a network call) and update the class map
            if image_example.classes is not None and "path" in image_example.classes:
                classes_path = image_example.classes["path"]
                classes_file = file.artifact.path_info(classes_path)
                if classes_file is None or isinstance(
                    classes_file, artifact_fs.FilesystemArtifactDir
                ):
                    raise errors.WeaveInternalError(
                        "classes_file is None or a directory"
                    )
                with classes_file.open() as f:
                    tracer = engine_trace.tracer()
                    with tracer.trace("classes_file:jsonload"):
                        classes_data = json.load(f)
                if (
                    "class_set" in classes_data
                    and classes_data["class_set"] is not None
                ):
                    for class_item in classes_data["class_set"]:
                        if (
                            "id" in class_item
                            and "name" in class_item
                            and class_map.get(class_item["id"]) is None
                        ):
                            class_map[class_item["id"]] = class_item["name"]

            # Update the number of loaded rows
            non_null_rows_evaluated += 1
            if non_null_rows_evaluated >= 10:
                break

        # Finally, construct the needed objects
        class_keys = list(class_map.keys())
        box_layers = {box_key: class_keys for box_key in box_keys_set}
        mask_layers = {box_key: class_keys for box_key in mask_keys_set}

        new_image_type = wbmedia.ImageArtifactFileRefType(
            boxLayers=box_layers,
            boxScoreKeys=list(box_score_key_set),
            maskLayers=mask_layers,
            classMap=class_map,
        )

        return_prop_types[col_name] = types.union(*other_members, new_image_type)
    return types.TypedDict(return_prop_types)


def should_infer_type_from_data(col_type: types.Type) -> bool:
    status = {"found_unknown": False}

    def is_unknown_type_mapper(t: types.Type) -> None:
        status["found_unknown"] = status["found_unknown"] or isinstance(
            t, (types.UnknownType, types.Any)
        )

    types.map_leaf_types(col_type, is_unknown_type_mapper)

    return status["found_unknown"]


def _get_rows_and_object_type_from_weave_format(
    data: typing.Any,
    file: artifact_fs.FilesystemArtifactFile,
    sample_max_rows: int = 1000,
) -> tuple[list, types.TypedDict]:
    rows = []
    artifact = file.artifact
    if not isinstance(artifact, artifact_wandb.WandbArtifact):
        raise errors.WeaveInternalError(
            "Weave table file format is only supported for wandb artifacts"
        )
    row_data = data["data"]
    # Always convert the column names to string names
    column_types = data["column_types"]
    column_names = [str(c) for c in data["columns"]]
    converted_object_type = wandb_util.weave0_type_json_to_weave1_type(column_types)
    if not isinstance(converted_object_type, types.TypedDict):
        raise errors.WeaveInternalError(
            "Weave table file format only supports typed dicts"
        )
    converted_object_type = types.TypedDict(
        {str(k): v for k, v in converted_object_type.property_types.items()}
    )
    # Fix two things:
    # 1. incoming table column names may not match the order of column_types
    # 2. if we had an unknown (happens when old type is "PythonObjectType")
    #    we need to manually detect the type.
    obj_prop_types = {}
    for i, key in enumerate(column_names):
        if key not in converted_object_type.property_types:
            raise errors.WeaveTableDeserializationError(
                f"Column name {key} not found in column_types"
            )
        col_type = converted_object_type.property_types[key]
        if should_infer_type_from_data(col_type):
            # Sample some data to detect the type. Otherwise this
            # can be very expensive. This could cause down-stream crashes,
            # for example if we don't realize that a column is union of string
            # and int, saving to arrow will crash.
            unknown_col_example_data = [
                row[i] for row in util.sample_rows(row_data, sample_max_rows)
            ]
            obj_prop_types[key] = _infer_type_from_col_list(unknown_col_example_data)
            logging.warning(
                f"Column {key} had type {col_type} requiring data-inferred type. Inferred type as {obj_prop_types[key]}. This may be incorrect due to data sampling"
            )
        else:
            obj_prop_types[key] = col_type
    object_type = types.TypedDict(obj_prop_types)

    raw_rows = [dict(zip(column_names, row)) for row in row_data]
    rows = _table_data_to_weave1_objects(raw_rows, file, object_type)
    object_type = _patch_legacy_image_file_types(rows, object_type, file)

    rows, object_type = _in_place_join_in_linked_tables(
        rows, object_type, column_types, file
    )

    return rows, object_type


def _get_rows_and_object_type_from_legacy_format(
    data: dict, file: artifact_fs.FilesystemArtifactFile, sample_max_rows: int = 1000
) -> tuple[list, types.TypedDict]:
    # W&B dataframe columns are ints, we always want strings
    data["columns"] = [str(c) for c in data["columns"]]
    raw_rows = [dict(zip(data["columns"], row)) for row in data["data"]]
    object_type = _infer_type_from_row_dicts(
        util.sample_rows(raw_rows, sample_max_rows)
    )

    rows = _table_data_to_weave1_objects(raw_rows, file, object_type)
    object_type = _patch_legacy_image_file_types(rows, object_type, file, True)

    return rows, object_type


@dataclasses.dataclass
class _TableLikeAWLFromFileResult:
    awl: ops_arrow.ArrowWeaveList
    data: dict


def _get_table_data_from_file(file: artifact_fs.FilesystemArtifactFile) -> dict:
    tracer = engine_trace.tracer()
    if file is None or isinstance(file, artifact_fs.FilesystemArtifactDir):
        raise errors.WeaveInternalError("File is None or a directory")
    with file.open() as f:
        with tracer.trace("get_table:jsonload"):
            data = json.load(f)
    return data


def _get_table_like_awl_from_file(
    file: typing.Union[
        artifact_fs.FilesystemArtifactFile, artifact_fs.FilesystemArtifactDir, None
    ],
    num_parts: int = 1,
) -> _TableLikeAWLFromFileResult:
    if file is None or isinstance(file, artifact_fs.FilesystemArtifactDir):
        raise errors.WeaveInternalError("File is None or a directory")
    data = _get_table_data_from_file(file)
    if file.path.endswith(".joined-table.json"):
        awl = _get_joined_table_awl_from_file(data, file)
    elif file.path.endswith(".partitioned-table.json"):
        awl = _get_partitioned_table_awl_from_file(data, file)
    elif file.path.endswith(".table.json"):
        awl = _get_table_awl_from_file(data, file, num_parts)
    else:
        raise errors.WeaveInternalError(
            f"Unknown table file format for path: {file.path}"
        )
    return _TableLikeAWLFromFileResult(awl, data)


def _get_rows_and_object_type_awl_from_file(
    data: dict,
    file: artifact_fs.FilesystemArtifactFile,
    num_parts: int = 1,
) -> typing.Tuple[list, types.Type]:
    tracer = engine_trace.tracer()
    rows: list = []
    object_type = None
    with tracer.trace("get_table:get_rows_and_object_type"):
        sample_max_rows = max(1000 // num_parts, 1)
        if _data_is_weave_file_format(data):
            rows, object_type = _get_rows_and_object_type_from_weave_format(
                data, file, sample_max_rows
            )
        elif _data_is_legacy_run_file_format(data):
            rows, object_type = _get_rows_and_object_type_from_legacy_format(
                data, file, sample_max_rows
            )
        else:
            raise errors.WeaveInternalError("Unknown table file format for data")

    return rows, object_type


def _get_table_awl_from_rows_object_type(
    rows: list, object_type: types.Type, file: artifact_fs.FilesystemArtifactFile
) -> "ops_arrow.ArrowWeaveList":
    tracer = engine_trace.tracer()
    with tracer.trace("get_table:to_arrow"):
        return ops_arrow.to_arrow_from_list_and_artifact(
            rows, object_type, file.artifact
        )


def _get_table_awl_from_file(
    data: dict, file: artifact_fs.FilesystemArtifactFile, num_parts: int = 1
) -> "ops_arrow.ArrowWeaveList":
    rows, object_type = _get_rows_and_object_type_awl_from_file(data, file, num_parts)
    return _get_table_awl_from_rows_object_type(rows, object_type, file)


def _get_partitioned_table_awl_from_file(
    data: dict, file: artifact_fs.FilesystemArtifactFile
) -> ops_arrow.ArrowWeaveList:
    parts_path_root = data["parts_path"]

    all_aws: list[ops_arrow.ArrowWeaveList] = []
    part_dir = file.artifact.path_info(parts_path_root)
    if isinstance(part_dir, artifact_fs.FilesystemArtifactDir):
        # Pre-download all the files in parallel.
        # We do this because we currently only have a synchronous pattern
        # available for resolving artifact-backed files.
        # TODO: Remove pre-download once artifact-backed files can be resolved asynchronously
        asyncio.run(ensure_files(part_dir.files))

        num_parts = len(part_dir.files)
        rrows: list[list] = []
        object_types: list[types.Type] = []
        for file in part_dir.files.values():
            data = _get_table_data_from_file(file)
            rows, object_type = _get_rows_and_object_type_awl_from_file(
                data, file, num_parts
            )
            rrows.append(rows)
            object_types.append(object_type)
        object_type = types.union(*object_types)

        for rows, file in zip(rrows, part_dir.files.values()):
            all_aws.append(
                _get_table_awl_from_rows_object_type(rows, object_type, file)
            )
    arrow_weave_list = ops_arrow.ops.concat.raw_resolve_fn(all_aws)
    return arrow_weave_list


# Download files in a `FilesystemArtifactDir` in parallel.
# This only downloads files that are `WandbArtifact`s and have a resolved `_read_artifact_uri`.
async def ensure_files(files: dict[str, artifact_fs.FilesystemArtifactFile]):
    client = io_service.get_async_client()

    loop = asyncio.get_running_loop()

    tasks = set()
    async with client.connect() as conn:
        for file in files.values():
            if (
                isinstance(file.artifact, artifact_wandb.WandbArtifact)
                and file.artifact._read_artifact_uri
            ):
                uri = file.artifact._read_artifact_uri.with_path(file.path)
                task = loop.create_task(conn.ensure_file(uri))
                tasks.add(task)
        await asyncio.wait(tasks)


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
    arrow_weave_list = ops_arrow.list_join.join_2.raw_resolve_fn(
        awl_1, awl_2, join_fn_1.val, join_fn_2.val, "0", "1", True, True
    )
    return arrow_weave_list


@op(name="file-table")
def file_table(file: artifact_fs.FilesystemArtifactFile) -> typing.Optional[Table]:
    # We do a try/catch here because it is possible that the `file` does not
    # exist. This can happen if the user has deleted the referenced artifact. In
    # this case we will throw a `FileNotFoundError` when calling file.open().
    # Technically we probably should do this try/catch in every case of
    # `file.open` (for example in file-contents, file-media, etc...). However,
    # in practice, the `file.open` should only fail if the File is constructed
    # directly (as opposed to use the `artifact.path_info` method - since
    # `path_info` will return None in this case). This only happens when pulling
    # a file from run summary since it is constructed from a hard-coded artifact
    # URL. This path is only used when fetching tables.
    try:
        return Table(_get_table_like_awl_from_file(file).awl)
    except FileNotFoundError as e:
        return None


@op(name="file-partitionedTable")
def partitioned_table(
    file: artifact_fs.FilesystemArtifactFile,
) -> typing.Optional[PartitionedTable]:
    # Please see comment in `file_table` regarding try/catch
    try:
        res = _get_table_like_awl_from_file(file)
    except FileNotFoundError as e:
        return None
    return PartitionedTable(res.awl, file, res.data)


@op(name="file-joinedTable")
def joined_table(
    file: artifact_fs.FilesystemArtifactFile,
) -> typing.Optional[JoinedTable]:
    # Please see comment in `file_table` regarding try/catch
    try:
        return JoinedTable(_get_table_like_awl_from_file(file).awl, file)
    except FileNotFoundError as e:
        return None
