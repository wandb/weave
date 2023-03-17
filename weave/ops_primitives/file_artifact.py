import typing
from ..api import op
from .. import artifact_fs


@op(name="FilesystemArtifactFile-directUrl")
def direct_url(file: artifact_fs.FilesystemArtifactFile) -> typing.Optional[str]:
    return file.artifact.direct_url(file.path)


@op(name="FilesystemArtifactFile-directUrlAsOf")
def direct_url_as_of(
    file: artifact_fs.FilesystemArtifactFile, asOf: int
) -> typing.Optional[str]:
    return file.artifact.direct_url(file.path)


@op(name="FilesystemArtifactFile-artifactVersion")
def file_artifact(
    file: artifact_fs.FilesystemArtifactFile,
) -> artifact_fs.FilesystemArtifact:
    return file.artifact
