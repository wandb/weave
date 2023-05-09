import typing

from . import types
from ..api import op
from .. import artifact_fs


@op(name="FilesystemArtifact-fileRefineType")
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
