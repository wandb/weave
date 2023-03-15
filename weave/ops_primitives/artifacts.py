import typing

from . import types
from ..api import op
from .. import artifact_fs


@op(name="FilesystemArtifact-fileRefineType")
def artifact_file_refine_type(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> types.Type:
    return types.TypeRegistry.type_of(artifact.path_info(path))


@op(
    name="FilesystemArtifact-file",
    refine_output_type=artifact_file_refine_type,
)
def artifact_file(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> typing.Union[
    None, artifact_fs.FilesystemArtifactFile, artifact_fs.FilesystemArtifactDir
]:
    return artifact.path_info(path)  # type:ignore
