# Implements backward compatibilty for existing W&B Media types.

import copy
import dataclasses
import typing

from wandb.apis import public as wandb_api

from ..artifacts_local import get_wandb_read_client_artifact
from ..language_features.tagging.tag_store import isolated_tagging_context
from .. import types
from .. import api as weave
from ..ops_primitives import html
from ..ops_primitives import markdown
from ..ops_primitives import file
from . import file_wbartifact
from . import wbartifact


## This is an ArtifactRefii, that lets us get access to the ref
# artifact/path during loading.


class ArtifactEntryType(types.Type):
    def save_instance(self, obj, artifact, name):
        # No-op, this is already a saved ArtifactEntry!
        pass

    def load_instance(self, artifact, name, extra=None):
        return ArtifactEntry(artifact, name)


@dataclasses.dataclass
class ArtifactEntry:
    artifact: typing.Any  # Artifact
    path: str


ArtifactEntryType.instance_classes = ArtifactEntry
ArtifactEntryType.instance_class = ArtifactEntry


@weave.type(__override_name="image-file")  # type: ignore
class ImageArtifactFileRef:
    # TODO: just File? No, because the frontend is going to call .artifactVersion()
    #     on us. So we need to be ImageArtifactEntry
    path: ArtifactEntry  # This should be a Ref<File<ImageExtensions>>
    format: str
    height: int
    width: int
    sha256: str

    @property
    def artifact(self):
        return self.path.artifact


@weave.type(__override_name="audio-file")  # type: ignore
class AudioArtifactFileRef:
    path: ArtifactEntry

    @property
    def artifact(self):
        return self.path.artifact


@weave.type(__override_name="bokeh-file")  # type: ignore
class BokehArtifactFileRef:
    path: ArtifactEntry

    @property
    def artifact(self):
        return self.path.artifact


@weave.type(__override_name="video-file")  # type: ignore
class VideoArtifactFileRef:
    path: ArtifactEntry

    @property
    def artifact(self):
        return self.path.artifact


@weave.type(__override_name="object3D-file")  # type: ignore
class Object3DArtifactFileRef:
    path: ArtifactEntry

    @property
    def artifact(self):
        return self.path.artifact


@weave.type(__override_name="molecule-file")  # type: ignore
class MoleculeArtifactFileRef:
    path: ArtifactEntry

    @property
    def artifact(self):
        return self.path.artifact


table_client_artifact_file_scheme = "wandb-client-artifact://"
table_artifact_file_scheme = "wandb-artifact://"


def _parse_artifact_path(path: str) -> typing.Tuple[str, str]:
    """Returns art_id, file_path. art_id might be client_id or seq:alias"""
    if path.startswith(table_artifact_file_scheme):
        path = path[len(table_artifact_file_scheme) :]
    elif path.startswith(table_client_artifact_file_scheme):
        path = path[len(table_client_artifact_file_scheme) :]
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
    def wb_artifact(self):
        if self._artifact == None:
            self._artifact = get_wandb_read_client_artifact(self._art_id)
        return self._artifact

    def get_local_path(self):
        return self.wb_artifact.path(self._file_path)

    # This is a temp hack until we have better support for _base_type inheritance
    @weave.op(
        name="tablefile-table",
        output_type=file.TableType(),
    )
    def table(self):
        if not hasattr(self, "artifact"):
            self.artifact = self.wb_artifact
        return file.File.table.resolve_fn(self)


@weave.type(__override_name="html-file")  # type: ignore
class HtmlArtifactFileRef:
    path: ArtifactEntry

    @property
    def artifact(self):
        return self.path.artifact


# This shows a pattern for how to convert an in memory object (Html)
# to a W&B media type style FileRef, so that the existing frontend
# code can work with it.
@weave.op()
def html_file(html: html.Html) -> HtmlArtifactFileRef:
    from weave import storage

    # This is a ref to the html object
    with isolated_tagging_context():
        ref = storage.save(html)
    ref = copy.copy(ref)
    ref.path += ".html"
    return HtmlArtifactFileRef(ref)  # type: ignore


# Yet another pattern for returning a file inside an artifact!
# In this case, the WeaveJS Markdown panel expects a 'file' type
# (with extension in the type).
# TODO: merge all these patterns!!!!
@weave.op(
    # Oof, returning a different type than the op returns. Ugly
    # Still haven't nailed type interfaces
    # TODO: fix
    output_type=weave.types.FileType(
        weave.types.Const(weave.types.String(), "md")  # type: ignore
    )
)
def markdown_file(md: markdown.Markdown):
    from weave import storage

    with isolated_tagging_context():
        ref = storage.save(md)
    return file_wbartifact.ArtifactVersionFile(ref.artifact, ref.path + ".md")


ArtifactAssetType = types.union(
    ImageArtifactFileRef.WeaveType(),  # type: ignore
    AudioArtifactFileRef.WeaveType(),  # type: ignore
    BokehArtifactFileRef.WeaveType(),  # type: ignore
    VideoArtifactFileRef.WeaveType(),  # type: ignore
    Object3DArtifactFileRef.WeaveType(),  # type: ignore
    MoleculeArtifactFileRef.WeaveType(),  # type: ignore
    TableClientArtifactFileRef.WeaveType(),  # type: ignore
    HtmlArtifactFileRef.WeaveType(),  # type: ignore
)


@weave.op(
    name="asset-artifactVersion",
    input_type={"asset": ArtifactAssetType},
    output_type=wbartifact.ArtifactVersionType(),
)
def artifactVersion(asset):
    return asset.artifact
