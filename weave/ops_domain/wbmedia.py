# Implements backward compatibility for existing W&B Media types.

import contextlib
import typing

from ..artifact_wandb import WandbRunFilesProxyArtifact, get_wandb_read_client_artifact
from ..language_features.tagging.tag_store import isolated_tagging_context
from .. import types
from .. import errors
from .. import api as weave
from .. import artifact_fs
from .. import file_util
from ..ops_primitives import html
from ..ops_primitives import markdown
from . import table


@weave.type(__override_name="image-file")  # type: ignore
class ImageArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str
    format: str
    height: int
    width: int
    sha256: str


@weave.type(__override_name="audio-file")  # type: ignore
class AudioArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


@weave.type(__override_name="bokeh-file")  # type: ignore
class BokehArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


@weave.type(__override_name="video-file")  # type: ignore
class VideoArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


@weave.type(__override_name="object3D-file")  # type: ignore
class Object3DArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


@weave.type(__override_name="molecule-file")  # type: ignore
class MoleculeArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


table_client_artifact_scheme = "wandb-client-artifact://"
table_artifact_scheme = "wandb-artifact://"


def _parse_artifact_path(path: str) -> typing.Tuple[str, str]:
    """Returns art_id, file_path. art_id might be client_id or seq:alias"""
    if path.startswith(table_artifact_scheme):
        path = path[len(table_artifact_scheme) :]
    elif path.startswith(table_client_artifact_scheme):
        path = path[len(table_client_artifact_scheme) :]
    else:
        raise ValueError('unknown artifact path scheme: "%s"' % path)
    art_identifier, file_path = path.split("/", 1)
    return art_identifier, file_path


@weave.type(__override_name="table-file")  # type: ignore
class TableClientArtifactFileRef:
    artifact_path: str

    def __init__(self, artifact_path):
        self.artifact_path = artifact_path
        self._artifact = None
        self._art_id, self._file_path = _parse_artifact_path(artifact_path)

    @property
    def artifact(self):
        if self._artifact == None:
            self._artifact = get_wandb_read_client_artifact(self._art_id)
        return self._artifact

    @property
    def path(self):
        return self._file_path

    # This is a temp hack until we have better support for _base_type inheritance
    @weave.op(
        name="tablefile-table",
        output_type=table.TableType(),
    )
    def table(self):
        path_info = self.artifact.path_info(self._file_path)
        if path_info is None:
            return None
        return table.file_table.resolve_fn(path_info)


@weave.type(__override_name="joinedtable-file")  # type: ignore
class JoinedTableClientArtifactFileRef:
    artifact_path: str

    def __init__(self, artifact_path):
        self.artifact_path = artifact_path
        self._artifact = None
        self._art_id, self._file_path = _parse_artifact_path(artifact_path)

    @property
    def artifact(self):
        if self._artifact == None:
            self._artifact = get_wandb_read_client_artifact(self._art_id)
        return self._artifact

    @property
    def path(self):
        return self._file_path

    @weave.op(
        name="joinedtablefile-joinedTable",
        output_type=table.JoinedTableType(),
    )
    def joined_table(self):
        path_info = self.artifact.path_info(self._file_path)
        if path_info is None:
            return None
        return table.joined_table.resolve_fn(self)


@weave.type(__override_name="runtable-file")  # type: ignore
class TableRunFileRef:
    entity_name: str
    project_name: str
    run_name: str
    file_path: str

    def __init__(self, entity_name, project_name, run_name, file_path):
        self.entity_name = entity_name
        self.project_name = project_name
        self.run_name = run_name
        self.file_path = file_path
        self.artifact = WandbRunFilesProxyArtifact(
            self.entity_name, self.project_name, self.run_name
        )

    # file_base.File interface
    @contextlib.contextmanager
    def open(self, mode: str = "r") -> typing.Generator[typing.IO, None, None]:
        if "r" in mode:
            with file_util.safe_open(self.artifact.path(self.file_path)) as f:
                yield f
        else:
            raise NotImplementedError

    @property
    def path(self):
        return self.file_path

    # This is a temp hack until we have better support for _base_type inheritance
    @weave.op(
        name="runtablefile-table",
        output_type=table.TableType(),
    )
    def table(self):
        return table.file_table.resolve_fn(self)


@weave.type(__override_name="runjoinedtable-file")  # type: ignore
class JoinedTableRunFileRef:
    entity_name: str
    project_name: str
    run_name: str
    file_path: str

    def __init__(self, entity_name, project_name, run_name, file_path):
        self.entity_name = entity_name
        self.project_name = project_name
        self.run_name = run_name
        self.file_path = file_path
        self.artifact = WandbRunFilesProxyArtifact(
            self.entity_name, self.project_name, self.run_name
        )

    # file_base.File interface
    @contextlib.contextmanager
    def open(self, mode: str = "r") -> typing.Generator[typing.IO, None, None]:
        if "r" in mode:
            with file_util.safe_open(self.artifact.path(self.file_path)) as f:
                yield f
        else:
            raise NotImplementedError

    @property
    def path(self):
        return self.file_path

    # This is a temp hack until we have better support for _base_type inheritance
    @weave.op(
        name="runjoinedtablefile-joinedTable",
        output_type=table.JoinedTableType(),
    )
    def joined_table(self):
        return table.joined_table.resolve_fn(self)


@weave.type(__override_name="html-file")  # type: ignore
class HtmlArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


# This shows a pattern for how to convert an in memory object (Html)
# to a W&B media type style FileRef, so that the existing frontend
# code can work with it.
@weave.op()
def html_file(html: html.Html) -> HtmlArtifactFileRef:
    from weave import storage

    # This is a ref to the html object
    with isolated_tagging_context():
        ref = storage.save(html)
    path = ref.path
    if path is None:
        raise errors.WeaveInternalError("storage save returned None path")
    file_path = path + ".html"
    return HtmlArtifactFileRef(ref.artifact, file_path)


# Yet another pattern for returning a file inside an artifact!
# In this case, the WeaveJS Markdown panel expects a 'file' type
# (with extension in the type).
# TODO: merge all these patterns!!!!
@weave.op(
    output_type=artifact_fs.FilesystemArtifactType(
        weave.types.Const(weave.types.String(), "md")  # type: ignore
    )
)
def markdown_file(md: markdown.Markdown):
    from weave import storage

    with isolated_tagging_context():
        ref = storage.save(md)
    path = ref.path
    if path is None:
        raise errors.WeaveInternalError("storage save returned None path")
    return artifact_fs.FilesystemArtifactFile(ref.artifact, path + ".md")


ArtifactAssetType = types.union(
    ImageArtifactFileRef.WeaveType(),  # type: ignore
    AudioArtifactFileRef.WeaveType(),  # type: ignore
    BokehArtifactFileRef.WeaveType(),  # type: ignore
    VideoArtifactFileRef.WeaveType(),  # type: ignore
    Object3DArtifactFileRef.WeaveType(),  # type: ignore
    MoleculeArtifactFileRef.WeaveType(),  # type: ignore
    TableClientArtifactFileRef.WeaveType(),  # type: ignore
    JoinedTableClientArtifactFileRef.WeaveType(),  # type: ignore
    HtmlArtifactFileRef.WeaveType(),  # type: ignore
)


@weave.op(
    name="asset-artifactVersion",
    input_type={"asset": ArtifactAssetType},
    output_type=artifact_fs.FilesystemArtifactType(),
)
def artifactVersion(asset):
    return asset.artifact
