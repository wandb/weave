import typing

from . import types
from ..api import op
from .. import artifact_fs


@op(name="FilesystemArtifact-fileRefineType")
def artifact_file_refine_type(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> types.Type:
    return types.TypeRegistry.type_of(artifact.path_info(path))


@op(name="FilesystemArtifact-file")
def artifact_file(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> typing.Optional[artifact_fs.FilesystemArtifactFile]:
    item = artifact.path_info(path)
    if not isinstance(item, artifact_fs.FilesystemArtifactFile):
        return None
    return item
