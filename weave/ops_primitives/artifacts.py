import datetime
import os
import pathlib
import typing

from .. import ref_base

from ..artifact_local import WORKING_DIR_PREFIX, LocalArtifact
from . import types
from ..api import op
from .. import artifact_fs


@op(name="FilesystemArtifact-fileRefineType", hidden=True)
def artifact_file_refine_type(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> types.Type:
    return types.TypeRegistry.type_of(artifact.path_info(path))


# Warning: the return type of this is incorrect! Weave0 treats
# type 'file' (FilesystemArtifactFile) as both dir and file.
# We have a refiner to do the correct thing, but the return
# type is set to `File` so that the first non-refine compile
# path will still work.
@op(
    name="FilesystemArtifact-file",
    refine_output_type=artifact_file_refine_type,
)
def artifact_file(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> typing.Union[
    None, artifact_fs.FilesystemArtifactFile  # , artifact_fs.FilesystemArtifactDir
]:
    return artifact.path_info(path)  # type:ignore


@op(
    name="FilesystemArtifact-artifactName",
)
def artifact_artifactname(artifact: artifact_fs.FilesystemArtifact) -> str:
    return artifact.name


@op(
    name="FilesystemArtifact-artifactVersion",
)
def artifact_artifactversion(artifact: artifact_fs.FilesystemArtifact) -> str:
    return artifact.branch or artifact.version


@op(
    name="FilesystemArtifact-artifactForVersion",
)
def artifact_version_artifact_for_version(
    artifact: artifact_fs.FilesystemArtifact,
    version: str,
) -> artifact_fs.FilesystemArtifact:
    if not isinstance(artifact, LocalArtifact):
        raise ValueError(f"Artifact {artifact.name} is not a local artifact")

    if artifact._version is not None:
        if artifact._version == version:
            return artifact
        else:
            raise ValueError(f"Artifact {artifact.name} is not version {version}")

    possible_art = LocalArtifact(artifact.name, version)
    if possible_art._read_dirname == None:
        return None  # type: ignore
    return possible_art


@op(
    name="FilesystemArtifact-weaveType",
)
def artifact_version_weave_type(
    artifact: artifact_fs.FilesystemArtifact,
) -> types.Type:
    return artifact_fs.FilesystemArtifactRef(artifact, "obj").type


@op(
    name="FilesystemArtifact-metadata",
)
def filesystem_artifact_metadata(
    artifact: artifact_fs.FilesystemArtifact,
) -> dict:
    return artifact.metadata.as_dict()


@op(
    name="FilesystemArtifact-getLatestVersion",
)
def most_recent_version(
    artifact: artifact_fs.FilesystemArtifact,
) -> artifact_fs.FilesystemArtifact:
    if not isinstance(artifact, LocalArtifact):
        raise ValueError(f"Artifact {artifact.name} is not a local artifact")

    if artifact._branch is not None and artifact._branch == "latest":
        return artifact

    possible_art = LocalArtifact(artifact.name, "latest")
    if possible_art._read_dirname != None:
        return possible_art

    obj_paths = sorted(
        pathlib.Path(artifact._root).iterdir(),
        key=os.path.getctime,
    )
    if not obj_paths:
        return None  # type: ignore

    latest_sym = None
    latest_dir = None

    for obj_path in reversed(obj_paths):
        if not obj_path.name.startswith(
            WORKING_DIR_PREFIX
        ) and not obj_path.name.startswith("."):
            if obj_path.is_symlink() and latest_sym is None:
                latest_sym = obj_path
            elif obj_path.is_dir() and latest_dir is None:
                latest_dir = obj_path
            if latest_sym is not None and latest_dir is not None:
                break

    if latest_dir is not None:
        if latest_sym is not None:
            latest_sym_points_to = latest_sym.resolve()
            if os.path.realpath(latest_sym_points_to) == os.path.realpath(latest_dir):
                return LocalArtifact(artifact.name, latest_sym.name)
            return LocalArtifact(artifact.name, obj_path.name)

    return None  # type: ignore


@op(
    name="FilesystemArtifact-previousURI",
)
def previous_uri(
    artifact: artifact_fs.FilesystemArtifact,
) -> typing.Optional[str]:
    return artifact.previous_uri()


@op(
    name="FilesystemArtifact-createdAt",
)
def created_at(
    artifact: artifact_fs.FilesystemArtifact,
) -> datetime.datetime:
    return artifact.created_at


@op(
    name="FilesystemArtifact-rootFromURI",
    pure=False,
)
def from_uri(
    uri: str,
) -> typing.Optional[artifact_fs.FilesystemArtifact]:
    ref = ref_base.Ref.from_str(uri)
    if not isinstance(ref, (artifact_fs.FilesystemArtifactRef)):
        return None
    return ref.artifact
