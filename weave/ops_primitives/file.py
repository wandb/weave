import json
import typing

from ..artifact_fs import FilesystemArtifactDir, FilesystemArtifactFile
from ..artifact_wandb import WandbArtifact, WandbArtifactManifest
from ..ops_domain.wbmedia import ImageArtifactFileRef
from ..api import op
from .. import weave_types as types
from .. import file_base
from .. import engine_trace
from .. import errors
from .. import wandb_file_manager


@op(name="dir-pathReturnType", hidden=True)
def path_return_type(dir: file_base.Dir, path: str) -> types.Type:
    return types.TypeRegistry.type_of(dir.path_info(path))


@op(
    name="dir-path",
    refine_output_type=path_return_type,
)
def open(
    dir: file_base.Dir, path: str
) -> typing.Union[file_base.File, file_base.Dir, None]:
    return dir.path_info(path)


def _file_dict_from_manifest(
    file: FilesystemArtifactFile, manifest: WandbArtifactManifest
) -> dict:

    art = file.artifact
    if not isinstance(art, WandbArtifact):
        return _file_dict(file)

    entry = manifest.get_entry_by_path(file.path)
    if entry is None:
        return _file_dict(file)

    digest = entry.get("digest")
    size = entry.get("size") or 0

    base_dict = {
        "birthArtifactID": "TODO",
        "digest": digest,
        "fullPath": file.path,
        "size": size,
        "type": "file",
    }

    ref = entry.get("ref")
    if ref is not None:
        base_dict["ref"] = ref

    # if the ref exists then use that for the URL
    if "ref" in base_dict:
        base_dict["url"] = base_dict["ref"]
    else:
        res = wandb_file_manager._local_path_and_download_url(
            art.uri_obj.with_path(file.path),
            manifest,
        )
        if res:
            base_dict["url"] = res[1]
        else:
            base_dict["url"] = None

    return base_dict


def _file_dict(file: FilesystemArtifactFile) -> dict:
    if isinstance(file.artifact, WandbArtifact):
        raise ValueError(
            "WandbArtifact passed to _file_dict. This is not supported. Use _file_dict_from_manifest instead."
        )

    return {
        "birthArtifactID": "TODO",
        "digest": file.digest(),
        "fullPath": file.path,
        "size": file.artifact.size(file.path),
        "type": "file",
        "url": file.artifact.direct_url(file.path),
    }


@op(
    name="dir-_as_w0_dict_",
)
def _as_w0_dict_(dir: file_base.Dir) -> dict:
    if isinstance(dir, FilesystemArtifactDir) and isinstance(
        dir.artifact, WandbArtifact
    ):
        manifest = dir.artifact._manifest()
    else:
        manifest = None
    if not isinstance(dir, FilesystemArtifactDir):
        raise errors.WeaveInternalError("Dir must be FilesystemArtifactDir")
    return {
        "fullPath": dir.fullPath,
        "size": dir.size,
        "dirs": {
            k: {
                "fullPath": v.fullPath,
                "size": v.size,
                "dirs": v.dirs,
                "files": v.files,
            }
            for k, v in dir.dirs.items()
        },
        "files": {
            k: _file_dict_from_manifest(v, manifest)
            if manifest is not None
            else _file_dict(v)
            for k, v in dir.files.items()
        },
    }


@op(name="file-directUrlAsOf")
def direct_url_as_of(file: file_base.File, asOf: int) -> str:
    # This should only be used in the first dispatch phase
    raise NotImplementedError


@op(name="file-contents")
def file_contents(file: file_base.File) -> str:
    with file.open("r") as f:
        return f.read()


@op(name="file-dir")
def artifactfile_dir(
    item: typing.Union[file_base.File, file_base.Dir],
) -> typing.Optional[file_base.Dir]:
    if not isinstance(item, file_base.Dir):
        return None
    return item


@op(name="file-type")
def file_type(file: typing.Union[file_base.File, file_base.Dir]) -> types.Type:
    return types.TypeRegistry.type_of(file)


@op(name="file-path")
def file_path(file: file_base.File) -> str:
    return file.path


@op(name="file-size")
def file_size(file: file_base.File) -> int:
    return file.size()


@op(name="file-digest")
def file_digest(file: file_base.File) -> typing.Optional[str]:
    return file.digest()


@op(name="file-media", output_type=lambda input_types: input_types["file"].wbObjectType)
def file_media(file: FilesystemArtifactFile):
    if isinstance(file, FilesystemArtifactDir):
        raise errors.WeaveInternalError("File is None or a directory")
    tracer = engine_trace.tracer()
    with file.open() as f:
        with tracer.trace("file_media:jsonload"):
            data = json.load(f)
    if "path" not in data or data["path"] is None:
        raise errors.WeaveInternalError("Media File is missing path")
    file_path = data["path"]
    if file.path.endswith(".image-file.json"):
        res = ImageArtifactFileRef(
            artifact=file.artifact,
            path=file_path,
            format=data["format"],
            height=data.get("height", 0),
            width=data.get("width", 0),
            sha256=data.get("sha256", file_path),
        )
    elif any(
        file.path.endswith(path_suffix)
        for path_suffix in [
            ".audio-file.json",
            ".bokeh-file.json",
            ".video-file.json",
            ".object3D-file.json",
            ".molecule-file.json",
            ".html-file.json",
        ]
    ):
        type_cls, _ = file_base.wb_object_type_from_path(file.path)
        if type_cls.instance_class is None:
            raise errors.WeaveInternalError(
                f"op file-media: Media Type has not bound instance_class: {file.path}: {type_cls}"
            )
        res = type_cls.instance_class(
            file.artifact, file_path, data.get("sha256", file_path)
        )
    else:
        raise errors.WeaveInternalError(
            f"op file-media: Unknown media file type: {file.path}"
        )
    return res
