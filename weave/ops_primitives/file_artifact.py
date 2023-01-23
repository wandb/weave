import os

from ..api import op
from .. import artifact_fs
from .. import environment


@op(name="FilesystemArtifactFile-directUrl")
def direct_url(file: artifact_fs.FilesystemArtifactFile) -> str:
    art_path = file.artifact.path(file.path)
    local_path = os.path.abspath(art_path)
    return f"{environment.weave_server_url()}/__weave/file/{local_path}"


@op(name="FilesystemArtifactFile-direct_url_as_of")
def direct_url_as_of(file: artifact_fs.FilesystemArtifactFile, asOf: int) -> str:
    art_path = file.artifact.path(file.path)
    local_path = os.path.abspath(art_path)
    return f"{environment.weave_server_url()}/__weave/file/{local_path}"


@op(name="FilesystemArtifactFile-artifactVersion")
def file_artifact(
    file: artifact_fs.FilesystemArtifactFile,
) -> artifact_fs.FilesystemArtifact:
    return file.artifact
