# Implements backward compatibility for existing W&B Media types.

from ..language_features.tagging.tag_store import isolated_tagging_context
from .. import types
from .. import errors
from .. import api as weave
from .. import artifact_fs
from ..ops_primitives import html
from ..ops_primitives import markdown


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


@weave.type(__override_name="html-file")  # type: ignore
class HtmlArtifactFileRef:
    artifact: artifact_fs.FilesystemArtifact
    path: str


# When a WB table is written to disk, it accumulates all the NDArrays into a
# single file so that these columns can be stored more efficiently. In the UI,
# we completely ignore such columns. The underlying data is even Nulled out!
#  With Weave1, we actually have the possibility of doing something with them if
# we wanted to! There are additional properties which we could use to add value:
# {"params": {"serialization_path": {"key": "output", "path":
# "media/serialized_data/498587e8.npz"}, "shape": [10]} However, I suspect we
# will just use the newer Weave1 NDArray type instead.
class LegacyTableNDArrayType(types.Type):
    name = "ndarray"


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
    output_type=artifact_fs.FilesystemArtifactFileType(
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
    HtmlArtifactFileRef.WeaveType(),  # type: ignore
)


@weave.op(
    name="asset-artifactVersion",
    input_type={"asset": ArtifactAssetType},
    output_type=artifact_fs.FilesystemArtifactType(),
)
def artifactVersion(asset):
    return asset.artifact
