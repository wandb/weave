import typing
from urllib import parse
from .. import weave_types as types
from .. import decorator_type


from . import table
from .. import artifact_fs

from dataclasses import dataclass


from ..artifact_wandb import (
    WandbArtifact,
    WeaveWBLoggedArtifactURI,
)

from . import history
from ..runfiles_wandb import WeaveWBRunFilesURI, WandbRunFiles


@dataclass
class RunPath:
    entity_name: str
    project_name: str
    run_name: str


# Avoiding name collision with PanelHistogram ('histogram') for now.
@decorator_type.type()
class WbHistogram:
    bins: list[float]
    values: list[int]


def filesystem_artifact_file_from_artifact_path(artifact_path: str):
    uri = WeaveWBLoggedArtifactURI.parse(artifact_path)
    artifact = WandbArtifact(uri=uri, name=uri.name)
    file_path = uri.path
    if file_path is None:
        raise ValueError("Artifact path must contain a file path")
    return artifact_fs.FilesystemArtifactFile(artifact, file_path)


def filesystem_runfiles_from_run_path(run_path: RunPath, file_path: str):
    uri = WeaveWBRunFilesURI(
        f"{run_path.entity_name}/{run_path.project_name}/{run_path.run_name}",
        None,
        run_path.entity_name,
        run_path.project_name,
        run_path.run_name,
    )
    runfiles = WandbRunFiles(name=uri.name, uri=uri)
    return runfiles.path_info(file_path)


def process_run_dict_obj(run_dict, run_path: typing.Optional[RunPath] = None):
    return {
        k: _process_run_dict_item(v, run_path)
        for k, v in run_dict.items()
        if k != "_wandb"
    }


def escape_artifact_path(artifact_path: str) -> str:
    prefix = "wandb-client-artifact://"
    if artifact_path.startswith(prefix):
        artifact_path = artifact_path[len(prefix) :]
        if ":" in artifact_path:
            name, version_path = artifact_path.split(":", 1)
            version, path = version_path.split("/", 1)
        else:
            version = None
            name, path = artifact_path.split("/", 1)
        path = parse.quote(path, safe="")
        version_string = f":{version}" if version is not None else ""
        artifact_path = f"{prefix}{name}{version_string}/{path}"
    return artifact_path


def _process_run_dict_item(val, run_path: typing.Optional[RunPath] = None):
    if isinstance(val, dict) and "_type" in val:
        if val["_type"] == "histogram":
            if "packedBins" in val:
                bins = []
                bin_min = val["packedBins"]["min"]
                for i in range(val["packedBins"]["count"]):
                    bins.append(bin_min)
                    bin_min += val["packedBins"]["size"]
            else:
                bins = val["bins"]
            return WbHistogram(
                bins=bins,
                values=val["values"],
            )
        if val["_type"] == "table-file":
            if "artifact_path" in val:
                artifact_path = escape_artifact_path(val["artifact_path"])
                return filesystem_artifact_file_from_artifact_path(artifact_path)
            elif "path" in val and run_path is not None:
                return filesystem_runfiles_from_run_path(run_path, val["path"])

        if val["_type"] in ["joined-table", "partitioned-table"]:
            return filesystem_artifact_file_from_artifact_path(val["artifact_path"])

        if val["_type"] == "image-file" and run_path is not None:
            from . import ImageArtifactFileRef

            fs_artifact_file = filesystem_runfiles_from_run_path(run_path, val["path"])
            return ImageArtifactFileRef(
                fs_artifact_file.artifact,
                fs_artifact_file.path,
                format=val["format"],
                width=val["width"],
                height=val["height"],
                sha256=val["sha256"],
            )
        if val["_type"] == "wb_trace_tree":
            from .trace_tree import WBTraceTree

            return WBTraceTree(
                root_span_dumps=val.get("root_span_dumps"),  # type: ignore
                model_dict_dumps=val.get("model_dict_dumps"),
                model_hash=val.get("model_hash"),
            )

    return val


def process_run_dict_type(run_dict):
    return types.TypedDict(
        {
            k: _process_run_dict_item_type(v)
            for k, v in run_dict.items()
            if k != "_wandb"
        }
    )


def _process_run_dict_item_type(val):
    if isinstance(val, dict):
        type_count = {"type": val.get("_type", None)}
        type = history.history_key_type_count_to_weave_type(type_count)
        if type != types.UnknownType():
            return type
    return types.TypeRegistry.type_of(val)
