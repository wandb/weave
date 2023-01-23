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
# We could return the union here and add a refiner, but there is a problem
# with compile/vectorization getting stuck in an infinite loop if we do
# so.
# TODO: fix
@op(name="FilesystemArtifact-file")
def artifact_file(
    artifact: artifact_fs.FilesystemArtifact, path: str
) -> typing.Optional[artifact_fs.FilesystemArtifactFile]:
    return artifact.path_info(path)  # type:ignore
