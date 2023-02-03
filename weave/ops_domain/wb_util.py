import typing
from .wbmedia import (
    TableRunFileRef,
    JoinedTableRunFileRef,
)
from .. import weave_types as types
from .. import decorator_type


from . import table
from .. import artifact_fs

from dataclasses import dataclass


from ..artifact_wandb import (
    WandbArtifact,
    WeaveWBLoggedArtifactURI,
)


@dataclass
class RunPath:
    entity_name: str
    project_name: str
    run_name: str


@decorator_type.type("histogram")
class Histogram:
    bins: list[float]
    values: list[int]


def filesystem_artifact_file_from_artifact_path(artifact_path: str):
    uri = WeaveWBLoggedArtifactURI.parse(artifact_path)
    artifact = WandbArtifact(uri=uri, name=uri.name)
    file_path = uri.path
    if file_path is None:
        raise ValueError("Artifact path must contain a file path")
    return artifact_fs.FilesystemArtifactFile(artifact, file_path)


def process_run_dict_obj(run_dict, run_path: typing.Optional[RunPath] = None):
    return {k: _process_run_dict_item(v, run_path) for k, v in run_dict.items()}


def _process_run_dict_item(val, run_path: typing.Optional[RunPath] = None):
    if isinstance(val, dict) and "_type" in val:
        if val["_type"] == "histogram":
            if "packedBins" in val:
                bins = []
                bin_min = val["packedBins"]["min"]
                for i in range(val["packedBins"]["count"]):
                    bins.append(bin_min)
                    bin_min += val["packedBins"]["size"]
                bins = val["packedBins"]
            else:
                bins = val["bins"]
            return Histogram(
                bins=bins,
                values=val["values"],
            )
        if val["_type"] == "table-file":
            if "artifact_path" in val:
                return filesystem_artifact_file_from_artifact_path(val["artifact_path"])
            elif "path" in val and run_path is not None:
                return TableRunFileRef(
                    run_path.entity_name,
                    run_path.project_name,
                    run_path.run_name,
                    val["path"],
                )

        if val["_type"] == "joined-table":
            if "artifact_path" in val:
                return filesystem_artifact_file_from_artifact_path(val["artifact_path"])
            elif "path" in val and run_path is not None:
                return JoinedTableRunFileRef(
                    run_path.entity_name,
                    run_path.project_name,
                    run_path.run_name,
                    val["path"],
                )

    return val


def process_run_dict_type(run_dict):
    return types.TypedDict(
        {k: _process_run_dict_item_type(v) for k, v in run_dict.items()}
    )


def _process_run_dict_item_type(val):
    if isinstance(val, dict):
        type = val.get("_type")
        if type == "histogram":
            return Histogram.WeaveType()
        if type == "joined-table":
            if "artifact_path" in val:
                extension = types.Const(
                    types.String(), val["artifact_path"].split(".")[-1]
                )
                # extension_node = make_const_node(types.String(), extension)
                return artifact_fs.FilesystemArtifactFileType(
                    extension, table.JoinedTableType()
                )
            else:
                return JoinedTableRunFileRef.WeaveType()

        if type == "table-file":
            if "artifact_path" in val:
                extension = types.Const(
                    types.String(), val["artifact_path"].split(".")[-1]
                )
                # extension_node = make_const_node(types.String(), extension)
                return artifact_fs.FilesystemArtifactFileType(
                    extension, table.TableType()
                )
            else:
                return TableRunFileRef.WeaveType()

    return types.TypeRegistry.type_of(val)
